"""Install or remove Better CtrlTab in a closed Zen profile (Python 3.9+)."""
import argparse
import configparser
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid

MOD_ID = "43e5b1ae-d1b5-4d38-a1ea-15a7c7de328f"
SOURCE = Path(__file__).resolve().parent
FILES = {"chrome.css": "chrome.css", "preferences.json": "preferences.json", "README.md": "readme.md"}
METADATA = {
    "id": MOD_ID, "name": "Better CtrlTab",
    "description": "Customize Ctrl+Tab. Set the total in about:config via browser.ctrlTab.maxPreviews.",
    "version": "1.0.0", "enabled": True, "preferences": "preferences.json",
}


def profile_roots():
    home = Path.home()
    return [home / "Library/Application Support/zen",
            Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "zen",
            home / ".zen", home / ".var/app/app.zen_browser.zen/.zen",
            home / "snap/zen-browser/common/.zen", home / "snap/zen/common/.zen"]


def discover_profiles(roots=None):
    """Return {resolved profile: default?}; ambiguous defaults require --profile."""
    found = {}
    for root in profile_roots() if roots is None else roots:
        defaults = set()
        candidates = set()
        for filename in ("profiles.ini", "installs.ini"):
            ini = root / filename
            if not ini.is_file():
                continue
            config = configparser.ConfigParser(interpolation=None)
            with ini.open(encoding="utf-8-sig") as stream:
                config.read_file(stream)
            for section in config.sections():
                values = config[section]
                if section.startswith("Profile") and values.get("path"):
                    path = Path(values["path"]).expanduser()
                    if values.get("isrelative", "1") == "1":
                        path = root / path
                    candidates.add(path.resolve())
                    if values.get("default") == "1":
                        defaults.add(path.resolve())
                elif values.get("default") and (section.startswith("Install") or filename == "installs.ini"):
                    path = Path(values["default"]).expanduser()
                    path = (root / path).resolve() if not path.is_absolute() else path.resolve()
                    candidates.add(path)
                    defaults.add(path)
        for parent in (root, root / "Profiles"):
            if parent.is_dir():
                candidates.update(path.resolve() for path in parent.iterdir()
                                  if path.is_dir() and (path / "prefs.js").is_file())
        for path in candidates:
            if (path / "prefs.js").is_file():
                found[path] = found.get(path, False) or path in defaults
    return dict(sorted(found.items(), key=lambda item: str(item[0])))


def find_profile(profiles):
    defaults = [path for path, default in profiles.items() if default]
    if len(defaults) == 1:
        return defaults[0]
    if len(profiles) == 1:
        return next(iter(profiles))
    raise ValueError('No unambiguous profile. Use --list-profiles, then --profile "Profile Folder" from about:support.')


def safe_path(profile, path):
    """Never follow a managed symlink/junction or escape the selected profile."""
    path.resolve().relative_to(profile)
    for part in (path, *path.parents):
        if part == profile:
            break
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError(f"Refusing linked path: {part}")


