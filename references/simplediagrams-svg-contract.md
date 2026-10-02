# SimpleDiagrams SVG contract

What SimpleDiagrams for macOS does with an SVG on **Convert to Editable Shape**, and the subset this skill writes. It describes 5.0.8; 5.0.7 behaves the same except that a converted shape starts with line width 2, not 1.

## Color markings

An editable shape has two color controls: a fill chip and a line chip. `data-sd-fill` and `data-sd-stroke` say which chip each paint follows.

| Attribute | Value | Result |
|---|---|---|
| `data-sd-fill` | `fill-chip` | Fill takes the fill chip's color and texture. |
| `data-sd-fill` | `stroke-chip` | Fill takes the line chip's color and texture. For solid ink details. |
| `data-sd-fill` | `keep` | Fill stays as drawn. |
| `data-sd-stroke` | `stroke-chip` | Stroke takes the line chip's color and texture and the shape's line width (1 by default). |
| `data-sd-stroke` | `fill-chip` | Stroke takes the fill chip's color and texture; keeps its drawn width. |
| `data-sd-stroke` | `keep` | Stroke stays as drawn. |

- Values are exact and lower-case. Put them on a drawable or a `<g>`; a group's value is inherited, per channel, until a descendant overrides it.
- An unmarked channel means `keep`.
- Dash, cap and join stay as drawn. An Outline Pattern chosen in SimpleDiagrams replaces the dash of `stroke-chip` strokes.
- No stroke width scales when the shape is resized. The SVG is placed at its `width` × `height` in points, or its viewBox size without them (16 at least on each side, 480 × 360 at most). Drawing every stroke at width 1 therefore makes the SVG look the way it imports.
- A chip channel ignores the drawn `fill-opacity` / `stroke-opacity`; its opacity comes from the chip color. `keep` paint keeps them. `opacity` on an element or group is always honored.

If a file has any `data-sd-fill` or `data-sd-stroke` attribute, nothing is inferred. In such a file an invalid value (`Fill-chip`), a marking on an element other than a drawable or `<g>`, or any other `data-sd-*` attribute is dropped and the import sheet says it "cannot be converted and will be left out". The channel then takes the marking it inherits from a parent group, or stays as drawn if there is none. A file whose only marking is a typo therefore converts with every color fixed. Markings inside a left-out element, such as a `mask`, are discarded with it. The validator treats all of these as errors.

Conversion produces native paths. SVG groups, IDs and markup are not preserved, so keep the SVG for revisions.

## Paint roots

An element with its **own** chip marking on either channel discards both inherited paints: a missing fill becomes black and a missing stroke becomes `none`. Width, opacity, dash and transforms still inherit. Inherited markings and an own `keep` do not do this.

So every chip-marked element declares both paints itself:

```xml
<g fill="none" stroke="#000000" stroke-width="1"
   stroke-linecap="round" stroke-linejoin="round">
  <path d="M5 20 Q20 10 35 20" fill="none" stroke="#000000"
        data-sd-fill="keep" data-sd-stroke="stroke-chip"/>
</g>
```

Without the child's own paints, this line looks right in a browser and converts to a filled black shape.

Use `none` for an absent paint. A zero-width or transparent stroke is still a stroke and becomes visible once it takes the line chip's color and the shape's line width.

## Starting colors

The colors drawn on chip channels are only a preview; conversion discards them.

**On the canvas**, a converted shape starts with white fill, black line and line width 1, overlaid with any fill, line color or line width the person has chosen in the toolbar.

**In a library**, a shape starts from its default colors: white fill and black line, unless changed under **Edit Library… ▸** the shape **▸ Default Appearance ▸ Custom Default Paint**. The library's **Initial colors** setting (**Edit Library… ▸ Library Settings ▸ When a shape is placed**) then decides what a newly placed shape gets:

| Initial colors | Newly placed shape gets |
|---|---|
| **Let SimpleDiagrams decide** (the default) | Its default colors if they are chosen colors; the person's current colors if they are neutral (white or black fill, black or default grey line, no texture). |
| **Keep the shape's default fill and stroke colors** | Its default colors. |
| **Use currently selected fill and stroke colors** | The person's current fill, line color and line width. |

- Option-dragging a shape out of the library gives the other result for that shape.
- **Edit ▸ Apply Current Colors** (⌥⌘A) and **Edit ▸ Reset to Library Colors** (⌥⌘R) switch a placed shape either way.
- `keep` parts never change, under any setting or command.
- The setting is each person's preference on their Mac. It is not in the SVG or the library file and an author cannot lock it. Do not invent markings to control it.

