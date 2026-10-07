import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

class AccessTests(unittest.TestCase):
    def test_only_admin_and_selected_user_authorized(self):
        source=Path(__file__).parents[1]/'custom_components/ev_neighbor_charger/__init__.py'
        setup=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.AsyncFunctionDef) and n.name=='async_setup_entry')
        fn=next(n for n in setup.body if isinstance(n,ast.FunctionDef) and n.name=='authorized')
        fn.decorator_list=[]
        settings={'allowed_users':['neighbor']}
        ns={'settings':settings,'CONF_USERS':'allowed_users','websocket_api':SimpleNamespace(ERR_UNAUTHORIZED='unauthorized')}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),str(source),'exec'),ns)
        for uid,admin,expected in [('admin',True,True),('neighbor',False,True),('other',False,False)]:
            errors=[]
            conn=SimpleNamespace(user=SimpleNamespace(id=uid,is_admin=admin),send_error=lambda *args:errors.append(args))
            self.assertEqual(ns['authorized'](conn,{'id':1}),expected)
            self.assertEqual(bool(errors),not expected)
        settings['allowed_users']=[]
        conn=SimpleNamespace(user=SimpleNamespace(id='neighbor',is_admin=False),send_error=lambda *args:None)
        self.assertFalse(ns['authorized'](conn,{'id':2}))
