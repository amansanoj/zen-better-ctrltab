"""Validate this mod's dropdown subset and CSS hook coverage (stdlib only)."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def validate():
    prefs = json.loads((ROOT / 'preferences.json').read_text(encoding='utf-8'))
    css = (ROOT / 'chrome.css').read_text(encoding='utf-8')
    expected = {
        'frost.ctrltab.favicon': ('overlap-right', ['overlap-left', 'overlap-center', 'overlap-right', 'title-left', 'title-right', 'none']),
        'frost.ctrltab.previews-per-row': ('5', [str(i) for i in range(1, 8)]),
    }
    assert isinstance(prefs, list) and len(prefs) == 2
    assert {p['property'] for p in prefs} == set(expected)
    for pref in prefs:
        default, values = expected[pref['property']]
        assert set(pref) == {'property', 'label', 'type', 'defaultValue', 'options'}
        assert isinstance(pref['label'], str) and pref['label']
        assert pref['type'] == 'dropdown' and pref['defaultValue'] == default
        assert [o['value'] for o in pref['options']] == values
        for option in pref['options']:
            assert set(option) == {'label', 'value'}
            assert isinstance(option['label'], str) and option['label']
        attr = pref['property'].replace('.', '-')
        hooks = set(re.findall(r'\[' + re.escape(attr) + r'="([^"]+)"\]', css))
        if pref['property'].endswith('favicon'):
            # Implicit overlap-right uses base end/5px values; title-left is
            # covered by title-* prefix, with a more specific right override.
            assert hooks == set(values) - {'overlap-right', 'title-left'}
            assert f'[{attr}^="title-"]' in css
            assert '--bct-icon-x, 5px' in css and '--bct-icon-align, end' in css
        else:
            assert hooks == set(values)
            for value in values:
                assert re.search(r'\[' + re.escape(attr) + r'="' + value + r'"\][^{]+\{\s*--bct-row-limit: ' + value + ';', css)
    assert '#theme-Better-CtrlTab' in css
    # Check actual installer metadata, not a second hardcoded display name.
    import importlib.util
    spec = importlib.util.spec_from_file_location('installer', ROOT / 'install.py')
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    assert 'theme-' + installer.METADATA['name'].replace(' ', '-') == 'theme-Better-CtrlTab'
    print('PASS: dropdown structure, values, defaults and CSS hooks')


if __name__ == '__main__':
    validate()
