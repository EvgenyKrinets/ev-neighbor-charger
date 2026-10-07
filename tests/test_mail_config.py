import importlib.util
from pathlib import Path
import sys
from types import ModuleType
import unittest

component=Path(__file__).parents[1]/'custom_components/ev_neighbor_charger'
package=ModuleType('mail_test_package');package.__path__=[str(component)];sys.modules[package.__name__]=package
spec=importlib.util.spec_from_file_location('mail_test_package.mail_config',component/'mail_config.py')
mail=importlib.util.module_from_spec(spec);spec.loader.exec_module(mail)

class MailConfigTests(unittest.TestCase):
    def test_presets_set_sender_host_and_tls(self):
        for provider,expected in [('gmail',('smtp.gmail.com',587,'starttls')),('yahoo',('smtp.mail.yahoo.com',465,'ssl')),('icloud',('smtp.mail.me.com',587,'starttls')),('brevo',('smtp-relay.brevo.com',587,'starttls')),('mailjet',('in-v3.mailjet.com',587,'starttls'))]:
            result=mail.mail_settings(provider,{'smtp_username':'owner@example.com','smtp_password':'app-secret','smtp_sender':'owner@example.com'}, {})
            self.assertEqual((result['smtp_host'],result['smtp_port'],result['smtp_security']),expected)
            self.assertEqual(result['smtp_sender'],'owner@example.com')
    def test_password_is_not_reused_for_changed_provider_or_account(self):
        previous={'smtp_provider':'gmail','smtp_username':'owner@example.com','smtp_password':'secret'}
        result=mail.mail_settings('gmail',{'smtp_username':'owner@example.com'},previous)
        self.assertEqual(result['smtp_password'],'secret')
        for provider,address in [('yahoo','owner@example.com'),('gmail','other@example.com')]:
            with self.assertRaisesRegex(ValueError,'password_required'):
                mail.mail_settings(provider,{'smtp_username':address},previous)
    def test_microsoft_password_only_is_not_advertised_as_working(self):
        with self.assertRaisesRegex(ValueError,'microsoft_oauth'):
            mail.mail_settings('microsoft',{'smtp_username':'owner@outlook.com','smtp_password':'secret'}, {})
    def test_custom_without_authentication(self):
        result=mail.mail_settings('custom',{'smtp_host':'smtp.example.com','smtp_port':587,'smtp_security':'starttls','smtp_sender':'owner@example.com'}, {})
        self.assertEqual(result['smtp_username'],'')

    def test_mailjet_api_key_is_not_an_email_address(self):
        result=mail.mail_settings('mailjet',{'smtp_username':'public-api-key','smtp_password':'secret-api-key','smtp_sender':'verified@example.com'}, {})
        self.assertEqual(result['smtp_username'],'public-api-key')
        self.assertEqual(result['smtp_sender'],'verified@example.com')
