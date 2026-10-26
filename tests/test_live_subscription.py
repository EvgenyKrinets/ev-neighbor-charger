"""Exercise subscription lifecycle without installing Home Assistant."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).parents[1] / 'custom_components/ev_neighbor_charger/__init__.py'

class SubscriptionTests(unittest.TestCase):
    def test_initial_push_changes_and_unload_cleanup(self):
        tree = ast.parse(SOURCE.read_text())
        setup = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'async_setup_entry')
        function = next(node for node in setup.body if isinstance(node, ast.FunctionDef) and node.name == 'ws_subscribe')
        function.decorator_list = []
        module = ast.Module(body=[function], type_ignores=[])
        listeners = {}; active = set(); messages = []
        def register(key, fn):
            listeners[key] = fn
            active.add(key)
            return lambda: active.discard(key)
        user=object()
        connection=SimpleNamespace(user=user,subscriptions={},send_result=lambda i:messages.append(('result',i)),send_event=lambda i,d:messages.append(('event',i,d)))
        namespace={'authorized':lambda connection,msg:True,'callback':lambda fn:fn,'DOMAIN':'ev_neighbor_charger','CONF_POWER':'power','CONF_ENERGY':'energy','CONF_SWITCH':'switch','settings':{'power':'sensor.power','energy':'sensor.energy','switch':'switch.charger'},'data':{},'snapshot':lambda recipient:{'recipient':recipient},'async_track_state_change_event':lambda hass,entities,fn:register(tuple(entities),fn),'async_dispatcher_connect':lambda hass,signal,fn:register(signal,fn)}
        exec(compile(module,str(SOURCE),'exec'),namespace)
        namespace['ws_subscribe'](object(),connection,{'id':7})
        self.assertEqual(messages[0],('result',7))
        self.assertIs(messages[1][2]['recipient'],user)
        listeners[('sensor.power','sensor.energy','switch.charger')](object())
        self.assertEqual(len(messages),3)
        listeners['ev_neighbor_charger_unloading']()
        self.assertEqual(messages[-1],('event',7,{'reload':True}))
        self.assertFalse(active)
        connection.subscriptions[7]()  # Disconnect after reload must remain safe.
        self.assertFalse(namespace['data']['live_subscriptions'])

    def test_charge_phases_and_complete_authorized_history(self):
        from datetime import datetime, timezone
        tree = ast.parse(SOURCE.read_text())
        setup = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'async_setup_entry')
        functions = [n for n in setup.body if isinstance(n, ast.FunctionDef) and n.name in ('snapshot', 'power_changed')]
        for fn in functions: fn.decorator_list = []
        data = {'active':{'user_id':'neighbor','name':'Neighbor'},'timer':None,'profiles':{},'mail_error':None,
                'sessions':[{'user_id':'neighbor','energy_kwh':1,'cost':1} for _ in range(150)]+[{'user_id':'other','energy_kwh':2,'cost':2}]}
        settings = {'power':'power','energy':'energy','switch':'switch.charger','users':['neighbor'],'idle':100,'delay':120,'rate':1}
        state = SimpleNamespace(state='0',last_updated=datetime.now(timezone.utc))
        saved=[]
        async def persist(): pass
        def schedule(coro): saved.append(True);coro.close()
        hass=SimpleNamespace(states=SimpleNamespace(get=lambda key:state),async_create_task=schedule)
        ns={'data':data,'settings':settings,'entry':SimpleNamespace(entry_id='test-entry'),'hass':hass,'persist':persist,'_num':lambda s,unit:None if s.state=='unavailable' else float(s.state),
            'CONF_POWER':'power','CONF_ENERGY':'energy','CONF_SWITCH':'switch','CONF_USERS':'users','CONF_RATE':'rate','CONF_IDLE_W':'idle','CONF_IDLE_SECONDS':'delay',
            'VERSION':'test','suggested_email':lambda u:None,'low_power_callback':lambda now:None,'async_call_later':lambda *args:lambda:None}
        exec(compile(ast.Module(body=functions,type_ignores=[]),str(SOURCE),'exec'),ns)
        user=SimpleNamespace(id='neighbor',is_admin=False)
        self.assertEqual(ns['snapshot'](user)['charge_phase'],'preparing')
        state.state='101';ns['power_changed'](SimpleNamespace(data={'new_state':state}))
        self.assertTrue(data['active']['has_load']);self.assertTrue(saved)
        self.assertEqual(ns['snapshot'](user)['charge_phase'],'charging')
        state.state='100';ns['power_changed'](SimpleNamespace(data={'new_state':state}))
        self.assertEqual(ns['snapshot'](user)['charge_phase'],'finishing')
        state.state='101';ns['power_changed'](SimpleNamespace(data={'new_state':state}))
        self.assertEqual(ns['snapshot'](user)['charge_phase'],'charging')
        state.state='unavailable';self.assertEqual(ns['snapshot'](user)['charge_phase'],'unavailable')
        self.assertEqual(len(ns['snapshot'](user)['sessions']),150)
        # External ON must claim the station without claiming a charge session.
        data['active'] = None
        switch_on = SimpleNamespace(state='on',last_updated=datetime.now(timezone.utc))
        hass.states.get = lambda key: switch_on if key == 'switch.charger' else state
        settings['switch'] = 'switch.charger'
        external = ns['snapshot'](user)
        self.assertEqual(external['charge_phase'], 'external')
        self.assertTrue(external['external_control'])
        self.assertTrue(external['busy'])
        self.assertIsNone(external['active'])
        switch_on.state = 'off'
        available = ns['snapshot'](user)
        self.assertFalse(available['external_control'])
        self.assertFalse(available['busy'])
        self.assertEqual(available['charge_phase'], 'available')
        user.is_admin=True;self.assertEqual(len(ns['snapshot'](user)['sessions']),151)
