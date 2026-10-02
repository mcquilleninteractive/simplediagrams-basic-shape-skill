"""Exercise the portable SVG preflight without treating it as a native compiler.

Run from any directory with:
    python3 -m unittest discover -s /path/to/skill/tests -v

All generated inputs live in temporary directories; no third-party modules or
installed SimpleDiagrams application are required.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL_DIRECTORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = SKILL_DIRECTORY / "scripts" / "validate_svg.py"
SPEC = importlib.util.spec_from_file_location(
    "simplediagrams_svg_validator", VALIDATOR_PATH
)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)

BODY = (
    '<path data-sd-fill="fill-chip" data-sd-stroke="stroke-chip" '
    'fill="#ffffff" stroke="#000000" stroke-width="0.9" '
    'd="M10 10 L70 10 L70 70 L10 70Z"/>'
)


def svg(body: str = BODY, attributes: str = "") -> str:
    """Wrap a test drawing in valid portable dimensions and namespace."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="80" height="80" viewBox="0 0 80 80" {attributes}>'
        f"{body}</svg>"
    )


class ValidateSvgTests(unittest.TestCase):
    """Cover authoring regressions, unsafe input, and truthful CLI reporting."""

    def setUp(self) -> None:
        """Isolate every test's generated source and CLI inputs."""
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)

    def write(self, source: str | bytes, name: str = "shape.svg") -> Path:
        """Create a temporary fixture without modifying bundled artwork."""
        path = self.directory / name
        path.write_bytes(source.encode("utf-8") if isinstance(source, str) else source)
        return path

    def test_bundled_assets_pass_without_warnings(self) -> None:
        """The shipped template and visual example must remain usable masters."""
        assets = sorted((SKILL_DIRECTORY / "assets").glob("*.svg"))
        self.assertGreaterEqual(len(assets), 2)
        for path in assets:
            with self.subTest(asset=path.name):
                report = validator.validate(path)
                self.assertEqual(report.errors, [])
                self.assertEqual(report.warnings, [])

    def test_chip_markings_require_both_local_paints(self) -> None:
        """A paint root resets both channels even when its parent paints them."""
        for carrier in ("g", "path"):
            for marking in ("data-sd-fill", "data-sd-stroke"):
                for missing_channel in ("fill", "stroke"):
                    with self.subTest(
                        carrier=carrier, marking=marking, missing=missing_channel
                    ):
                        paint = (
                            'stroke="#000000"'
                            if missing_channel == "fill"
                            else 'fill="#ffffff"'
                        )
                        geometry = (
                            ' d="M10 10 L70 10 L70 70Z"' if carrier == "path" else ""
                        )
                        child = (
                            '<path d="M10 10 L70 10 L70 70Z"/>'
                            if carrier == "g"
                            else ""
                        )
                        content = (
                            '<g fill="#ffffff" stroke="#000000">'
                            f'<{carrier} {marking}="stroke-chip" {paint}{geometry}>'
                            f"{child}</{carrier}></g>"
                        )
                        report = validator.validate(self.write(svg(content)))
                        self.assertTrue(
                            any(
                                f"must declare {missing_channel} explicitly" in error
                                for error in report.errors
                            ),
                            report.errors,
                        )

    def test_children_inherit_paint_from_marked_group(self) -> None:
        """Ordinary children need not repeat an intentional group's paints."""
        content = (
            '<g data-sd-fill="fill-chip" data-sd-stroke="stroke-chip" '
            'fill="#ffffff" stroke="#000000"><path d="M10 10 L70 10 L70 70Z"/></g>'
        )
        report = validator.validate(self.write(svg(content)))
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_keep_only_markings_do_not_reset_inherited_paint(self) -> None:
        """Keep is safe with inherited paint and must not create a paint root."""
        content = (
            '<g fill="#ffffff" stroke="#000000">'
            '<path data-sd-fill="keep" data-sd-stroke="keep" '
            'd="M10 10 L70 10 L70 70Z"/></g>'
        )
        report = validator.validate(self.write(svg(content)))
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_css_and_import_rules_are_rejected(self) -> None:
        """CSS is outside the explicit-paint portable authoring subset."""
        cases = (
            svg(BODY, 'style="fill: black"'),
            svg(BODY, 'class="body"'),
            svg('<style>@import "https://example.invalid/shape.css";</style>' + BODY),
            svg('<style>@IMPORT "local.css";</style>' + BODY),
        )
        for source in cases:
            with self.subTest(source=source):
                self.assertTrue(validator.validate(self.write(source)).errors)

    def test_entities_are_rejected_before_xml_parsing(self) -> None:
        """Untrusted DTD/entity input must never reach either XML parser API."""
        for declaration in (
            '<!DOCTYPE svg [<!ENTITY value "expanded">]>',
            '<!ENTITY value SYSTEM "file:///etc/passwd">',
            '<!DOCTYPE svg SYSTEM "https://example.invalid/shape.dtd">',
        ):
            with self.subTest(declaration=declaration):
                path = self.write(declaration + svg())
                with (
                    mock.patch.object(validator.ET, "parse") as parse,
                    mock.patch.object(validator.ET, "fromstring") as fromstring,
                ):
                    report = validator.validate(path)
                parse.assert_not_called()
                fromstring.assert_not_called()
                self.assertTrue(report.errors)

    def test_foreign_namespaces_and_nested_svg_are_rejected(self) -> None:
        """Local tag names alone cannot admit foreign or nested SVG content."""
        cases = (
            svg('<path xmlns="urn:foreign" d="M1 1 L2 2"/>' + BODY),
            svg('<path xmlns="" d="M1 1 L2 2"/>' + BODY),
            svg('<svg width="80" height="80" viewBox="0 0 80 80">' + BODY + "</svg>"),
        )
        for source in cases:
            with self.subTest(source=source):
                self.assertTrue(validator.validate(self.write(source)).errors)

    def test_invalid_utf8_is_reported_without_crashing(self) -> None:
        """An unreadable encoding should produce an actionable validation error."""
        report = validator.validate(self.write(svg().encode("utf-8") + b"\xff"))
        self.assertIn("SVG must be UTF-8 encoded", report.errors)

    def test_shared_authoring_budget_counts_bytes_and_includes_boundary(self) -> None:
        """Enforce the 500,000-byte authoring budget exactly at its boundary."""
        self.assertEqual(validator.MAX_SVG_BYTES, 500_000)
        source = svg("<title>Plante en pot — été</title>" + BODY).encode("utf-8")
        exact = source + b" " * (validator.MAX_SVG_BYTES - len(source))
        report = validator.validate(self.write(exact))
        self.assertEqual(report.errors, [])
        report = validator.validate(self.write(exact + b" "))
        self.assertTrue(
            any("exceeds 500,000 bytes" in error for error in report.errors)
        )

    def test_desktop_filename_can_contain_spaces_and_uppercase(self) -> None:
        """Any filename the user chooses is valid; only the content is checked."""
        report = validator.validate(self.write(svg(), "My Potted Plant.svg"))
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_unmarked_painted_channel_in_marked_file_warns(self) -> None:
        """Desktop reads valid markings, so an unmarked painted channel silently keeps its color."""
        report = validator.validate(
            self.write(
                svg(BODY + '<circle fill="white" stroke="none" cx="40" cy="40" r="4"/>')
            )
        )
        self.assertEqual(report.errors, [])
        self.assertEqual(len(report.warnings), 1)
        self.assertIn("no data-sd-fill marking", report.warnings[0])
        report = validator.validate(
            self.write(
                svg(
                    '<g data-sd-fill="fill-chip" fill="#ffffff" stroke="#000000">'
                    '<path d="M10 10 L70 10 L70 70Z"/></g>'
                )
            )
        )
        self.assertEqual(report.errors, [])
        self.assertEqual(len(report.warnings), 1)
        self.assertIn("no data-sd-stroke marking", report.warnings[0])

    def test_light_fill_beside_dark_stroke_passes_strict_cli(self) -> None:
        """A marked light fill-only detail is accepted; dark strokes supply tone contrast."""
        path = self.write(
            svg(
                BODY + '<circle data-sd-fill="fill-chip" data-sd-stroke="keep" '
                'fill="white" stroke="none" cx="40" cy="40" r="4"/>'
            )
        )
        report = validator.validate(path)
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])
        result = subprocess.run(
            [sys.executable, str(VALIDATOR_PATH), str(path), "--strict"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("PASS:"), result.stdout)

    def test_strict_cli_warning_reports_failure_and_nonzero_exit(self) -> None:
        """Invisible geometry still produces a warning and fails strict QA."""
        path = self.write(
            svg(BODY + '<circle fill="none" stroke="none" cx="40" cy="40" r="4"/>')
        )
        report = validator.validate(path)
        self.assertEqual(report.errors, [])
        self.assertTrue(report.warnings)
        for strict in (False, True):
            with self.subTest(strict=strict):
                command = [sys.executable, str(VALIDATOR_PATH), str(path)]
                if strict:
                    command.append("--strict")
                result = subprocess.run(
                    command, capture_output=True, text=True, check=False
                )
                self.assertEqual(result.returncode, 1 if strict else 0, result.stderr)
                self.assertTrue(
                    result.stdout.startswith("FAIL:" if strict else "PASS:")
                )
                self.assertIn("WARNING:", result.stdout)

    def test_strokeless_art_remains_outside_authoring_subset(self) -> None:
        """A hand-drawn shape needs at least one real line or outline."""
        content = BODY.replace('stroke="#000000"', 'stroke="none"')
        report = validator.validate(self.write(svg(content)))
        self.assertTrue(any("no stroked drawable" in error for error in report.errors))

    def test_active_svg_content_is_rejected(self) -> None:
        """Executable and resource-loading SVG constructs must fail preflight."""
        cases = (
            svg("<script>alert(1)</script>" + BODY),
            svg(
                '<foreignObject><div xmlns="http://www.w3.org/1999/xhtml"/></foreignObject>'
                + BODY
            ),
            svg('<image href="data:image/png;base64,AAAA"/>' + BODY),
            svg('<animate attributeName="fill" values="red;blue"/>' + BODY),
            svg(BODY, 'onload="alert(1)"'),
            svg(BODY, 'onmouseover="alert(1)"'),
            svg(BODY, 'xmlns:x="urn:foreign" x:onload="alert(1)"'),
            svg(BODY, 'href="&#104;ttps://example.invalid/image.svg"'),
            '<?xml-stylesheet href="https://example.invalid/style.css"?>' + svg(),
        )
        for source in cases:
            with self.subTest(source=source):
                self.assertTrue(validator.validate(self.write(source)).errors)

    def test_prose_in_title_desc_and_comments_is_not_active_content(self) -> None:
        """Human annotations may mention data without failing preflight.

        The skill permits <title> and <desc>, so a raw-text scan that mistook
        "metadata:" for a data URL would send an agent chasing a fault that
        does not exist.
        """
        cases = (
            "<title>Server metadata: rack unit</title>",
            "<desc>Indicator data: none</desc>",
            "<!-- no foreignObject or @import here -->",
        )
        for annotation in cases:
            with self.subTest(annotation=annotation):
                report = validator.validate(self.write(svg(annotation + BODY)))
                self.assertEqual(report.errors, [])

    def test_text_the_app_refuses_anywhere_fails_even_in_annotations(self) -> None:
        """SimpleDiagrams scans the whole source, so harmless-looking prose matters.

        A comment that says "<script" or a CDATA section disables Convert to
        Editable Shape, and passing it here would promise an import that fails.
        """
        cases = (
            "<!-- no <script> here -->",
            "<desc><![CDATA[plain text]]></desc>",
            "<desc>not a javascript: link</desc>",
        )
        for annotation in cases:
            with self.subTest(annotation=annotation):
                report = validator.validate(self.write(svg(annotation + BODY)))
                self.assertTrue(
                    any("unsafe or unsupported" in e for e in report.errors),
                    report.errors,
                )

    def test_attributes_outside_the_subset_are_rejected(self) -> None:
        """The app leaves unknown attributes out with a warning; catch them first."""
        for attributes in (
            'role="img"',
            'paint-order="stroke"',
            'display="none"',
            'xml:space="preserve"',
        ):
            with self.subTest(attributes=attributes):
                report = validator.validate(self.write(svg(BODY, attributes)))
                self.assertTrue(
                    any("outside the authoring subset" in e for e in report.errors),
                    report.errors,
                )

    def test_widths_and_opacities_must_be_usable_numbers(self) -> None:
        """A non-numeric value disables conversion; zero hides paint the chips reveal."""
        for attributes in (
            'stroke-width="abc"',
            'stroke-width="0"',
            'opacity="2"',
            'stroke-opacity="0"',
        ):
            with self.subTest(attributes=attributes):
                report = validator.validate(self.write(svg(BODY + f"<g {attributes}/>")))
                self.assertTrue(
                    any("must be a" in e for e in report.errors), report.errors
                )

    def test_data_and_script_urls_in_attributes_are_rejected(self) -> None:
        """A resource or script scheme in any attribute value must still fail."""
        for attributes in (
            'data-note="data:image/png;base64,AAAA"',
            'data-note=" JavaScript:alert(1)"',
            'data-note="see (data :text/plain,x)"',
        ):
            with self.subTest(attributes=attributes):
                report = validator.validate(self.write(svg(BODY + f"<g {attributes}/>")))
                self.assertTrue(
                    any("embedded data or script URL" in e for e in report.errors),
                    report.errors,
                )

    def test_values_the_app_cannot_read_are_rejected(self) -> None:
        """An unreadable number or keyword disables conversion, so it must not pass.

        Path data is deliberately not parsed; these are the plain numeric and
        enumerated attributes, where a wrong value is cheap to catch.
        """
        cases = (
            '<g stroke-width="1e309"/>',
            '<g stroke-linecap="banana"/>',
            '<g stroke-linejoin="pointy"/>',
            '<g fill-rule="odd"/>',
            '<g stroke-dasharray="2 x"/>',
            '<g stroke-dasharray="-1 2"/>',
            '<g transform="spin(45)"/>',
            '<g transform="translate(1e999 0)"/>',
            '<g stroke-miterlimit="0"/>',
            '<circle cx="5" cy="5" fill="none" stroke="#000000" data-sd-stroke="stroke-chip" data-sd-fill="keep"/>',
            '<circle r="-1" fill="none" stroke="#000000" data-sd-stroke="stroke-chip" data-sd-fill="keep"/>',
            '<rect width="0" height="5" fill="none" stroke="#000000" data-sd-stroke="stroke-chip" data-sd-fill="keep"/>',
            '<polygon points="1 2 3" fill="none" stroke="#000000" data-sd-stroke="stroke-chip" data-sd-fill="keep"/>',
            '<path d="L1 1" fill="none" stroke="#000000" data-sd-stroke="stroke-chip" data-sd-fill="keep"/>',
        )
        for extra in cases:
            with self.subTest(extra=extra):
                self.assertTrue(validator.validate(self.write(svg(BODY + extra))).errors)

    def test_readable_values_still_pass(self) -> None:
        """The stricter value checks must not reject ordinary, valid drawings."""
        extra = (
            '<g transform="translate(2, 3) rotate(-15 4 4) scale(1.5)" stroke-dasharray="2 1.5" '
            'stroke-linecap="round" stroke-linejoin="bevel" stroke-miterlimit="4" opacity="0.5">'
            '<circle cx="5" cy="5" r="2" fill="none" stroke="#000000" stroke-width="1" '
            'data-sd-fill="keep" data-sd-stroke="stroke-chip"/>'
            '<path d="M1 1 L9 9 M2 2 L8 2 L8 8 Z" fill-rule="evenodd" fill="#ffffff" stroke="#000000" '
            'data-sd-fill="fill-chip" data-sd-stroke="stroke-chip"/></g>'
        )
        self.assertEqual(validator.validate(self.write(svg(BODY + extra))).errors, [])

    def test_structure_the_app_would_not_draw_is_rejected(self) -> None:
        """A file must not pass when its artwork is ignored or refused on import."""
        hidden = svg("<title>" + BODY + "</title>")
        prefixed = (
            '<svg:svg xmlns:svg="http://www.w3.org/2000/svg" width="80" height="80" '
            'viewBox="0 0 80 80">'
            + BODY.replace("<path", "<svg:path")
            + "</svg:svg>"
        )
        commented = svg('<!-- see href="https://example.invalid/a.svg" -->' + BODY)
        for name, source in (("hidden", hidden), ("prefixed", prefixed), ("commented", commented)):
            with self.subTest(case=name):
                self.assertTrue(validator.validate(self.write(source)).errors)

    def test_element_count_limit_matches_the_app(self) -> None:
        """SimpleDiagrams refuses more than 50,000 elements; stay inside it."""
        with mock.patch.object(validator, "MAX_ELEMENTS", 3):
            report = validator.validate(self.write(svg(BODY + "<g/><g/><g/>")))
        self.assertTrue(any("elements" in error for error in report.errors))

    def test_local_and_remote_references_are_rejected_anywhere(self) -> None:
        """A local URL must not hide a later remote URL from reference checks."""
        cases = (
            'fill="url(#local)"',
            'fill="url(https://example.invalid/paint.svg)"',
            'fill="url(#local) url(https://example.invalid/paint.svg)"',
            'data-note="URL (#local) url(https://example.invalid/paint.svg)"',
            'href="#local"',
            'href="https://example.invalid/shape.svg"',
            'xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="#local"',
        )
        for attributes in cases:
            with self.subTest(attributes=attributes):
                report = validator.validate(
                    self.write(svg(BODY + f"<g {attributes}/>"))
                )
                self.assertTrue(
                    any("references are outside" in error for error in report.errors),
                    report.errors,
                )

    def test_invalid_unknown_and_qualified_markings_fail(self) -> None:
        """Only canonical unqualified metadata may describe paint channels."""
        cases = (
            '<g data-sd-fill="Fill-Chip"/>',
            '<g data-sd-fill=""/>',
            '<g data-sd-color="stroke-chip"/>',
            '<g xmlns:sd="urn:sd" sd:data-sd-fill="fill-chip"/>',
            '<title data-sd-fill="keep">Invalid carrier</title>',
        )
        for content in cases:
            with self.subTest(content=content):
                self.assertTrue(
                    validator.validate(self.write(svg(BODY + content))).errors
                )

    def test_absent_markings_fail(self) -> None:
        """Visually valid SVG is not sufficient without shared paint metadata."""
        content = '<path fill="white" stroke="black" d="M10 10 L70 10 L70 70Z"/>'
        report = validator.validate(self.write(svg(content)))
        self.assertIn(
            "SVG has no data-sd-fill or data-sd-stroke markings", report.errors
        )

    def test_missing_effective_paint_fails(self) -> None:
        """Browser default paints must not conceal an unspecified channel."""
        for paint in ('fill="white"', 'stroke="black"', ""):
            with self.subTest(paint=paint):
                content = (
                    f'<path data-sd-fill="keep" {paint} d="M10 10 L70 10 L70 70Z"/>'
                )
                report = validator.validate(self.write(svg(content)))
                self.assertTrue(
                    any("explicit fill AND stroke" in error for error in report.errors)
                )


if __name__ == "__main__":
    unittest.main()
