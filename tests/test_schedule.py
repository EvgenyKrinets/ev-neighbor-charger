"""Exercise reservation commands and launch lifecycle with fake HA services."""
import ast
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

SOURCE = Path(__file__).parents[1] / 'custom_components/ev_neighbor_charger/__init__.py'

class ScheduleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = NS(id='one',name='One',is_admin=False,is_active=True)
        self.data = {'active':None,'reservation':None,'starting':False,'stopped':False,'timer':None,'schedule_error':None}
        self.calls=[]; self.errors=[]; self.results=[]; self.timers=[]
        self.power=NS(state='0',attributes={})
        self.switch=NS(state='off',attributes={})
        self.energy=NS(state='42',attributes={})
        async def persist(): pass
        async def deliver(): pass
        async def get_user(uid): return self.user
        async def service(*args,**kwargs): self.calls.append((args,kwargs))
        def task(coro): coro.close()
        self.hass=NS(states=NS(get=lambda key:{'switch':self.switch,'energy':self.energy,'power':self.power}[key]),services=NS(async_call=service),auth=NS(async_get_user=get_user),async_create_task=task)
        self.connection=NS(user=self.user,send_error=lambda *v:self.errors.append(v),send_result=lambda *v:self.results.append(v))
        def authorized(c,m):
            ok=c.user.is_admin or c.user.id in ['one','two']
            if not ok:c.send_error(m['id'],'unauthorized','Unauthorized')
            return ok
        def timer(*args):
            self.timers.append(args);return lambda:None
        self.ns={'data':self.data,'settings':{'switch':'switch','energy':'energy','power':'power','users':['one','two']},'hass':self.hass,'datetime':datetime,'timezone':timezone,'timedelta':timedelta,'persist':persist,'deliver':deliver,'authorized':authorized,'Context':lambda:None,'queue_mail':lambda *v:None,'_num':lambda s,u:float(s.state),'async_call_later':timer,'low_power_callback':lambda now:None,'CONF_SWITCH':'switch','CONF_ENERGY':'energy','CONF_POWER':'power','CONF_USERS':'users','CONF_RATE':'rate','CONF_IDLE_W':'idle','CONF_IDLE_SECONDS':'seconds'}
        tree=ast.parse(SOURCE.read_text());setup=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='async_setup_entry')
        names=['start_session','ws_start','ws_schedule','ws_cancel_schedule','scheduled_tick','power_changed']
        functions=[n for n in setup.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in names]
        for n in functions:n.decorator_list=[]
        exec(compile(ast.Module(body=functions,type_ignores=[]),str(SOURCE),'exec'),self.ns)
    async def command(self,name,**kwargs):
        await self.ns[name](self.hass,self.connection,{'id':1,**kwargs})
    async def reserve(self):
        await self.command('ws_schedule',start_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())
    def due(self):
        self.data['reservation']['start_at']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    async def test_reserve_edit_cancel_and_no_switch_activation(self):
        await self.reserve();self.assertEqual(self.data['reservation']['user_id'],'one');self.assertFalse(self.calls)
        await self.reserve();self.assertFalse(self.errors)
        await self.command('ws_cancel_schedule');self.assertIsNone(self.data['reservation'])
    async def test_other_user_cannot_start_edit_or_cancel(self):
        await self.reserve();self.connection.user=NS(id='two',is_admin=False,name='Two')
        await self.command('ws_start');await self.reserve();await self.command('ws_cancel_schedule')
        self.assertEqual(len(self.errors),3);self.assertFalse(self.calls);self.assertEqual(self.data['reservation']['user_id'],'one')
    async def test_admin_start_now_preserves_owner_and_counts_from_activation(self):
        await self.reserve();self.connection.user=NS(id='admin',is_admin=True)
        await self.command('ws_start');self.assertFalse(self.errors)
        self.assertEqual(self.data['active']['user_id'],'one');self.assertEqual(self.data['active']['start_kwh'],42)
        self.assertIsNone(self.data['reservation']);self.assertEqual(len(self.calls),1);self.assertFalse(self.timers)
    async def test_restore_due_and_no_load_wait_has_no_timer(self):
        await self.reserve();await self.ns['scheduled_tick']();self.assertFalse(self.calls)
        self.due();await self.ns['scheduled_tick']();await self.ns['scheduled_tick']()
        self.assertEqual(len(self.calls),1);self.assertFalse(self.timers)
        self.ns['power_changed'](NS(data={'new_state':self.power}));self.assertFalse(self.timers)
        self.power.state='101';self.ns['power_changed'](NS(data={'new_state':self.power}))
        self.assertTrue(self.data['active']['has_load'])
        self.power.state='0';self.ns['power_changed'](NS(data={'new_state':self.power}));self.assertEqual(len(self.timers),1)
    async def test_failure_retains_reservation_then_retry_succeeds(self):
        await self.reserve();self.due()
        async def fail(*a,**k):raise RuntimeError('Switch unavailable')
        original=self.hass.services.async_call;self.hass.services.async_call=fail
        await self.ns['scheduled_tick']();self.assertIsNotNone(self.data['reservation']);self.assertIsNone(self.data['active'])
        self.assertEqual(self.data['schedule_error'],'Switch unavailable');self.assertFalse(self.data['starting'])
        self.data['schedule_retry_after']=None;self.hass.services.async_call=original;await self.ns['scheduled_tick']();self.assertIsNotNone(self.data['active'])
    async def test_past_naive_and_invalid_times_rejected(self):
        for value in ['broken','2026-01-01T10:00:00', (datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()]:
            await self.command('ws_schedule',start_at=value)
        self.assertEqual(len(self.errors),3);self.assertIsNone(self.data['reservation'])
    async def test_disabled_owner_and_unload_do_not_launch(self):
        await self.reserve();self.due();self.user.is_active=False
        await self.ns['scheduled_tick']();self.assertFalse(self.calls);self.assertIsNotNone(self.data['reservation'])
        self.user.is_active=True;self.data['stopped']=True
        await self.ns['scheduled_tick']();self.assertFalse(self.calls)
    async def test_immediate_start_keeps_existing_idle_timer(self):
        await self.command('ws_start');self.assertEqual(len(self.timers),1)
