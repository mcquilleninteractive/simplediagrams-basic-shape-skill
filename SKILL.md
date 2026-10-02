---
name: simplediagrams-basic-shape-skill
description: Creates and revises hand-drawn SVG shapes for SimpleDiagrams, with the data-sd-fill / data-sd-stroke color markings used by Convert to Editable Shape. Use for flat or isometric shapes, matching sets, reference redraws, and fill or line-color repairs.
license: MIT
---

# Create SimpleDiagrams hand-drawn SVGs

Deliver SVG files that SimpleDiagrams for macOS (5.0.7 or later) turns into editable shapes through **Convert to Editable Shape**, with fills and outlines that follow the diagram's fill and line colors. The same file works dropped on the canvas or added to a library.

## References

- [references/simplediagrams-svg-contract.md](references/simplediagrams-svg-contract.md): color markings, paint roots, starting colors and library settings, unmarked files, failure patterns. Read before writing or repairing markings.
- [references/hand-drawn-geometry.md](references/hand-drawn-geometry.md): line construction, isometric projection, visual check. Read before drawing or changing linework.
- [references/request-patterns.md](references/request-patterns.md): reference redraws, revisions, sets, fixed accents, cutouts, labels.
- [assets/shape-template.svg](assets/shape-template.svg) is the structural starting point; [assets/example-potted-plant.svg](assets/example-potted-plant.svg) is a complete example.

Never present output as legally cleared, and do not trace or adapt SimpleDiagrams stock shapes or third-party artwork for redistribution. A substantial copy of a bundled asset keeps its MIT notice.

## Workflow

1. Settle the subject, view, placed size and details. Defaults: one shape per SVG, transparent background, white fills, black strokes of width 1, subtly wavy lines. Save where asked, otherwise in `output/`. Ask only when a missing choice changes the result materially.
2. Build clean baseline geometry. For isometric work, fix the projection and shared edges first.
3. Give every part one of the paint recipes below.
4. Add the hand-drawn character in the path coordinates.
5. Validate, and again after every edit. The script is in this skill's directory and needs Python 3.10+:

   ```bash
   python3 scripts/validate_svg.py path/to/shape.svg --strict
   ```

6. Render at placed size, about 2×, and thumbnail size, and run the visual check in the geometry reference.
7. If SimpleDiagrams is available, run the import test in the contract.
8. Deliver the SVG, a preview if one was rendered, and a statement of which checks were actually performed: validator, visual, real import. If a tool was unavailable, deliver anyway and name the unperformed check; for example, "Validator passed; preview inspected; import not tested."

## Rules

- Root `<svg>`: SVG namespace, positive `width` and `height`, matching `viewBox`.
- Only `path`, `rect`, `circle`, `ellipse`, `polygon`, `polyline`, `line` and `g`, plus `title` / `desc`. No CSS, references, clipping, masks, filters, gradients, patterns, images, text, scripts or `vector-effect`.
- Colors are `none`, `black`, `white` or hex.
- Every drawable has an explicit `fill` and `stroke`, its own or inherited. An absent paint is `none`, never zero width or transparent.
- Every painted channel carries a `data-sd-fill` / `data-sd-stroke` marking. Write `keep` on fixed parts.
- An element with a chip marking declares both `fill` and `stroke` itself. It is a paint root and inherits neither.
- A body's fill and outline are on the same closed drawable: `fill="#ffffff"`, `stroke="#000000"`. No fill-only face under a separate outline.
- `stroke-width="1"`, round caps and round joins on every stroke, and at least one stroked drawable per file.
- Faces that share an edge use identical coordinates for it.
- Transparent background. No canvas-sized rectangle.
- Waviness lives in path coordinates and never changes an edge's average direction or endpoints.

## Paint recipes

Body, following the fill and line colors:

```xml
<g data-sd-fill="fill-chip" data-sd-stroke="stroke-chip"
   fill="#ffffff" stroke="#000000" stroke-width="1"
   stroke-linecap="round" stroke-linejoin="round">
  <path d="...Z"/>
</g>
```

Open line, following the line color:

```xml
<g data-sd-fill="keep" data-sd-stroke="stroke-chip"
   fill="none" stroke="#000000" stroke-width="1"
   stroke-linecap="round" stroke-linejoin="round">
  <path d="..."/>
</g>
```

Solid ink detail such as a dot, following the line color:

```xml
<g data-sd-fill="stroke-chip" data-sd-stroke="keep"
   fill="#000000" stroke="none">
  <path d="...Z"/>
</g>
```

Fixed accent. The color stays as drawn; it is not a third editable color, so say so when a user asks for one:

```xml
<path d="...Z" data-sd-fill="keep" data-sd-stroke="stroke-chip"
      fill="#f2a900" stroke="#000000" stroke-width="1"
      stroke-linecap="round" stroke-linejoin="round"/>
```

If SimpleDiagrams behaves differently from the contract, keep the artwork, report what was observed, and trust the real import.
