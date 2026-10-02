# Hand-drawn geometry

The target is a clean illustration drawn by a confident hand: not a rough.js sketch, a noisy trace, or a distorted object. Build correct geometry first, then add small, frequent imperfections. The eye should read the intended line before it notices the wobble.

## Pencil-line construction

For each baseline edge or curve:

1. Keep endpoints and true corners fixed.
2. Sample the baseline at short, fairly even intervals.
3. Move each interior sample a small distance along the local normal.
4. Vary magnitude and side irregularly. Include near-zero offsets and occasional consecutive samples on the same side; strict alternation at uniform spacing looks mechanical.
5. Fit smooth quadratic or cubic curves through the displaced samples (Catmull–Rom to cubic works well). Keep designed corners sharp.

Standard values:

| | Value |
|---|---|
| ViewBox, shorter side | 64–100 units |
| Stroke width | 1 |
| Maximum normal displacement | 0.3 |
| Sample spacing | 3 |

SimpleDiagrams draws lines at width 1 by default at any shape size, and places the SVG at one unit per point, so these values make the SVG look the way it imports. They are fixed, not proportional to the viewBox. Leave margin for the stroke, keep parts at least 2 units apart, and drop details that would clog at placed size.

The bundled potted-plant example uses exactly these values. If the silhouette scallops or looks lumpy, reduce displacement and break up the rhythm; short curves and small rigid objects may need 0.2.

Use a fixed irregular sequence, not random noise, so revisions are repeatable:

```text
+0.52, -0.12, -0.39, +0.08, +0.46, -0.33, +0.04, -0.55
```

**Amplitude** is the maximum displacement of a sample from the baseline. For amplitude `A`, divide each value by the largest magnitude (`0.55`) and multiply by `A`. "Half amplitude" halves these offsets, not the stroke width or the shape. Smoothing can overshoot, so inspect the curves, not only the samples. Start neighboring lines at different points in the sequence.

## Flat organic shapes

- Give each long contour several shallow deviations, not one broad bend. Short curves need fewer.
- Draw internal veins, stems, rims and decoration with the same line character as the outline.
- Paired parts may be related but should not be mirrored clones.

## Straight-edged and isometric shapes

- An edge's average direction stays correct; the wobble crosses the baseline repeatedly with a mean of zero.
- Adjacent faces share one edge: generate it once and reuse the exact coordinates.
- Do not round a designed corner to make a path smooth.

For a conventional 30° isometric projection, use basis vectors proportional to:

```text
right-down: (dx,  dx × tan 30°)
right-up:   (dx, -dx × tan 30°)
vertical:   (0, height)
```

A top face `A → B → C → D` is a parallelogram: `D = A + C - B`. Drop every visible corner of a prism by the same height, so bottom edges stay parallel to top edges. Perturb only after this construction is correct.

## Avoid

- One or two large bows along an edge, or perfectly straight CAD lines
- Sawtooth, polygonal jitter, or uniform sine waves
- Random noise that changes on every run
- Double-stroked sketch lines, unless requested
- Filters or displacement effects
- Perspective errors passed off as hand-drawn character
- A wavy silhouette around mechanical internal lines

## Visual check

Render on a plain light background at the expected placed size, at about 2×, and at thumbnail size.

- The subject is recognizable at once, and small details do not clog the thumbnail.
- The wobble is visible at placed size and the line still looks continuous and confident at 2×.
- No edge looks melted, scalloped, or polygonal.
- Parallel, vertical, circular and isometric relationships hold.
- Fill and outline meet cleanly at every shared seam.

If the wobble cannot be seen, increase displacement, not stroke width. If the object looks warped, restore the baseline and reduce displacement, not the number of deviations.
