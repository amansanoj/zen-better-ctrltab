# Development

Use Python 3.9+ for the standard-library installer and tests. Node 22+ and npm
are needed only for CSS linting, never to install or use the mod.

```sh
python3 -m unittest discover -s tests -v
python3 tests/check_preferences.py
python3 tests/dry_run.py
npm ci --ignore-scripts
npm run lint:css
```

The CI workflow runs Python checks on Ubuntu, macOS and Windows with Python
3.9, and Stylelint on Ubuntu. The preference checker covers this mod's dropdown
subset, fixed option/default values and CSS hook mapping; it does not emulate
Zen's settings UI.

## CSS hooks and tweaks

The first `#ctrlTab-panel` block documents tweak variables: `--bct-blur`
(default 0px), light/dark opacity, ring color, selection fill, radii, gap,
preview size/aspect ratio, minimum thumbnail width (96px), padding and badge size. Blur is opt-in and cannot
sample the web page behind the native popup. Reduced transparency removes it
and makes the surface opaque. Forced colors uses system surfaces and outlines.
No animations are introduced, so no reduced-motion override is necessary.

Keep `Better CtrlTab` as the display name: Zen's marker is
`#theme-Better-CtrlTab`. Dots in preference property names become hyphens in
attributes. The CSS comment maps all six favicon options and seven row limits.
The default overlap-right mode uses the base fallback values; title-left uses
the shared title-* rule. Do not add a seventh favicon mode merely to match a
miscount. Keep both current defaults and CSS-only operation.

Native IDs/classes, XUL image elements, popup parts, and Mozilla properties are
fragile. Static CSS lint cannot verify native layout, inheritance or focus.
Test in a real Zen build with all six favicon modes, row limits 1–7,
narrow windows, long titles, keyboard selection, light/dark themes, compact
mode, both tab orientations, forced colors and reduced transparency.

## Screenshots to take

Keep the original `before.jpg` / `after.jpg`; do not synthesize replacements.
After live testing, take these in a disposable profile, record Zen version/OS,
and add them below the current README Preview table:

- Matching light and dark default layouts (`screenshots/default-light.png`,
  `screenshots/default-dark.png`).
- A labeled contact sheet of all six favicon positions, including hidden
  (`screenshots/favicon-positions.png`); reference it after the Settings table.
- One-, five-, and seven-column settings with enough eligible tabs, plus a
  narrow window and an incomplete final row (`screenshots/rows.png`); reference
  it after the row-count explanation.
- Keyboard selection in forced colors and reduced transparency
  (`screenshots/accessibility.png`); reference it in Troubleshooting.

Those filenames are plans, not existing assets. Avoid broken image links until
real captures are committed.
