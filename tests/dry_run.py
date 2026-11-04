"""Exercise the real CLI with an explicit disposable profile on every OS."""
from pathlib import Path
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory() as root:
    profile = Path(root) / 'profile'
    profile.mkdir()
    (profile / 'prefs.js').write_text('// fake profile\n', encoding='utf-8')
    subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'install.py'),
                    '--profile', str(profile), '--dry-run'], check=True)
    assert [p.name for p in profile.iterdir()] == ['prefs.js']
