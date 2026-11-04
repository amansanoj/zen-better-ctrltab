"""Installer regression tests; no real browser/profile is used."""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('installer', Path(__file__).resolve().parents[1] / 'install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.profile = self.root / 'profile'
        self.profile.mkdir()
        (self.profile / 'prefs.js').write_text('// untouched\n', encoding='utf-8')
        self.registry = self.profile / 'zen-themes.json'
        self.original = b'{"other-mod": {"enabled": false}}\r\n'
        self.registry.write_bytes(self.original)
        self.folder = self.profile / 'chrome/zen-themes' / installer.MOD_ID

    def run_cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            return installer.main(['--profile', str(self.profile), *args])

    def snapshot(self):
        return {str(path.relative_to(self.profile)): path.read_bytes()
                for path in self.profile.rglob('*') if path.is_file()}

    def test_install_and_noop_reinstall(self):
        self.run_cli('--yes')
        data = json.loads(self.registry.read_bytes())
        self.assertEqual(data['other-mod'], {'enabled': False})
        self.assertEqual(data[installer.MOD_ID]['name'], 'Better CtrlTab')
        for source, target in installer.FILES.items():
            self.assertEqual((self.folder / target).read_bytes(), (installer.SOURCE / source).read_bytes())
        before = self.snapshot()
        self.run_cli('--yes')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual((self.profile / 'prefs.js').read_text(), '// untouched\n')

    def test_preserves_disabled_and_unknown_metadata(self):
        self.run_cli('--yes')
        data = json.loads(self.registry.read_bytes())
        data[installer.MOD_ID].update(enabled=False, custom='keep')
        self.registry.write_text(json.dumps(data), encoding='utf-8')
        self.run_cli('--yes')
        self.assertEqual(json.loads(self.registry.read_bytes())[installer.MOD_ID]['enabled'], False)
        self.assertEqual(json.loads(self.registry.read_bytes())[installer.MOD_ID]['custom'], 'keep')

    def test_uninstall_backups_and_unrelated_files(self):
        self.run_cli('--yes')
        (self.folder / 'user.txt').write_text('keep', encoding='utf-8')
        self.run_cli('--uninstall', '--yes')
        self.assertEqual(json.loads(self.registry.read_bytes()), {'other-mod': {'enabled': False}})
        self.assertEqual([p.name for p in self.folder.iterdir()], ['user.txt'])
        backups = self.profile / '.better-ctrltab-backups'
        self.assertTrue(any(p.read_bytes() == self.original for p in backups.rglob('zen-themes.json')))
        self.assertTrue(list(backups.rglob('chrome.css')))
        before = self.snapshot()
        self.run_cli('--uninstall', '--yes')
        self.assertEqual(self.snapshot(), before)

    def test_changed_bundle_is_backed_up(self):
        self.run_cli('--yes')
        css = self.folder / 'chrome.css'
        css.write_bytes(b'/* local edits */')
        self.run_cli('--yes')
        self.assertTrue(any(p.read_bytes() == b'/* local edits */'
                            for p in (self.profile / '.better-ctrltab-backups').rglob('chrome.css')))

    def test_dry_run_and_uninstall_dry_run_do_not_write(self):
        before = self.snapshot()
        self.run_cli('--dry-run')
        self.run_cli('--uninstall', '--dry-run')
        self.assertEqual(self.snapshot(), before)
        self.run_cli('--yes')
        before = self.snapshot()
        self.run_cli('--uninstall', '--dry-run')
        self.assertEqual(self.snapshot(), before)

    def test_empty_owned_folder_removed(self):
        self.run_cli('--yes')
        self.run_cli('--uninstall', '--yes')
        self.assertFalse(self.folder.exists())

    def test_persistent_unlocked_files_do_not_block_install(self):
        for name in ('parent.lock', '.parentlock', 'lock'):
            (self.profile / name).write_bytes(b'leftover lock file')
        self.run_cli('--yes')
        self.assertIn(installer.MOD_ID, json.loads(self.registry.read_bytes()))
        for name in ('parent.lock', '.parentlock', 'lock'):
            self.assertEqual((self.profile / name).read_bytes(), b'leftover lock file')

    def test_active_native_lock_refused_even_with_yes(self):
        lock = self.profile / ('parent.lock' if os.name == 'nt' else '.parentlock')
        lock.write_bytes(b'')
        # POSIX record locks are per-process: use a real child, not a mock or
        # a second descriptor in the test process. Match Gecko's Windows handle.
        script = r"""
import os, sys
if os.name == 'nt':
    import ctypes
    from ctypes import wintypes
    create = ctypes.WinDLL('kernel32', use_last_error=True).CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    handle = create(sys.argv[1], 0xC0000000, 0, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
else:
    import fcntl
    stream = open(sys.argv[1], 'r+b')
    fcntl.lockf(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
print('locked', flush=True)
sys.stdin.readline()
"""
        child = subprocess.Popen([sys.executable, '-u', '-c', script, str(lock)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), 'locked')
            before = self.snapshot() if os.name != 'nt' else self.registry.read_bytes()
            with self.assertRaisesRegex(ValueError, 'no mod files were changed'):
                self.run_cli('--yes')
            result = subprocess.run([sys.executable, str(installer.SOURCE / 'install.py'),
                                     '--profile', str(self.profile), '--yes'],
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 1)
            self.assertIn('no mod files were changed', result.stderr)
            self.assertNotIn('restore', result.stderr)
            if os.name != 'nt':
                self.assertEqual(self.snapshot(), before)
            else:
                self.assertEqual(self.registry.read_bytes(), before)
                self.assertFalse(self.folder.exists())
        finally:
            try:
                child.communicate('done\n', timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.communicate()
                raise
        self.assertEqual(child.returncode, 0)
        # Releasing the held lock leaves the file behind; installation succeeds.
        self.run_cli('--yes')
        self.assertTrue(self.folder.exists())

    def test_legacy_symlink_lock_is_not_followed_or_removed(self):
        path = self.profile / 'lock'
        try:
            path.symlink_to('unresolved-owner')
        except OSError:
            self.skipTest('Symlinks unavailable for this account')
        with self.assertRaisesRegex(ValueError, 'legacy profile lock'):
            self.run_cli('--yes')
        self.assertTrue(path.is_symlink())
        self.assertFalse(self.folder.exists())

    def test_invalid_registry_does_not_modify_bundle(self):
        for bad in (b'not JSON', b'[]', b''):
            self.registry.write_bytes(bad)
            before = self.snapshot()
            with self.assertRaises(ValueError):
                self.run_cli('--yes')
            self.assertEqual(self.snapshot(), before)

    def test_conflicting_uuid_refused(self):
        self.registry.write_text(json.dumps({installer.MOD_ID: {'name': 'Someone else'}}), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            self.run_cli('--yes')

    def test_symlink_escape_refused(self):
        outside = self.root / 'outside'
        outside.mkdir()
        try:
            (self.profile / 'chrome').symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('Symlinks unavailable for this account')
        with self.assertRaises(ValueError):
            self.run_cli('--yes')
        self.assertEqual(list(outside.iterdir()), [])

    def test_backup_failure_prevents_writes(self):
        before = self.snapshot()
        with mock.patch.object(installer.shutil, 'copy2', side_effect=OSError('full disk')):
            with self.assertRaisesRegex(ValueError, 'No mod files were changed'):
                self.run_cli('--yes')
        self.assertEqual(self.snapshot(), before)

    def test_discovery_ini_absolute_relative_and_defaults(self):
        root = self.root / 'zen'
        root.mkdir()
        relative = root / 'Profiles/default'
        relative.mkdir(parents=True)
        (relative / 'prefs.js').touch()
        (root / 'profiles.ini').write_text(
            '[Profile0]\nPath=Profiles/default\nIsRelative=1\n'
            '[Profile1]\nPath=' + self.profile.as_posix() + '\nIsRelative=0\n'
            '[InstallABC]\nDefault=Profiles/default\n', encoding='utf-8')
        profiles = installer.discover_profiles([root])
        self.assertEqual(set(profiles), {relative.resolve(), self.profile.resolve()})
        self.assertEqual(installer.find_profile(profiles), relative.resolve())
        (root / 'installs.ini').write_text('[DEF]\nDefault=' + self.profile.as_posix() + '\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'unambiguous'):
            installer.find_profile(installer.discover_profiles([root]))

    def test_list_profiles_and_platform_roots(self):
        with mock.patch.object(installer.Path, 'home', return_value=self.root):
            with mock.patch.dict(installer.os.environ, {'APPDATA': str(self.root / 'roaming')}):
                roots = installer.profile_roots()
        self.assertIn(self.root / 'roaming/zen', roots)
        self.assertIn(self.root / '.var/app/app.zen_browser.zen/.zen', roots)
        self.assertIn(self.root / 'snap/zen-browser/common/.zen', roots)
        with mock.patch.object(installer, 'discover_profiles', return_value={self.profile: True}):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(installer.main(['--list-profiles']), 0)
            self.assertIn('[default]', output.getvalue())

    def test_atomic_failure_cleans_temp_and_preserves_original(self):
        target = self.profile / 'existing.css'
        target.write_bytes(b'original')
        with mock.patch.object(installer.os, 'replace', side_effect=OSError('replace failed')):
            with self.assertRaises(OSError):
                installer.atomic_write(target, b'new')
        self.assertEqual(target.read_bytes(), b'original')
        self.assertEqual(list(self.profile.glob('.better-ctrltab-*')), [])

    def test_absent_registry_and_bom_preservation(self):
        self.registry.unlink()
        self.run_cli('--yes')
        self.assertIn(installer.MOD_ID, json.loads(self.registry.read_bytes()))
        self.registry.write_bytes(b'\xef\xbb\xbf' + self.original)
        self.run_cli('--yes')
        self.assertTrue(self.registry.read_bytes().startswith(b'\xef\xbb\xbf'))
        self.assertIn(b'\r\n', self.registry.read_bytes())

    def test_missing_profile_and_confirmation(self):
        with self.assertRaisesRegex(ValueError, 'Not a Zen'):
            installer.main(['--profile', str(self.root / 'missing'), '--dry-run'])
        before = self.snapshot()
        with mock.patch.object(installer.sys.stdin, 'isatty', return_value=False):
            with self.assertRaisesRegex(ValueError, 'Noninteractive'):
                self.run_cli()
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
