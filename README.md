# Create SimpleDiagrams hand-drawn SVGs

This Agent Skill teaches an AI agent to draw clean hand-drawn SVG shapes for SimpleDiagrams.

When SimpleDiagrams converts an SVG into an editable shape, it has to decide which parts follow the fill color, which follow the line color, and which keep the color they were drawn in. That isn't always obvious: an artist may draw a brush stroke as a filled area and still want it to take the line color. Two attributes, data-sd-fill and data-sd-stroke, let the SVG say so explicitly. Without them SimpleDiagrams makes a reasonable guess; with them the author decides.

The skill writes those attributes for you, along with the hand-drawn line style.

Requires SimpleDiagrams for macOS 5.0.7 or later. In 5.0.7 a converted shape arrives with a 2-point line; set its line weight to 1 to match the drawing. From 5.0.8 it arrives at 1.

## Install

Keep the folder name `simplediagrams-basic-shape-skill`. If you download a ZIP from GitHub, remove the branch suffix from the folder name.

- Claude Code: copy the folder into `~/.claude/skills/`, or `.claude/skills/` inside a project.
- Claude.ai: upload a zip of the folder, following Anthropic's [skill installation instructions](https://support.claude.com/en/articles/12512180-use-skills-in-claude).
- Codex: copy the folder to `$HOME/.agents/skills/`, or `.agents/skills/` inside a repository.
- Other agents: tell the agent to read `SKILL.md` and follow its references.

## Example requests

> Use the simplediagrams-basic-shape-skill skill to make a flat hand-drawn bicycle as an editable SimpleDiagrams SVG, and validate it.

- "Make three matching office plants."
- "Make these waves smaller and more frequent without changing the silhouette."
- "Redraw my reference as an isometric server with correct angles."
- "Make an outline-only mug with a transparent handle opening."

## Validate an SVG

Run these from the skill's folder.

```bash
python3 scripts/validate_svg.py path/to/shape.svg --strict
```

The validator needs Python 3.10+ and nothing else. It checks structure, paints and markings; it does not run the import. The real test is in SimpleDiagrams: drag the SVG onto a diagram, choose **Convert to Editable Shape**, then change the fill and line colors.

To run the validator's own tests:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

## License

[MIT](LICENSE), covering the skill, validator, tests and the two teaching SVGs. The license does not cover SimpleDiagrams itself or its stock shape libraries, and grants no rights in the SimpleDiagrams name or logo. The license covers the skill's own files, not the artwork you make with it; checking that you may use any reference you supply is up to you.
