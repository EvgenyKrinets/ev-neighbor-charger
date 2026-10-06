const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const {test}=require('node:test');
const source=fs.readFileSync(require('node:path').join(__dirname,'../custom_components/ev_neighbor_charger/panel.js'),'utf8');
function setup(){
 let Panel;const timeouts=new Map();let id=0;
 const ctx={HTMLElement:class{},document:{visibilityState:'visible',addEventListener(){},removeEventListener(){}},window:{addEventListener(){},removeEventListener(){}},setTimeout:(f)=>{timeouts.set(++id,f);return id;},clearTimeout:i=>timeouts.delete(i),setInterval:()=>1,clearInterval(){},customElements:{get:()=>false,define:(n,c)=>Panel=c}};
 vm.runInNewContext(source,ctx);
 const p=new Panel();p.isConnected=true;p._hass={language:'ru',states:{},connection:{}};
 const nodes={'#live':{},'#message':{}};p.querySelector=k=>nodes[k]||null;p._render=()=>p._renderStats();
 return {p,nodes,timeouts};
}
const reading=(power=1234)=>({power_w:power,energy_kwh:12,active:{start:'now',start_kwh:10,rate:.65,name:'Neighbor'},owner:'Neighbor',busy:true,entities:{energy:'sensor.energy',power:'sensor.power'}});
test('server readings override stale frontend cache, and null energy is not zero',()=>{
 const {p,nodes}=setup();p._hass.states={'sensor.power':{state:'0',attributes:{}},'sensor.energy':{state:'10',attributes:{}}};
 p._accept(reading());assert.match(nodes['#live'].innerHTML.replace(/<[^>]*>/g,''),/1234 W/);assert.match(nodes['#live'].innerHTML.replace(/<[^>]*>/g,''),/2.000 kWh/);
 p._accept({...reading(),energy_kwh:null});assert.match(nodes['#live'].innerHTML.replace(/<[^>]*>/g,''),/— kWh/);
});
test('late poll cannot roll back a pushed reading',async()=>{
 const {p,nodes}=setup();let resolve;
 p._hass.connection.sendMessagePromise=()=>new Promise(r=>resolve=r);
 const pending=p._refresh();p._pushRevision=1;p._accept(reading(9000));resolve(reading(10));await pending;
 assert.match(nodes['#live'].innerHTML.replace(/<[^>]*>/g,''),/9000 W/);
});
test('a stalled request times out and allows another poll',async()=>{
 const {p,timeouts}=setup();p._hass.connection.sendMessagePromise=()=>new Promise(()=>{});
 const pending=p._refresh();for(const timeout of [...timeouts.values()])timeout();await pending;
 assert.equal(p._loading,null);p._hass.connection.sendMessagePromise=async()=>reading(2200);await p._refresh();assert.equal(p._data.power_w,2200);
});
test('reconnect discards old pending response and fetches new data',async()=>{
 const {p}=setup();let resolve;p._hass.connection.sendMessagePromise=()=>new Promise(r=>resolve=r);
 const old=p._refresh();p._resetConnection();p._hass.connection.sendMessagePromise=async()=>reading(7000);await p._refresh();resolve(reading(0));await old;assert.equal(p._data.power_w,7000);
});
test('push subscription updates immediately and unsubscribes on close',async()=>{
 const {p}=setup();let push,removed=0;p._hass.connection.subscribeMessage=async cb=>{push=cb;return ()=>{removed++;};};
 await p._subscribe();push(reading(3300));assert.equal(p._data.power_w,3300);
 p.isConnected=false;p.disconnectedCallback();await Promise.resolve();assert.equal(removed,1);
 push(reading(1));assert.equal(p._data.power_w,3300);
});

test('start button is hidden during charging and owner is prominent',()=>{
 const {p}=setup();delete p._render;p.querySelector=()=>({});p._data=reading();p._render();
 assert.doesNotMatch(p.innerHTML,/id="start"/);assert.match(p.innerHTML,/class="owner-name">Neighbor/);
 p._data={...reading(),busy:false,active:null,can_start:true};p._render();assert.match(p.innerHTML,/id="start"/);
 p._starting=true;p._render();assert.doesNotMatch(p.innerHTML,/id="start"/);
});
