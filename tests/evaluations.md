# Agent evaluations

Run each prompt in a fresh conversation with only this skill installed, once per agent or model being supported. Record the agent, date, validator result, visual inspection and real import result, and score each check pass, fail or not tested.

## Status

Checked on 2 October 2026 against SimpleDiagrams for macOS 5.0.8 (build 31):

- The contract was checked against the app's importer by reading it; no drag-and-drop import was performed.
- The validator's 28 tests pass, and both bundled SVGs and every recipe in the documentation pass `--strict`.
- None of the prompts below has been run yet. Add a dated line here for each agent and prompt as it is run, with its result.

## 1. New organic shape

"Use this skill to draw a hand-drawn potted cactus with two arms in a simple pot. Save cactus.svg. I want a flat shape I can recolor in SimpleDiagrams."

Check: an SVG file is delivered; recognizable cactus; subtle waviness on contours and inner lines; bodies carry fill and stroke on one drawable; no background plate; correct markings; passes `--strict`; preview supplied; the import test is reported honestly.

## 2. Isometric construction and revision

"Make an isometric two-bay server with three side vents, in the same pencil style. Then make the waves half as strong and more frequent without changing the box's corners or angles."

Check: axes at ±30°; equal vertical drops; shared faces reuse exact edge coordinates; vents follow the face axes; the revision halves displacement to about 0.12 and shortens the spacing, with corners and stroke width unchanged.

## 3. Matching set and a true hole

"Create matching flat SVGs of a mug, a desk lamp and a plant for a diagram. The mug handle hole must show the page behind it. Deliver separate SVG files at similar visual scale."

Check: three files; consistent line weight and wobble; the handle is a real opening, not a white patch; all pass `--strict` and read clearly as thumbnails.

## 4. Fixed accent

"Make an editable server whose light always stays red while I change the fill and line colors."

Check: the light is marked `data-sd-fill="keep"` with an explicit red fill; every chip-marked element declares both paints; the agent says the red is fixed, not a third editable color; no invented markings; states whether the behavior was tested in SimpleDiagrams.

## 5. Repairs

Each of these supplies an SVG and must be fixed without changing its geometry.

- A single closed white-filled path with `stroke="none"` and no markings: "This comes in solid black after Convert to Editable Shape. Make it a normal filled-and-outlined body." Check: identifies an unmarked single-color silhouette; adds a black stroke and both markings to the existing path.
- A child with a chip marking but no paints of its own, under a painted group: "This line turns into a filled black shape." Check: diagnoses a paint root; adds `fill="none"` and `stroke` on the marked element.
- A marked file whose inner line has no marking: "The outline changes with my line color but this inner line stays black. Why?" Check: identifies the unmarked channel as `keep`; adds `data-sd-stroke="stroke-chip"` with explicit paints.

## 6. Missing tools

"Use the skill to create an outline-only flower. Python and SimpleDiagrams are unavailable in this environment. Give me the SVG and tell me how to check it."

Check: SVG delivered; no fill or background; the agent names the checks it could not run and claims none of them.

## 7. Library starting colors

"I added your server shape to my library, but when I drag it out it ignores my current colors. Can you fix the SVG?"

Check: explains that the library's **Initial colors** setting, not the SVG, decides this; names where the setting is, Option-drag and **Apply Current Colors**; leaves correct markings alone; invents no metadata.

## Discovery

Without naming the skill: "Draw a hand-drawn router SVG for SimpleDiagrams" should select it. "Explain an SVG logo's accessibility" should not.
