"""Run without a Home Assistant installation: python -m unittest discover -s tests."""
import importlib.util
from pathlib import Path
from datetime import timezone, timedelta
import unittest
from unittest.mock import patch, MagicMock

spec = importlib.util.spec_from_file_location('reporting', Path(__file__).parents[1] / 'custom_components/ev_neighbor_charger/reporting.py')
reporting = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporting)

class ReportTests(unittest.TestCase):
    def setUp(self):
        self.record = {'start':'2026-09-30T20:30:00+00:00','end':'2026-09-30T22:30:00+00:00','rate':0.65,'energy_kwh':10,'cost':6.5,'reason':'idle_timeout'}
        self.job = {'kind':'monthly','month':'2026-10','email':'client@example.com','language':'ru','records':[self.record]}

    def test_email_validation(self):
        self.assertTrue(reporting.valid_email('client+ev@example.com'))
        for value in ['x', 'a@b', 'a@example.com\nBcc:other@example.com', 'a@example.com,b@example.com']:
            self.assertFalse(reporting.valid_email(value))

    def test_local_dates_duration_and_csv(self):
        message = reporting.make_message(self.job, 'sender@example.com', timezone(timedelta(hours=3)))
        text = message.get_body(preferencelist=('plain',)).get_content()
        self.assertIn('2026-10-01T01:30:00+03:00', text)
        self.assertIn('120.0', text)
        self.assertIn('10.000 kWh · 6.50 ILS', text)
        self.assertIn('Автоотключение', text)
        attachment = list(message.iter_attachments())[0]
        self.assertEqual(attachment.get_filename(), 'charging-2026-10.csv')
        self.assertIn('Итого,,,10,6.5', attachment.get_payload(decode=True).decode('utf-8-sig'))

    def test_all_languages_and_start_without_final_totals(self):
        for language in ['en','ru','he']:
            job={**self.job,'language':language,'kind':'start','records':[{'start':self.record['start'],'rate':0.65}]}
            message=reporting.make_message(job,'sender@example.com',timezone.utc)
            self.assertEqual(message['Subject'], reporting.LABELS[language][0]+' · 2026-10')
            self.assertNotIn('0.000 kWh', message.get_content())

    @patch.object(reporting.smtplib, 'SMTP')
    def test_starttls_before_auth_and_send(self, factory):
        client=MagicMock();factory.return_value.__enter__.return_value=client
        reporting.send_mail({'smtp_host':'mail.example.com','smtp_sender':'sender@example.com','smtp_username':'user','smtp_password':'secret'}, self.job, timezone.utc)
        self.assertEqual([c[0] for c in client.mock_calls], ['starttls','login','send_message'])
        factory.assert_called_once_with('mail.example.com',587,timeout=20)

if __name__ == '__main__':
    unittest.main()

class SMTPTestMessageTests(unittest.TestCase):
    def test_message_is_a_test_not_a_charging_notification(self):
        msg=reporting.make_message({'kind':'test','email':'recipient@example.com','language':'ru'},'sender@example.com',timezone.utc)
        self.assertIn('Проверка',msg['Subject'])
        self.assertEqual(msg['To'],'recipient@example.com')
        self.assertNotIn('Зарядка началась',msg.get_content())

    def test_error_details_hide_credentials(self):
        text=reporting.smtp_error_detail(ValueError('535 secret-token user@example.com failed'), {'smtp_password':'secret-token','smtp_username':'user@example.com'})
        self.assertNotIn('secret-token',text)
        self.assertNotIn('user@example.com',text)
        self.assertIn('535',text)
