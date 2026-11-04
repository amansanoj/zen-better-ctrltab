# Changelog

## Unreleased

- Check native profile locks instead of blocking on persistent lock files after
  Zen exits. Keep checked locks held during writes and clarify plan/error output.

- Review native CSS hooks, settings, installer safety and upstream licensing.
- Add profile INI discovery, conventional Flatpak/Snap paths, explicit change
  plans, confirmation, dry runs, profile listing and uninstall.
- Back up changed files with timestamps, write files atomically, preserve
  existing enabled state and unrelated mods, refuse locks and unsafe links.
- Preserve default styling and dropdowns while exposing CSS tweak variables,
  enforcing a readable minimum thumbnail width and adding accessibility media fallbacks.
- Add installer regression tests, preference validation, development-only
  Stylelint and Ubuntu/macOS/Windows CI checks.
- Document installation, recovery, troubleshooting and manual validation.

Live Zen appearance and hosted macOS/Windows execution remain unverified.
Upstream licensing requires clarification; no license has been invented.
