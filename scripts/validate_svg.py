"""Preflight SVGs written for SimpleDiagrams; not a renderer or an import test.

Checks the conservative authoring subset, explicit paints, paint roots and the
canonical `data-sd-fill` / `data-sd-stroke` markings that SimpleDiagrams reads
during Convert to Editable Shape. Warnings mark
constructions that import but stop following the diagram chips; `--strict`
treats them as failures.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import stat
import unicodedata
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path

SVG_NAMESPACE = "http://www.w3.org/2000/svg"
# Authoring budget. The app's own importer accepts far larger files.
MAX_SVG_BYTES = 500_000
MAX_DEPTH = 64
MAX_ELEMENTS = 50_000
# Authoring size limit for every number in a size, coordinate, path or transform; a
# hand-drawn shape needs nothing near it, and it stays far inside what SimpleDiagrams takes.
MAX_NUMBER = 100_000
# SimpleDiagrams refuses a stroke width, miter limit or dash length above this.
MAX_STROKE = 10_000
# Attributes whose values are numbers or lists of them, all held to MAX_NUMBER.
NUMERIC_ATTRIBUTES = {
    "viewBox", "width", "height", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r",
    "rx", "ry", "d", "points", "transform", "stroke-width", "stroke-miterlimit",
    "stroke-dasharray", "stroke-dashoffset",
}  # fmt: skip
DRAWABLES = {"path", "rect", "circle", "ellipse", "polygon", "polyline", "line"}
ALLOWED_ELEMENTS = DRAWABLES | {"svg", "g", "title", "desc"}
MARKING_CARRIERS = DRAWABLES | {"g"}
# Everything else is left out by SimpleDiagrams with a warning, or refused.
ALLOWED_ATTRIBUTES = {
    "id", "version", "viewBox", "width", "height", "x", "y", "x1", "y1", "x2",
    "y2", "cx", "cy", "r", "rx", "ry", "d", "points", "transform", "fill",
    "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin",
    "stroke-miterlimit", "stroke-dasharray", "stroke-dashoffset", "fill-rule",
    "opacity", "fill-opacity", "stroke-opacity", "data-sd-fill", "data-sd-stroke",
}  # fmt: skip
OPACITY_ATTRIBUTES = {"opacity", "fill-opacity", "stroke-opacity"}
COORDINATE_ATTRIBUTES = {"x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "stroke-dashoffset"}
ENUMERATED_ATTRIBUTES = {
    "stroke-linecap": {"butt", "round", "square"},
    "stroke-linejoin": {"miter", "round", "bevel"},
    "fill-rule": {"nonzero", "evenodd"},
}
REQUIRED_GEOMETRY = {
    "path": ("d",),
    "rect": ("width", "height"),
    "circle": ("r",),
    "ellipse": ("rx", "ry"),
    "polygon": ("points",),
    "polyline": ("points",),
}
MARKING_VALUES = {"fill-chip", "stroke-chip", "keep"}
# A pinned part keeps its drawn size and its distance from one of these spots of the
# frame when the shape is resized (SimpleDiagrams desktop ADR 0042). Only a library
# shipped inside the app reads it so far; the download packager refuses it by name.
PIN_ATTRIBUTE = "data-sd-pin"
PIN_VALUES = {
    "top-left", "top", "top-right", "left", "center", "right",
    "bottom-left", "bottom", "bottom-right",
}  # fmt: skip
# A <rect> marked as a hand-drawn outline is a box the app draws by hand at every size,
# keeping its corners, its distance from the frame and its wobble at their drawn size
# (SimpleDiagrams desktop ADR 0043). Offsets list the distances inwards at which it is
# drawn, for a double or heavy border. Shipped libraries only, like pins.
OUTLINE_ATTRIBUTE = "data-sd-outline"
OUTLINE_VALUES = {"hand-drawn"}
OUTLINE_OFFSETS_ATTRIBUTE = "data-sd-outline-offsets"
MAXIMUM_OUTLINE_OFFSETS = 4
LINKED_VALUES = {"fill-chip", "stroke-chip"}
FORBIDDEN_ATTRIBUTES = {
    "vector-effect",
    "filter",
    "mask",
    "style",
    "class",
    "clip-path",
}
PAINT_RE = re.compile(r"(?:none|black|white|#[0-9a-f]{3}|#[0-9a-f]{6})")
# A resource or script scheme inside an attribute value. Matched on parsed
# attributes, never on raw source, so prose in <title>/<desc> cannot trip it.
ACTIVE_SCHEME_RE = re.compile(r"(?:^|[\s(,;'\"])(?:data|javascript)\s*:", re.IGNORECASE)
# ASCII digits only: `\d` would also accept other scripts' digits, which SimpleDiagrams refuses.
_NUMBER = r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
NUMBER_RE = re.compile(rf"^{_NUMBER}$")
MAX_TRANSFORM_BYTES = 4_096
# One transform function. Its arguments are captured whole and counted afterwards, so
# matching stays linear however much whitespace a file contains.
TRANSFORM_FUNCTION_RE = re.compile(r"(matrix|translate|scale|rotate|skewX|skewY)[ \t\r\n]*\(([^()]*)\)")
TRANSFORM_ARGUMENTS = {
    "matrix": {6}, "translate": {1, 2}, "scale": {1, 2}, "rotate": {1, 3}, "skewX": {1}, "skewY": {1},
}  # fmt: skip
# SimpleDiagrams refuses a file whose source contains these, comments included.
EXTERNAL_REFERENCE_RES = (
    re.compile(r"(?:href|src)\s*=\s*[\"']\s*(?:https?://|file:|data:)"),
    re.compile(r"url\s*\(\s*[\"']?\s*(?:https?://|file:|data:)"),
)
# A prefixed tag such as <svg:path>: valid XML, but not compiled by SimpleDiagrams.
PREFIXED_TAG_RE = re.compile(r"<\s*/?\s*[A-Za-z_][\w.-]*:[\w.-]+[\s/>]")
LENGTH_RE = re.compile(rf"^({_NUMBER})(?:px|pt|pc|mm|cm|in)?$")


@dataclass
class Report:
    """Collect validation messages for one SVG."""

    path: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, message: str) -> None:
        """Record a contract violation."""
        self.errors.append(message)

    def warn(self, message: str) -> None:
        """Record a compatibility or maintainability risk."""
        self.warnings.append(message)


def local_name(name: str) -> str:
    """Return an XML name without its namespace."""
    return name.rsplit("}", 1)[-1]


def positive_length(value: str | None) -> bool:
    """Return whether an SVG length is a finite numeric length of at least 1."""
    if value is None:
        return False
    match = LENGTH_RE.fullmatch(value.strip())
    if match is None:
        return False
    number = float(match.group(1))
    return math.isfinite(number) and number >= 1


def finite_number(value: str) -> float | None:
    """Parse one finite SVG number; `1e309` and `abc` are both None."""
    text = value.strip()
    if not NUMBER_RE.fullmatch(text):
        return None
    number = float(text)
    return number if math.isfinite(number) else None


def number_list(value: str) -> list[float] | None:
    """Parse a whitespace- or comma-separated list of finite numbers."""
    numbers = [finite_number(part) for part in re.split(r"[\s,]+", value.strip()) if part]
    return None if None in numbers else numbers  # type: ignore[return-value]


def usable_transform(value: str) -> bool:
    """Whether a transform is a list of known functions with the right number of finite arguments."""
    if len(value.encode("utf-8")) > MAX_TRANSFORM_BYTES:
        return False
    functions = list(TRANSFORM_FUNCTION_RE.finditer(value))
    # Nothing but separators may remain once the functions are taken out.
    if not functions or TRANSFORM_FUNCTION_RE.sub("", value).strip(" \t\r\n,"):
        return False
    for function in functions:
        arguments = number_list(function.group(2))
        if arguments is None or len(arguments) not in TRANSFORM_ARGUMENTS[function.group(1)]:
            return False
    return True


def value_problem(element: str, attribute: str, value: str) -> str | None:
    """Say what a geometry or stroke attribute must be, or None when it is usable.

    These are the values SimpleDiagrams must be able to read to convert the
    file at all. Path data and root sizing are checked elsewhere.
    """
    if attribute in ENUMERATED_ATTRIBUTES:
        allowed = ENUMERATED_ATTRIBUTES[attribute]
        return None if value.strip() in allowed else f"must be one of {', '.join(sorted(allowed))}"
    if attribute == "stroke-dasharray":
        dashes = None if value.strip() == "none" else number_list(value)
        usable = value.strip() == "none" or (dashes and all(0 <= dash <= MAX_STROKE for dash in dashes))
        return None if usable else f"must be none or a list of numbers from 0 to {MAX_STROKE:,}"
    if attribute == "transform":
        if usable_transform(value):
            return None
        return "must be a list of matrix, translate, scale, rotate, skewX or skewY with valid arguments"
    if attribute == "points":
        points = number_list(value)
        minimum = 6 if element == "polygon" else 4
        usable = points is not None and len(points) >= minimum and len(points) % 2 == 0
        return None if usable else "must be a list of finite x,y pairs"
    number = finite_number(value)
    if attribute == "stroke-width":
        usable = number is not None and 0 < number <= MAX_STROKE
        return None if usable else f'must be a positive number up to {MAX_STROKE:,}; use stroke="none" for no stroke'
    if attribute in OPACITY_ATTRIBUTES:
        return None if number is not None and 0 < number <= 1 else "must be a number above 0 and at most 1"
    if attribute in COORDINATE_ATTRIBUTES:
        return None if number is not None else "must be a finite number"
    if attribute == "stroke-miterlimit":
        usable = number is not None and 1 <= number <= MAX_STROKE
        return None if usable else f"must be a number from 1 to {MAX_STROKE:,}"
    if attribute == "r" or (attribute in {"rx", "ry"} and element == "ellipse"):
        return None if number is not None and number > 0 else "must be a positive number"
    if attribute in {"rx", "ry"}:
        return None if number is not None and number >= 0 else "must be a non-negative number"
    if attribute in {"width", "height"} and element == "rect":
        return None if number is not None and number > 0 else "must be a positive number"
    return None


def parse_view_box(value: str | None) -> tuple[float, float, float, float] | None:
    """Parse a finite positive SVG viewBox."""
    if value is None:
        return None
    parts = re.split(r"[\s,]+", value.strip())
    if len(parts) != 4 or not all(NUMBER_RE.fullmatch(part) for part in parts):
        return None
    numbers = tuple(float(part) for part in parts)
    if not all(math.isfinite(number) for number in numbers):
        return None
    if numbers[2] < 1 or numbers[3] < 1:
        return None
    return numbers  # type: ignore[return-value]


def inherited_paint(
    element: ET.Element,
    inherited: tuple[str | None, str | None],
) -> tuple[str | None, str | None]:
    """Track explicit paints; missing declarations remain visible to the checker."""
    fill, stroke = inherited
    if "fill" in element.attrib:
        fill = element.attrib["fill"].strip().lower()
    if "stroke" in element.attrib:
        stroke = element.attrib["stroke"].strip().lower()
    return fill, stroke


def inherited_markings(
    element: ET.Element,
    inherited: tuple[str | None, str | None],
) -> tuple[str | None, str | None]:
    """Track the effective marking of each channel, as SimpleDiagrams inherits it."""
    fill, stroke = inherited
    if element.get("data-sd-fill") in MARKING_VALUES:
        fill = element.get("data-sd-fill")
    if element.get("data-sd-stroke") in MARKING_VALUES:
        stroke = element.get("data-sd-stroke")
    return fill, stroke


def walk(
    element: ET.Element,
    inherited: tuple[str | None, str | None],
    report: Report,
    stats: dict[str, int],
    depth: int = 0,
    markings: tuple[str | None, str | None] = (None, None),
) -> None:
    """Validate one element and recursively validate its descendants."""
    name = local_name(element.tag)
    if depth >= MAX_DEPTH:
        report.error(f"nesting exceeds authoring limit of {MAX_DEPTH}; flatten groups")
        return
    if not element.tag.startswith(f"{{{SVG_NAMESPACE}}}"):
        report.error(f"foreign or missing namespace on <{name}>")
    if name not in ALLOWED_ELEMENTS:
        report.error(f"unsupported element <{name}>; use direct geometry and groups")
    if name == "svg" and depth > 0:
        report.error("nested <svg> is unsupported; flatten its coordinates")
    stats["elements"] += 1
    for required in REQUIRED_GEOMETRY.get(name, ()):
        if not element.get(required, "").strip():
            report.error(f"<{name}> requires {required}")

    for attribute, value in element.attrib.items():
        attribute_name = local_name(attribute)
        if attribute_name in FORBIDDEN_ATTRIBUTES or attribute_name.lower().startswith(
            "on"
        ):
            report.error(f"unsupported attribute {attribute_name!r} on <{name}>")
        elif (
            attribute != attribute_name or attribute_name not in ALLOWED_ATTRIBUTES
        ) and not attribute_name.startswith("data-sd-"):
            report.error(
                f"attribute {attribute_name!r} on <{name}> is outside the authoring subset"
            )
        problem = value_problem(name, attribute_name, value)
        if problem:
            report.error(f"{attribute_name} on <{name}> {problem}")
        if attribute_name in NUMERIC_ATTRIBUTES and any(
            not abs(float(number.group())) <= MAX_NUMBER for number in SVG_NUMBER_RE.finditer(value)
        ):
            report.error(
                f"{attribute_name} on <{name}> has a number beyond ±{MAX_NUMBER:,}; draw at a smaller scale"
            )
        if attribute_name == "href" or re.search(r"url\s*\(", value, re.IGNORECASE):
            report.error(f"references are outside the portable subset on <{name}>")
        if ACTIVE_SCHEME_RE.search(value):
            report.error(f"embedded data or script URL in {attribute_name!r} on <{name}>")
        if attribute_name.startswith("data-sd-") and attribute_name not in {
            "data-sd-fill",
            "data-sd-stroke",
            PIN_ATTRIBUTE,
            OUTLINE_ATTRIBUTE,
            OUTLINE_OFFSETS_ATTRIBUTE,
        }:
            report.error(f"unknown SimpleDiagrams marking {attribute_name!r}")
        if attribute_name.startswith("data-sd-") and attribute != attribute_name:
            report.error(f"paint markings must be unqualified attributes on <{name}>")
        if attribute_name in {"fill", "stroke"} and not PAINT_RE.fullmatch(
            value.lower().strip()
        ):
            report.error(
                f"use none, black, white, or an explicit hex color for {attribute_name} on <{name}>"
            )

    for marking in ("data-sd-fill", "data-sd-stroke"):
        if marking not in element.attrib:
            continue
        value = element.attrib[marking]
        if name not in MARKING_CARRIERS:
            report.error(f"{marking} is not allowed on <{name}>")
        if value not in MARKING_VALUES:
            report.error(f"invalid {marking} value {value!r} on <{name}>")
        else:
            stats["markings"] += 1

    if name in {"title", "desc"}:
        # SimpleDiagrams ignores everything inside an annotation, so artwork
        # placed there would validate here and then never be drawn.
        if len(element):
            report.error(f"<{name}> may contain only text")
        return
    # SimpleDiagrams draws no text outside <title> and <desc>; it drops any with a warning.
    if (element.text or "").strip() or any((child.tail or "").strip() for child in element):
        report.error(f"text inside <{name}> is not drawn; put words in <title> or <desc>")

    paint_root = any(
        element.get(key) in LINKED_VALUES for key in ("data-sd-fill", "data-sd-stroke")
    )
    if paint_root:
        for channel in ("fill", "stroke"):
            if not element.get(channel, "").strip():
                report.error(
                    f"paint root <{name}> must declare {channel} explicitly (use none if unpainted); "
                    "a chip marking resets BOTH inherited paints"
                )

    fill, stroke = inherited_paint(element, inherited)
    fill_marking, stroke_marking = inherited_markings(element, markings)
    if name in DRAWABLES:
        stats["drawables"] += 1
        # SimpleDiagrams draws only what sits in <svg> or <g>; drawing inside a shape such
        # as a <path> is never drawn. A <title> or <desc> there is harmless.
        if any(local_name(child.tag) not in {"title", "desc"} for child in element):
            report.error(f"<{name}> may not contain other elements; put them beside it in a <g>")
        if fill is None or stroke is None:
            report.error(f"<{name}> must declare or inherit explicit fill AND stroke")
        if name == "path" and element.get("d", "").strip()[:1] not in {"M", "m", ""}:
            report.error("<path> d must start with a move command")
        paints_fill = name != "line" and fill != "none"
        paints_stroke = stroke not in {None, "none"}
        if paints_stroke:
            stats["stroked"] += 1
        if not paints_fill and not paints_stroke:
            report.warn(f"paintless <{name}> has no visible contribution")
        # Markings are optional per channel. In a marked file an unmarked
        # channel means `keep`: the part stays as drawn whatever the chips do.
        # That is legitimate for a fixed part, so this is a warning asking the
        # author to state that intent, not an error.
        if paints_fill and fill_marking is None:
            report.warn(
                f"painted fill on <{name}> has no data-sd-fill marking, so it keeps its "
                'authored color; write data-sd-fill="keep" if that is intended, or a chip value'
            )
        if paints_stroke and stroke_marking is None:
            report.warn(
                f"painted stroke on <{name}> has no data-sd-stroke marking, so it keeps its "
                'authored color and width; write data-sd-stroke="keep" if that is intended, or a chip value'
            )

    for child in element:
        walk(
            child,
            (fill, stroke),
            report,
            stats,
            depth + 1,
            (fill_marking, stroke_marking),
        )


def check_pins(
    element: ET.Element, report: Report, inside_pin: bool = False, depth: int = 0
) -> None:
    """A pin sits on a group or drawable, names one of nine spots, and never nests.

    Each pinned part has one size and one spot, so a pin inside another would have two.
    The root cannot be pinned: the whole shape is what the pinned parts sit in. Like
    `walk`, it stops at the nesting limit, which `walk` reports.
    """
    if depth >= MAX_DEPTH:
        return
    name = local_name(element.tag)
    value = element.attrib.get(PIN_ATTRIBUTE)
    if value is not None:
        if name == "svg":
            report.error(f"{PIN_ATTRIBUTE} is not allowed on the root <svg>")
        elif name not in MARKING_CARRIERS:
            report.error(f"{PIN_ATTRIBUTE} is not allowed on <{name}>")
        if value not in PIN_VALUES:
            report.error(
                f"invalid {PIN_ATTRIBUTE} value {value!r} on <{name}>; use one of "
                + ", ".join(sorted(PIN_VALUES))
            )
        if inside_pin:
            report.error(f"{PIN_ATTRIBUTE} on <{name}> is inside another pinned part")
    for child in element:
        check_pins(child, report, inside_pin or value is not None, depth + 1)


SVG_NUMBER_RE = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")


def svg_number(text: str | None) -> float | None:
    """A finite number spelt as SVG spells one, or None. Python's float() would also take
    'inf', 'nan' and '1_0', which the app refuses."""
    if text is None or not SVG_NUMBER_RE.fullmatch(text.strip()):
        return None
    number = float(text.strip())
    return number if math.isfinite(number) else None


def check_outlines(
    element: ET.Element,
    report: Report,
    inside_pin: bool = False,
    moved: bool = False,
    depth: int = 0,
) -> None:
    """A hand-drawn outline is an unmoved, unpinned <rect> with round corners.

    The app redraws the box from the rect's own numbers at every size, so a transform
    on it or around it, a pin, or corners with different x and y radii would be lost.
    Like `walk`, it stops at the nesting limit, which `walk` reports.
    """
    if depth >= MAX_DEPTH:
        return
    name = local_name(element.tag)
    value = element.attrib.get(OUTLINE_ATTRIBUTE)
    offsets = element.attrib.get(OUTLINE_OFFSETS_ATTRIBUTE)
    pinned = element.attrib.get(PIN_ATTRIBUTE) is not None
    moved = moved or element.attrib.get("transform") is not None
    if value is not None:
        if name != "rect":
            report.error(f"{OUTLINE_ATTRIBUTE} is allowed only on <rect>, not <{name}>")
        if value not in OUTLINE_VALUES:
            report.error(
                f"invalid {OUTLINE_ATTRIBUTE} value {value!r}; use "
                + ", ".join(sorted(OUTLINE_VALUES))
            )
        if inside_pin or pinned:
            report.error(f"{OUTLINE_ATTRIBUTE} cannot be pinned or inside a pinned part")
        if moved:
            report.error(f"{OUTLINE_ATTRIBUTE} cannot be moved by a transform")
        rx, ry = svg_number(element.attrib.get("rx")), svg_number(element.attrib.get("ry"))
        if rx is not None and ry is not None and rx != ry:
            report.error(f"{OUTLINE_ATTRIBUTE} needs round corners: rx and ry must agree")
    if offsets is not None:
        if value is None:
            report.error(f"{OUTLINE_OFFSETS_ATTRIBUTE} needs {OUTLINE_ATTRIBUTE} on the same <rect>")
        # Read as the app reads it: an SVG list of numbers, separated by spaces or commas.
        words = [word for word in re.split(r"[\s,]+", offsets.strip()) if word]
        numbers = [svg_number(word) for word in words]
        if (
            not 1 <= len(words) <= MAXIMUM_OUTLINE_OFFSETS
            or any(n is None or n < 0 for n in numbers)
            or any(a >= b for a, b in pairwise(numbers))
        ):
            report.error(
                f"invalid {OUTLINE_OFFSETS_ATTRIBUTE} {offsets!r}; list one to "
                f"{MAXIMUM_OUTLINE_OFFSETS} increasing distances, none negative"
            )
        else:
            # A copy further in than the corner radius would turn its corners inside out.
            radius = svg_number(element.attrib.get("rx")) or svg_number(element.attrib.get("ry")) or 0
            width = svg_number(element.attrib.get("width")) or 0
            height = svg_number(element.attrib.get("height")) or 0
            radius = min(radius, width / 2, height / 2)
            if numbers and numbers[-1] > radius:
                report.error(
                    f"{OUTLINE_OFFSETS_ATTRIBUTE} {offsets!r} reaches further in than the "
                    f"corner radius {radius:g}"
                )
    for child in element:
        check_outlines(child, report, inside_pin or pinned, moved, depth + 1)


def read_limited(path: Path, limit: int) -> bytes:
    """Reads at most `limit` + 1 bytes of a regular file.

    The file is opened without waiting, where the system allows, so a named pipe or a
    folder is refused at once instead of stalling the run.

    Raises:
        OSError: The file cannot be opened or read.
        ValueError: The path is not a regular file.
    """
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("not a regular file")
        stream = os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise
    with stream:
        return stream.read(limit + 1)


def validate(path: Path) -> Report:
    """Validate one SVG and return its report."""
    report = Report(path=path)
    try:
        payload = read_limited(path, MAX_SVG_BYTES)
    except OSError as error:
        report.error(f"cannot read file: {error}")
        return report
    except ValueError:
        report.error("not a regular file; give the path of an SVG file")
        return report
    if len(payload) > MAX_SVG_BYTES:
        report.error(f"SVG exceeds {MAX_SVG_BYTES:,} bytes; simplify the geometry")
        return report
    try:
        source = payload.decode("utf-8")
    except UnicodeDecodeError:
        report.error("SVG must be UTF-8 encoded")
        return report

    lowered = source.lower()
    # Raw-source checks. The parser must never meet a DTD or entity. The rest
    # SimpleDiagrams refuses wherever it appears in the file, comments and
    # annotations included, so prose that merely mentions it still fails import.
    for forbidden in (
        "<!doctype",
        "<!entity",
        "<?xml-stylesheet",
        "<![cdata[",
        "<script",
        "javascript:",
    ):
        if forbidden in lowered:
            report.error(f"unsafe or unsupported source token {forbidden!r}")
    if any(pattern.search(lowered) for pattern in EXTERNAL_REFERENCE_RES):
        report.error("unsafe or unsupported external reference in the source")
    if PREFIXED_TAG_RE.search(source):
        report.error("namespace-prefixed elements are unsupported; use unprefixed SVG tags")
    # Never parse a rejected DTD/entity declaration, even to accumulate diagnostics.
    if report.errors and any(token in lowered for token in ("<!doctype", "<!entity")):
        return report

    try:
        root = ET.fromstring(source)
    except ET.ParseError as error:
        report.error(f"invalid XML: {error}")
        return report

    if local_name(root.tag) != "svg":
        report.error("root element must be <svg>")
        return report
    if not root.tag.startswith(f"{{{SVG_NAMESPACE}}}"):
        report.error(f"root must declare xmlns={SVG_NAMESPACE!r}")
    if parse_view_box(root.attrib.get("viewBox")) is None:
        report.error("root requires a finite viewBox with width and height of at least 1")
    if not positive_length(root.attrib.get("width")):
        report.error("root requires a numeric width of at least 1")
    if not positive_length(root.attrib.get("height")):
        report.error("root requires a numeric height of at least 1")

    stats = {"elements": 0, "drawables": 0, "stroked": 0, "markings": 0}
    walk(root, (None, None), report, stats)
    check_pins(root, report)
    check_outlines(root, report)
    if stats["elements"] > MAX_ELEMENTS:
        report.error(f"SVG exceeds {MAX_ELEMENTS:,} elements; simplify the drawing")
    if stats["drawables"] == 0:
        report.error("SVG contains no supported drawable elements")
    if stats["stroked"] == 0:
        report.error(
            "SVG has no stroked drawable; a hand-drawn shape needs at least one real line or outline"
        )
    if stats["markings"] == 0:
        report.error("SVG has no data-sd-fill or data-sd-stroke markings")
    return report


def validate_or_report(path: Path) -> Report:
    """Validate one SVG, turning an unexpected failure into that file's error.

    The checks are bounded, so this should never be needed; if one still fails, that file
    fails with the reason and the files after it are still checked.
    """
    try:
        return validate(path)
    except Exception as failure:  # noqa: BLE001 - reported as this file's failure
        report = Report(path=path)
        report.error(f"could not be checked ({type(failure).__name__}): {failure}")
        return report


def printable(text: str) -> str:
    """`text` with control characters shown as escapes, so a file name or value cannot
    send the terminal a command such as one that sets the clipboard."""
    return "".join(
        f"\\u{ord(c):04x}" if unicodedata.category(c) in {"Cc", "Cf"} else c for c in text
    )


def print_report(report: Report, strict: bool = False) -> None:
    """Print one human-readable validation report."""
    status = "FAIL" if report.errors or (strict and report.warnings) else "PASS"
    print(printable(f"{status}: {report.path}"))
    for message in report.errors:
        print(printable(f"  ERROR: {message}"))
    for message in report.warnings:
        print(printable(f"  WARNING: {message}"))


def main(argv: Iterable[str] | None = None) -> int:
    """Run the command-line validator."""
    parser = argparse.ArgumentParser(
        description="Validate compatibility-first hand-drawn SVGs for SimpleDiagrams."
    )
    parser.add_argument("svg", nargs="+", type=Path, help="SVG file(s) to validate")
    parser.add_argument(
        "--strict", action="store_true", help="treat compatibility warnings as failures"
    )
    arguments = parser.parse_args(argv)

    reports = [validate_or_report(path) for path in arguments.svg]
    for report in reports:
        print_report(report, strict=arguments.strict)
    has_errors = any(report.errors for report in reports)
    has_strict_warnings = arguments.strict and any(
        report.warnings for report in reports
    )
    return 1 if has_errors or has_strict_warnings else 0


if __name__ == "__main__":
    raise SystemExit(main())
