"""Exercise explicit SMTP testing and failure presentation without network calls."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase

source=Path(__file__).parents[1]/'custom_components/ev_neighbor_charger/config_flow.py'

class SMTPOptionsTests(IsolatedAsyncioTestCase):
    def make_flow(self, fail=False):
        tree=ast.parse(source.read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='EVNeighborChargerOptionsFlow')
        cls.bases=[];cls.decorator_list=[]
        class Select:
            SelectSelectorMode=SimpleNamespace(DROPDOWN='dropdown')
            def SelectSelectorConfig(self,**kwargs):return kwargs
            def SelectSelector(self,cfg):return cfg
        vol=SimpleNamespace(Required=lambda key,**kwargs:key,Schema=lambda cfg:cfg)
        ns={'vol':vol,'selector':Select(),'DOMAIN':'ev_neighbor_charger','valid_email':lambda value:isinstance(value,str) and '@' in value,'dt_util':SimpleNamespace(get_time_zone=lambda value:value),'send_mail':object(),'smtp_error_detail':lambda err,settings:str(err)}
        exec(compile(ast.Module(body=[cls],type_ignores=[]),str(source),'exec'),ns)
        flow=ns['EVNeighborChargerOptionsFlow']()
        flow.config_entry=SimpleNamespace(data={'smtp_enabled':True,'smtp_sender':'sender@example.com'},options={},entry_id='entry')
        self.calls=[]
        async def executor(*args):
            self.calls.append(args)
            if fail:raise RuntimeError('535 authentication rejected')
        flow.hass=SimpleNamespace(config=SimpleNamespace(language='ru',time_zone='Asia/Jerusalem'),data={'ev_neighbor_charger':{'entry':{'profiles':{'user':{'email':'saved@example.com'}}}}},async_add_executor_job=executor)
        flow.async_show_form=lambda **kwargs:kwargs
        flow.async_create_entry=lambda **kwargs:kwargs
        return flow

    async def test_saved_or_manual_recipient_and_success(self):
        flow=self.make_flow()
        initial=await flow.async_step_mail_test()
        selector=initial['data_schema']['test_recipient']
        self.assertTrue(selector['custom_value'])
        self.assertIn('saved@example.com',selector['options'])
        result=await flow.async_step_mail_test({'test_recipient':'typed@example.com','test_action':'test'})
        self.assertEqual(self.calls[0][2]['email'],'typed@example.com')
        self.assertEqual(self.calls[0][2]['kind'],'test')
        self.assertEqual(result['errors'],{})
        self.assertEqual(result['step_id'],'mail_test_result')
        self.assertIn('принял',result['description_placeholders']['result'])

    async def test_failure_remains_in_form(self):
        flow=self.make_flow(fail=True)
        result=await flow.async_step_mail_test({'test_recipient':'typed@example.com','test_action':'test'})
        self.assertEqual(result['errors']['base'],'mail_test_failed')
        self.assertEqual(result['step_id'],'mail_test_result')
        self.assertIn('535',result['description_placeholders']['result'])

    async def test_save_does_not_send_another_message(self):
        flow=self.make_flow()
        flow._pending_mail={'smtp_host':'new.example.com'}
        result=await flow.async_step_mail_test({'test_action':'save'})
        self.assertEqual(result['data']['smtp_host'],'new.example.com')
        self.assertEqual(self.calls,[])

    async def test_result_submit_retries_and_updates_status(self):
        flow=self.make_flow(fail=True)
        first=await flow.async_step_mail_test({"test_recipient":"typed@example.com","test_action":"test"})
        self.assertEqual(first["step_id"],"mail_test_result")
        async def success(*args): self.calls.append(args)
        flow.hass.async_add_executor_job=success
        result=await flow.async_step_mail_test_result({"test_recipient":"typed@example.com","test_action":"test"})
        self.assertEqual(len(self.calls),2)
        self.assertEqual(result["errors"],{})
        self.assertNotIn("535",result["description_placeholders"]["result"])
