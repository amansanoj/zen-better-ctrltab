"""Install the bundled Better CtrlTab mod into a Zen profile."""
import argparse
import json
import shutil
import sys
from pathlib import Path

MOD_ID = "43e5b1ae-d1b5-4d38-a1ea-15a7c7de328f"
SOURCE = Path(__file__).resolve().parent


def find_profile():
    roots = [
        Path.home() / "Library/Application Support/zen/Profiles",
        Path.home() / ".zen",
        Path.home() / ".var/app/app.zen_browser.zen/.zen",
        Path.home() / "AppData/Roaming/zen/Profiles",
    ]
    profiles = sorted({
        path for root in roots if root.is_dir()
        for path in root.iterdir() if (path / "prefs.js").is_file()
    })
    if len(profiles) == 1:
        return profiles[0]
    listing = "\n".join(str(path) for path in profiles)
    raise SystemExit(
        "Open about:support in Zen, find Profile Folder, quit Zen, and rerun "
        'with --profile "/path/to/profile".' + (f"\n\nProfiles found:\n{listing}" if listing else "")
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, help="Zen profile folder from about:support")
    args = parser.parse_args()
    profile = args.profile.expanduser().resolve() if args.profile else find_profile()
    if not (profile / "prefs.js").is_file():
        raise SystemExit(f"Not a Zen profile folder: {profile}")
    registry = profile / "zen-themes.json"
    mods = json.loads(registry.read_text(encoding="utf-8")) if registry.exists() else {}
    if not isinstance(mods, dict):
        raise SystemExit("Unexpected Zen Mods registry format.")
    for name in ("chrome.css", "preferences.json", "README.md"):
        if not (SOURCE / name).is_file():
            raise SystemExit(f"Missing bundled file: {name}")

    folder = profile / "chrome" / "zen-themes" / MOD_ID
    folder.mkdir(parents=True, exist_ok=True)
    for source, target in (("chrome.css", "chrome.css"), ("preferences.json", "preferences.json"),
                           ("README.md", "readme.md")):
        shutil.copyfile(SOURCE / source, folder / target)

    mods[MOD_ID] = {
        "id": MOD_ID,
        "name": "Better CtrlTab",
        "description": "Customize Ctrl+Tab. Set the total in about:config via browser.ctrlTab.maxPreviews.",
        "version": "1.0.0",
        "enabled": True,
        "preferences": "preferences.json",
    }
    backup = registry.with_suffix(".json.before-better-ctrltab")
    if registry.exists() and not backup.exists():
        shutil.copy2(registry, backup)
    temp = registry.with_suffix(".json.better-ctrltab.tmp")
    temp.write_text(json.dumps(mods, indent=2) + "\n", encoding="utf-8")
    temp.replace(registry)
    print("Installed Better CtrlTab. Reopen Zen, then toggle it off and on in Settings → Zen Mods.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        sys.exit(f"Installation failed: {error}")