def check_closed(profile):
    # Existence deliberately includes dangling Unix lock symlinks. Stale locks
    # require manual verification; --yes never overrides this protection.
    for name in ("parent.lock", ".parentlock", "lock"):
        if os.path.lexists(profile / name):
            raise ValueError(f"Zen may be running: {profile / name}. Quit Zen; verify any stale lock manually.")


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".better-ctrltab-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            shutil.copymode(path, temp)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def plan(profile, uninstall=False):
    registry = profile / "zen-themes.json"
    folder = profile / "chrome/zen-themes" / MOD_ID
    for path in (registry, folder, *(folder / name for name in FILES.values())):
        safe_path(profile, path)
    raw = registry.read_bytes() if registry.exists() else b""
    mods = json.loads(raw.decode("utf-8-sig")) if raw else {}
    if not isinstance(mods, dict):
        raise ValueError("Unexpected Zen Mods registry format (expected an object).")
    existing = mods.get(MOD_ID)
    if MOD_ID in mods and (not isinstance(existing, dict) or existing.get("id", MOD_ID) != MOD_ID
                           or existing.get("name") != METADATA["name"]):
        raise ValueError(f"Conflicting registry entry for {MOD_ID}; refusing to overwrite it.")
    changes = []
    if uninstall:
        for target in FILES.values():
            path = folder / target
            if path.exists():
                changes.append((path, None))
        mods.pop(MOD_ID, None)
    else:
        for source, target in FILES.items():
            data = (SOURCE / source).read_bytes()
            path = folder / target
            if not path.exists() or path.read_bytes() != data:
                changes.append((path, data))
        entry = dict(existing or {})
        entry.update(METADATA)
        if existing:
            entry["enabled"] = existing.get("enabled", True)
        mods[MOD_ID] = entry
    # Do not rewrite a semantically unchanged registry (or create one on no-op removal).
    old = json.loads(raw.decode("utf-8-sig")) if raw else {}
    if mods != old:
        newline = "\r\n" if b"\r\n" in raw else "\n"
        data = (json.dumps(mods, indent=2, ensure_ascii=False) + "\n").replace("\n", newline).encode("utf-8")
        if raw.startswith(b"\xef\xbb\xbf"):
            data = b"\xef\xbb\xbf" + data
        changes.append((registry, data))
    return changes, folder


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, help="Profile Folder from about:support")
    parser.add_argument("--dry-run", action="store_true", help="print changes without writing")
    parser.add_argument("--uninstall", action="store_true", help="remove only this mod's registry entry and bundled files")
    parser.add_argument("--list-profiles", action="store_true", help="list discovered profiles and exit")
    parser.add_argument("--yes", action="store_true", help="accept the printed plan without prompting (does not bypass locks)")
    args = parser.parse_args(argv)
    if args.list_profiles:
        profiles = discover_profiles()
        for path, default in profiles.items():
            print(f"{path}" + (" [default]" if default else ""))
        if not profiles:
            print("No profiles found. Use --profile with the Profile Folder from about:support.")
        return 0
    profile = args.profile.expanduser().resolve() if args.profile else find_profile(discover_profiles())
    if not (profile / "prefs.js").is_file():
        raise ValueError(f"Not a Zen profile folder: {profile}")
    changes, folder = plan(profile, args.uninstall)
    backup = profile / ".better-ctrltab-backups" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ-") + uuid.uuid4().hex[:8])
    safe_path(profile, backup)
    print(f"Profile: {profile}")
    for path, data in changes:
        print(f"{'REMOVE' if data is None else 'REPLACE' if path.exists() else 'CREATE'} {path}")
        if path.exists():
            print(f"BACKUP {path} -> {backup / path.relative_to(profile)}")
    cleanup = args.uninstall and folder.is_dir() and all(path.name in FILES.values() and path.is_file() for path in folder.iterdir())
    if cleanup:
        print(f"REMOVE DIRECTORY IF EMPTY {folder}")
    if not changes and not cleanup:
        print("No changes needed.")
        return 0
    if args.dry_run:
        print("Dry run: no files changed. Quit Zen before applying this plan.")
        return 0
    check_closed(profile)
    if not args.yes:
        if not sys.stdin.isatty():
            raise ValueError("Noninteractive operation requires --yes (or --dry-run).")
        if input("Apply these changes? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Cancelled; no files changed.")
            return 0
    check_closed(profile)
    # Complete all backups before modifying any original file.
    for path, _ in changes:
        safe_path(profile, path)
        if path.exists():
            target = backup / path.relative_to(profile)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    for path, data in changes:
        if data is None:
            path.unlink()
        else:
            atomic_write(path, data)
    if cleanup and not any(folder.iterdir()):
        folder.rmdir()
    print("Removed Better CtrlTab." if args.uninstall else
          "Installed Better CtrlTab. Reopen Zen and toggle it off/on in Settings > Zen Mods.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, configparser.Error) as error:
        sys.exit(f"Operation failed: {error}. If partially applied, restore files from the printed backup paths.")
