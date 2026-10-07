// Navigation guard. Entity access is enforced separately by HA permissions.
(() => {
 let connection,userId,restricted=false,target='/ev-neighbor-charger',pending=false,checked=0;
 const styles=new Map();
 function restore(){for(const style of styles.values())style.remove();styles.clear();}
 function enforce(root){
  if(!root)return;
  if(root instanceof ShadowRoot&&!styles.has(root)){
   const style=document.createElement('style');
   style.textContent='ha-sidebar,app-header,ha-menu-button{display:none!important} ha-drawer{--mdc-drawer-width:0px!important}';
   root.append(style);styles.set(root,style);
  }
  for(const el of root.querySelectorAll('*'))if(el.shadowRoot)enforce(el.shadowRoot);
 }
 function guard(app){
  if(!restricted){restore();return;}
  if(location.pathname!==target){
   history.replaceState(null,'',target);
   window.dispatchEvent(new CustomEvent('location-changed',{detail:{replace:true}}));
  }
  enforce(app?.shadowRoot);
 }
 async function tick(){
  const app=document.querySelector('home-assistant'),hass=app?.hass;
  if(!hass?.connection||!hass.user){restricted=false;restore();connection=null;userId=null;checked=0;return;}
  if(connection!==hass.connection||userId!==hass.user.id){
   restricted=false;restore();connection=hass.connection;userId=hass.user.id;checked=0;
  }
  guard(app);
  if(pending||Date.now()-checked<10000)return;
  pending=true;const expected=connection,uid=userId;
  try{
   const access=await expected.sendMessagePromise({type:'ev_neighbor_charger/access'});
   if(expected===connection&&uid===userId){restricted=access.restricted;target=access.path;checked=Date.now();guard(app);}
  }catch{checked=0;}finally{pending=false;}
 }
 window.addEventListener('popstate',tick);
 window.addEventListener('location-changed',()=>{if(location.pathname!==target)tick();});
 window.addEventListener('pageshow',tick);
 setInterval(tick,1000);tick();
})();
