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
        namespace={'callback':lambda fn:fn,'DOMAIN':'ev_neighbor_charger','CONF_POWER':'power','CONF_ENERGY':'energy','CONF_SWITCH':'switch','settings':{'power':'sensor.power','energy':'sensor.energy','switch':'switch.charger'},'data':{},'snapshot':lambda recipient:{'recipient':recipient},'async_track_state_change_event':lambda hass,entities,fn:register(tuple(entities),fn),'async_dispatcher_connect':lambda hass,signal,fn:register(signal,fn)}
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
