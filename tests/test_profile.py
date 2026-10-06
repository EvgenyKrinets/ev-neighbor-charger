"""Email suggestions must never cross users or silently replace saved email."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace, ModuleType
import unittest

ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / 'custom_components/ev_neighbor_charger'
package = ModuleType('ev_test_package')
package.__path__ = [str(COMPONENT)]
sys.modules[package.__name__] = package
spec = importlib.util.spec_from_file_location('ev_test_package.profile', COMPONENT / 'profile.py')
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)

def user(*values):
    return SimpleNamespace(credentials=[SimpleNamespace(auth_provider_type=provider, data={'username':value}) for provider,value in values])

class ProfileTests(unittest.TestCase):
    def test_local_email_login(self):
        self.assertEqual(profile.suggested_email(user(('homeassistant','neighbor@example.com'))), 'neighbor@example.com')

    def test_plain_login_and_other_auth_provider_not_email_source(self):
        self.assertEqual(profile.suggested_email(user(('homeassistant','neighbor'),('cloud','owner@example.com'))), '')
        self.assertEqual(profile.suggested_email(None), '')

    def test_ambiguous_emails_are_not_selected(self):
        self.assertEqual(profile.suggested_email(user(('homeassistant','a@example.com'),('homeassistant','b@example.com'))), '')

    def test_manifest_and_display_version_match(self):
        values={}
        exec((COMPONENT/'const.py').read_text(),values)
        self.assertEqual(values['VERSION'],json.loads((COMPONENT/'manifest.json').read_text())['version'])