## Authoring subset

- Drawables: `path`, `rect`, `circle`, `ellipse`, `polygon`, `polyline`, `line`. Also `g`, and `title` / `desc` for annotations.
- Attributes: geometry, `transform`, `fill`, `stroke`, `stroke-width`, `stroke-linecap`, `stroke-linejoin`, `stroke-miterlimit`, `stroke-dasharray`, `stroke-dashoffset`, `fill-rule`, `opacity`, `fill-opacity`, `stroke-opacity`, `id`, and the two markings. SimpleDiagrams leaves out most others, such as `role` or `paint-order`, with a warning.
- Colors are `none`, `black`, `white`, `#rgb` or `#rrggbb`.
- Root: SVG namespace, positive `width` and `height`, and a `viewBox` of four finite numbers with positive size. Keep every stroke inside the viewBox.
- UTF-8, at most 500,000 bytes.

Not used: `style`, `class`, `defs`, `symbol`, `use`, `clipPath`, `mask`, `filter`, `pattern`, gradients, `image`, `text`, `marker`, nested `svg`, scripts, event handlers, animation, `vector-effect`, and any `href` or `url()` reference. SimpleDiagrams accepts some of these, drops others with a warning, and refuses the conversion for others; direct geometry avoids all three outcomes.

## Unmarked files

For diagnosing an SVG with no markings. Its channels are inferred, and every drawn color is replaced:

- Every stroke follows the line chip.
- A fill on a drawable that also has a stroke follows the fill chip.
- A fill-only drawable follows the line chip if it is dark and the fill chip if it is light. The dividing point is midway between the darkest and lightest tone in the file, taking each drawable's stroke color if it has one, otherwise its fill.
- If those tones span less than `0.05`, every fill-only drawable follows the line chip.
- A single-color silhouette (no strokes anywhere, every fill the same color) follows the fill chip and starts black unless a toolbar fill is chosen.

A marked file that cannot be compiled falls back to these rules without notice.

## Failure patterns

| Symptom | Cause | Fix |
|---|---|---|
| Shape is solid black, or everything follows one chip | No markings: a silhouette, or fill-only parts sorted to the line chip | Put white fill and black outline on one closed drawable and mark both channels |
| Chips change nothing | The file's only markings are invalid | Correct spelling and placement |
| One part follows the wrong chip or none | Its channel is unmarked, or its own marking was dropped and it fell back to its group's | Mark it, with explicit paints; if it is meant to be fixed, write `keep` |
| Fill and line colors change together | Both channels carry the same marking, or ink geometry is marked as a body | Bodies `fill-chip` / `stroke-chip`; ink fills `stroke-chip` / `keep` |
| A line becomes a filled black shape | Paint root without its own paints | Add `fill="none"` and `stroke` on the marked element |
| A detail vanishes after recoloring | It is a fill following the fill chip, or white `keep` paint | Draw it as a black stroke marked `stroke-chip` |
| A translucent part becomes opaque | Chip channels ignore `fill-opacity` / `stroke-opacity` | Use `opacity` on the element or group |
| Lines are thicker or thinner than drawn | `stroke-chip` strokes take the shape's line width | Change the line width in SimpleDiagrams, or mark the stroke `keep` |
| "…cannot be converted and will be left out" | Filter, mask, pattern, gradient, image, text, marker, or `vector-effect` | Redraw it as paths |
| **Convert to Editable Shape** is unavailable | Unsupported color syntax such as `hsl()` or most named colors, a non-numeric width or opacity, nested `svg`, CSS beyond class selectors, CDATA, or the text `<script` or `javascript:` anywhere in the file, comments included | Use hex colors and direct geometry |
| A library shape arrives in unexpected colors | The library's **Initial colors** setting | See Starting colors; this is not an SVG fault |
| Cracks or thick seams when resized | Adjacent faces have nearly matching edges | Reuse one edge's exact coordinates |

## Import test

1. Drag the SVG onto a diagram and choose **Convert to Editable Shape**.
2. Set a conspicuous fill color and a different line color. Bodies follow fill, outlines and details follow line, `keep` parts stay as drawn.
3. Resize larger and smaller. Check seams, strokes and readability.
4. Set the fill transparent or textured. Look for background plates and overlaps that a solid fill hides.

The validator checks structure, paints and markings only. It does not parse path data, render, or run the conversion, so a validator pass is not an import pass.
