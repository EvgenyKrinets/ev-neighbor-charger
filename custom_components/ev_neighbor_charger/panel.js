const EV_TEXT = {
 en: ['EV charging','Available','Charging','Charger occupied','Start charging','Energy','Cost','Power','History','Start','End','User','Total','Email reports','Email','Save','Saved','Configure SMTP in integration options to enable emails.','No sessions yet','Loading…','Refresh failed','Charging failed','Report language','Low power automatic shutoff','Switch turned off','Completed','Duration (min)','Email delivery failed; retry pending'],
 ru: ['EV зарядка','Свободно','Идёт зарядка','Зарядка занята','Начать зарядку','Энергия','Стоимость','Мощность','История','Начало','Окончание','Пользователь','Всего','Отчёты по почте','Электронная почта','Сохранить','Сохранено','Настройте SMTP в параметрах интеграции для отправки писем.','Зарядок пока нет','Загрузка…','Ошибка обновления','Ошибка запуска','Язык отчётов','Автоотключение: низкая мощность','Выключатель отключён','Завершено','Длительность (мин)','Ошибка отправки почты; ожидается повтор'],
 he: ['טעינת רכב','פנוי','טעינה פעילה','המטען תפוס','התחלת טעינה','אנרגיה','עלות','הספק','היסטוריה','התחלה','סיום','משתמש','סך הכול','דוחות בדוא״ל','דוא״ל','שמירה','נשמר','יש להגדיר SMTP בהגדרות האינטגרציה לשליחת הודעות.','אין עדיין טעינות','טוען…','עדכון נכשל','התחלת טעינה נכשלה','שפת הדוחות','כיבוי אוטומטי עקב הספק נמוך','המתג כובה','הושלם','משך (דקות)','שליחת דוא״ל נכשלה; ניסיון חוזר ממתין']
};
const EV_EXTRA = {
 ru: {scheduled:'Зарядка запланирована',schedule:'Запланировать зарядку',when:'Дата и время запуска',confirm:'Сохранить время',cancel:'Отменить бронь',edit:'Изменить время',now:'Начать сейчас',close:'Закрыть',future:'Выбери дату и время в будущем',local:'Время на этом устройстве',preparing:'Подготовка к зарядке',finishing:'Окончание зарядки',unavailable:'Мощность недоступна',menu:'Меню Home Assistant',period:'Период',all:'Всё время',day:'Сегодня',week:'Последние 7 дней',month:'Текущий месяц',year:'Текущий год',name:'Поиск по имени'},
 en: {scheduled:'Charging scheduled',schedule:'Schedule charging',when:'Start date and time',confirm:'Save time',cancel:'Cancel reservation',edit:'Change time',now:'Start now',close:'Close',future:'Choose a future date and time',local:'Time on this device',preparing:'Preparing to charge',finishing:'Finishing charging',unavailable:'Power unavailable',menu:'Home Assistant menu',period:'Period',all:'All time',day:'Today',week:'Last 7 days',month:'This month',year:'This year',name:'Search by name'},
 he: {scheduled:'טעינה מתוזמנת',schedule:'תזמון טעינה',when:'תאריך ושעת התחלה',confirm:'שמירת השעה',cancel:'ביטול הזמנה',edit:'שינוי השעה',now:'התחלה עכשיו',close:'סגירה',future:'יש לבחור תאריך ושעה בעתיד',local:'השעה במכשיר זה',preparing:'הכנה לטעינה',finishing:'סיום טעינה',unavailable:'ההספק אינו זמין',menu:'תפריט Home Assistant',period:'תקופה',all:'כל הזמן',day:'היום',week:'7 הימים האחרונים',month:'החודש הנוכחי',year:'השנה הנוכחית',name:'חיפוש לפי שם'}
};
class EVNeighborChargerPanel extends HTMLElement {
 set hass(hass) {
  const previous=this._hass; this._hass=hass;
  if(!this.isConnected)return;
  if(previous?.connection!==hass.connection){this._resetConnection();this._refresh();}
  this._subscribe();
 }
 set panel(panel){this._panel=panel;}
 connectedCallback(){
  this._resume=()=>{if(document.visibilityState!=='hidden'){this._resetConnection();this._subscribe();this._refresh();}};
  document.addEventListener('visibilitychange',this._resume);
  window.addEventListener('pageshow',this._resume);
  window.addEventListener('online',this._resume);
  this._subscribe();this._refresh();
  this._timer=setInterval(()=>{this._subscribe();this._refresh();},2000);
 }
 disconnectedCallback(){
  clearInterval(this._timer);this._resetConnection();
  document.removeEventListener('visibilitychange',this._resume);
  window.removeEventListener('pageshow',this._resume);
  window.removeEventListener('online',this._resume);
 }
 _resetConnection(){
  this._requestGeneration=(this._requestGeneration||0)+1;
  this._loading=null;this._subscribing=null;
  const unsub=this._unsubscribe;this._unsubscribe=null;
  if(unsub)Promise.resolve().then(unsub).catch(()=>{});
 }
 _language(){const l=(this._lang||this._hass?.language||'en').split('-')[0];return EV_TEXT[l]?l:'en';}
 async _subscribe(){
  const connection=this._hass?.connection;
  if(!connection||!this.isConnected||this._unsubscribe||this._subscribing)return;
  const generation=this._requestGeneration||0,token={};this._subscribing=token;
  // A stalled subscription must not prevent retries forever.
  const timeout=setTimeout(()=>{if(this._subscribing===token)this._subscribing=null;},10000);
  try{
   const unsub=await connection.subscribeMessage(d=>{
    if(this._subscribing!==token&&this._subscriptionToken!==token)return;
    if(!this.isConnected||generation!==(this._requestGeneration||0))return;
    if(d.reload){this._resetConnection();return;}
    this._pushRevision=(this._pushRevision||0)+1;this._accept(d);
   },{type:'ev_neighbor_charger/subscribe'});
   if(!this.isConnected||generation!==(this._requestGeneration||0)||this._subscribing!==token){await unsub();return;}
   this._subscriptionToken=token;this._unsubscribe=unsub;
  }catch(e){/* Polling remains available while the integration reconnects. */}
  finally{clearTimeout(timeout);if(this._subscribing===token)this._subscribing=null;}
 }
 _accept(d){
  if(!this._data&&!this._lang&&d.profile?.language)this._lang=d.profile.language;
  const structural=x=>JSON.stringify([x?.reservation,x?.can_manage_reservation,x?.schedule_error,x?.active?.start,x?.owner,x?.active?.name,x?.busy,x?.sessions,x?.profile,x?.email_enabled,x?.mail_error,x?.can_start,x?.is_admin,x?.version]);
  const changed=structural(d)!==structural(this._data);
  this._data=d;this._error='';
  if(changed||!this.querySelector('#live'))this._render();else this._renderStats();
  this._showMessage();
 }
 async _refresh(){
  if(!this._hass?.connection||this._loading||!this.isConnected)return;
  const token={};this._loading=token;
  const generation=this._requestGeneration||0,revision=this._pushRevision||0;
  let timeout;
  try{
   const d=await Promise.race([
    this._hass.connection.sendMessagePromise({type:'ev_neighbor_charger/get'}),
    new Promise((_,reject)=>{timeout=setTimeout(()=>reject(new Error(EV_TEXT[this._language()][20])),10000);})
   ]);
   if(!this.isConnected||generation!==(this._requestGeneration||0))return;
   // An older poll response must not overwrite a newer pushed reading.
   if(revision===(this._pushRevision||0))this._accept(d);
  }catch(e){
   if(this.isConnected&&generation===(this._requestGeneration||0)&&revision===(this._pushRevision||0)){
    this._error=e.message||EV_TEXT[this._language()][20];this._showMessage();
   }
  }finally{clearTimeout(timeout);if(this._loading===token)this._loading=null;}
 }
 async _start(){
  if(this._starting)return;
  this._editingSchedule=false;this._starting=true;this._render();
  try{await this._hass.connection.sendMessagePromise({type:'ev_neighbor_charger/start'});await this._refresh();}
  catch(e){this._error=e.message||EV_TEXT[this._language()][21];}
  finally{this._starting=false;this._render();this._showMessage();}
 }
 _openSchedule(){
  this._editingSchedule=true;
  const date=new Date(this._data?.reservation?.start_at||Date.now()+3600000);
  this._scheduleDraft=new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);
  this._render();
 }
 async _scheduleAction(cancel=false){
  if(this._schedulePending)return;
  const x=EV_EXTRA[this._language()];
  const date=new Date(this._scheduleDraft);
  if(!cancel&&(!Number.isFinite(date.getTime())||date<=new Date())){this._error=x.future;this._showMessage();return;}
  this._schedulePending=true;
  try{
   await this._hass.connection.sendMessagePromise(cancel?{type:'ev_neighbor_charger/cancel_schedule'}:{type:'ev_neighbor_charger/schedule',start_at:date.toISOString()});
   this._editingSchedule=false;
   this._error='';await this._refresh();
  }catch(e){this._error=e.message||String(e);}
  finally{this._schedulePending=false;this._render();this._showMessage();}
 }
 async _save(){
  const email=this.querySelector('#email').value.trim(),language=this._language();
  try{
   await this._hass.connection.sendMessagePromise({type:'ev_neighbor_charger/profile',email,language});
   // Update immediately even if a background refresh is already pending.
   this._data={...this._data,profile:{email,language}};
   this._editingEmail=false;this._draft=null;this._error='';this._render();
  }catch(e){this._error=e.message;this._showMessage();}
 }
 _showMessage(){const node=this.querySelector('#message');if(node)node.textContent=this._error||'';}
 _openEmailSettings(){
  this._editingEmail=true;
  this._render();
  const email=this.querySelector('#email');
  if(email){
   email.scrollIntoView?.({behavior:'smooth',block:'center'});
   email.focus?.({preventScroll:true});
  }
 }
 _statusText(){
  const d=this._data,t=EV_TEXT[this._language()],x=EV_EXTRA[this._language()];
  if(!d)return t[19];
  if(this._starting)return x.preparing;
  if(!d.busy)return t[1];
  return x[d.charge_phase]||(d.charge_phase==='charging'?t[2]:(d.active?t[2]:t[3]));
 }
 _toggleMenu(){
  const narrow=this.narrow??window.matchMedia?.('(max-width: 870px)').matches??false;
  if(this._data?.is_admin)this.dispatchEvent(new CustomEvent('hass-toggle-menu',{bubbles:true,composed:true,detail:narrow?undefined:{open:true}}));
 }
 _filteredSessions(now=new Date()){
  let since=null;
  if(this._historyPeriod==='day'){since=new Date(now);since.setHours(0,0,0,0);}
  if(this._historyPeriod==='week'){since=new Date(now);since.setHours(0,0,0,0);since.setDate(since.getDate()-6);}
  if(this._historyPeriod==='month')since=new Date(now.getFullYear(),now.getMonth(),1);
  if(this._historyPeriod==='year')since=new Date(now.getFullYear(),0,1);
  const name=(this._historyName||'').trim().toLocaleLowerCase();
  return (this._data?.sessions||[]).filter(s=>{
   const start=new Date(s.start);
   return (!since||(start>=since&&start<=now))&&(!name||String(s.name||'').toLocaleLowerCase().includes(name));
  });
 }
 _renderHistory(){
  const node=this.querySelector('#history-rows');if(!node)return;
  const lang=this._language(),t=EV_TEXT[lang],esc=v=>this._esc(v),date=v=>v?new Date(v).toLocaleString(lang==='he'?'he-IL':lang==='ru'?'ru-RU':'en-GB'):'—';
  const sessions=this._filteredSessions();
  node.innerHTML=sessions.map(s=>`<tr><td>${esc(date(s.start))}</td><td>${esc(date(s.end))}</td>${this._data?.is_admin?`<td>${esc(s.name)}</td>`:''}<td>${((new Date(s.end)-new Date(s.start))/60000).toFixed(1)}</td><td>${s.energy_kwh}</td><td>₪${Number(s.cost).toFixed(2)}</td></tr>`).join('')||`<tr><td colspan="6">${t[18]}</td></tr>`;
  const total=this.querySelector('#history-total');
  if(total){
   const sum=sessions.reduce((a,s)=>({minutes:a.minutes+Math.max(0,(new Date(s.end)-new Date(s.start))/60000||0),kwh:a.kwh+(Number(s.energy_kwh)||0),cost:a.cost+(Number(s.cost)||0)}),{minutes:0,kwh:0,cost:0});
   total.innerHTML=`<tr><td colspan="${this._data?.is_admin?3:2}">${t[12]}</td><td>${sum.minutes.toFixed(1)}</td><td>${sum.kwh.toFixed(3)}</td><td>₪${sum.cost.toFixed(2)}</td></tr>`;
  }
 }
 _renderStats(){
  const node=this.querySelector('#live');if(!node||!this._data)return;
  const d=this._data,a=d.active,t=EV_TEXT[this._language()];
  const status=this.querySelector('#charge-status');if(status)status.textContent=this._statusText();
  // Only use authoritative readings from this integration's server snapshot.
  // hass.states can be stale after a mobile reconnect and must not override them.
  const currentEnergy=d.energy_kwh,power=d.power_w;
  const used=a?(currentEnergy==null?null:Math.max(0,currentEnergy-a.start_kwh)):0;
  node.innerHTML=`<div class="metric power"><small>${t[7]}</small><strong>${power==null?'—':power.toFixed(0)} <span>W</span></strong><div class="metric-detail">${power==null?'—':(power/1000).toFixed(2)} kW</div></div><div class="metric"><small>${t[5]}</small><strong>${used==null?'—':used.toFixed(3)} <span>kWh</span></strong></div><div class="metric"><small>${t[6]}</small><strong><span>₪</span>${used==null?'—':(used*(a?.rate??d.rate??0)).toFixed(2)}</strong></div>`;

 }
 _render(){
  if(!this.isConnected||!this._hass)return;
  const old=this.querySelector('#email');if(old)this._draft=old.value;
  const d=this._data||{},lang=this._language(),t=EV_TEXT[lang],x=EV_EXTRA[lang],a=d.active,esc=v=>this._esc(v),date=v=>v?new Date(v).toLocaleString(lang==='he'?'he-IL':lang==='ru'?'ru-RU':'en-GB'):'—';
  this.innerHTML=`<style>
  ev-neighbor-charger-panel{display:block;color:var(--primary-text-color,#172a35);font-family:var(--paper-font-body1_-_font-family,Arial);--ev-accent:#0baf91;--ev-border:var(--divider-color,#dce6e9)}
  .history-filters{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-end;margin-bottom:16px}.history-filters select{margin-top:7px}.settings-button{background:transparent;color:var(--secondary-text-color);border:1px solid var(--ev-border);padding:8px 13px;font-size:21px}.evtop{flex-wrap:wrap;direction:ltr} *{box-sizing:border-box}.evwrap{max-width:1080px;margin:auto;padding:28px 24px 56px}.evtop{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:26px}h1{display:flex;align-items:center;gap:12px;font-size:24px;margin:0;letter-spacing:-.5px}.brand-icon{width:48px;height:48px;object-fit:contain;border-radius:14px}.version{font-size:11px;font-weight:500;border:1px solid var(--ev-border);border-radius:20px;padding:4px 8px;letter-spacing:0}h2{font-size:18px;margin:0 0 20px}.card{background:var(--card-background-color,#fff);border:1px solid var(--ev-border);border-radius:24px;padding:28px;margin:18px 0;box-shadow:0 5px 22px #102b3610}.charge-card{position:relative;overflow:hidden;background:linear-gradient(125deg,#0baf9112,transparent 65%),var(--card-background-color,#fff);border-color:#0baf9140}.charge-card:before{content:"";position:absolute;top:0;inset-inline:0;height:4px;background:linear-gradient(90deg,#0baf91,#4abade)}.status{display:inline-flex;align-items:center;gap:9px;padding:8px 13px;border-radius:30px;background:#0baf9118;color:var(--primary-text-color);font-size:13px;margin:0;font-weight:650}.status:before{content:"";width:8px;height:8px;border-radius:50%;background:var(--ev-accent);box-shadow:0 0 0 4px #0baf9112}.charging-owner{margin:22px 0 12px}.owner-label{font-size:12px;text-transform:uppercase;letter-spacing:1.4px;color:var(--secondary-text-color);margin-bottom:8px}.owner-name{display:block;font-size:clamp(30px,6vw,48px);font-weight:800;line-height:1.15;letter-spacing:-1px;overflow-wrap:anywhere}.session-start{color:var(--secondary-text-color);font-size:13px;margin:12px 0 26px}.stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:24px 0}.metric{border:1px solid var(--ev-border);border-radius:18px;padding:22px 18px;background:var(--card-background-color,#fff);min-width:0}.metric.power{background:#0baf9110;border-color:#0baf9135}small{display:block;color:var(--secondary-text-color);font-size:13px}strong{display:block;font-size:clamp(25px,3.5vw,39px);font-weight:750;margin-top:12px;letter-spacing:-1px;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}strong span{font-size:15px;font-weight:500;letter-spacing:0;color:var(--secondary-text-color)}.metric-detail{font-size:13px;margin-top:8px;color:var(--secondary-text-color)}.session-footer{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}.rate{font-size:13px;color:var(--secondary-text-color)}button{border:0;border-radius:13px;padding:15px 24px;background:var(--ev-accent);color:#fff;font-size:15px;font-weight:650;cursor:pointer;min-height:48px;transition:filter .2s}button:hover{filter:brightness(.94)}button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid var(--primary-color,#03a9f4);outline-offset:3px}button:disabled{opacity:.45;cursor:default}input,select{padding:12px;border-radius:12px;border:1px solid var(--ev-border);background:var(--card-background-color,#fff);color:inherit;font-size:15px;min-height:46px}input{width:320px;max-width:100%;margin-top:7px}.form{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end}label{font-size:13px;color:var(--secondary-text-color)}.summary-stats{grid-template-columns:repeat(2,minmax(0,1fr));margin-bottom:0}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;white-space:nowrap;font-size:13px}td,th{text-align:start;padding:15px 12px;border-bottom:1px solid var(--ev-border)}th{color:var(--secondary-text-color);font-weight:500}tbody tr:last-child td{border:0}tfoot td{font-weight:700;background:#0baf9110;border-top:2px solid var(--ev-border);border-bottom:0}#message{color:var(--error-color,#d44);font-size:14px}.mail-note{color:var(--secondary-text-color);font-size:13px;line-height:1.6}.section-title{display:flex;align-items:center;gap:10px}.section-title:before{content:"";width:4px;height:18px;border-radius:4px;background:var(--ev-accent)}
  @media(max-width:640px){.evwrap{padding:18px 12px 36px}.evtop{gap:8px;margin-bottom:18px;align-items:flex-start}h1{font-size:19px;flex-wrap:wrap;gap:8px}.brand-icon{width:36px;height:36px}.version{font-size:10px}#language{max-width:105px;font-size:13px;padding:9px}.card{padding:22px 16px;border-radius:20px}.stats{gap:8px}.metric{padding:16px 10px;border-radius:14px}strong{font-size:27px}strong span{display:block;font-size:12px;margin-top:5px}small{font-size:12px}.owner-name{font-size:36px}.session-footer button{width:100%}.form label,.form input{width:100%}.form button{width:100%}.metric-detail{font-size:11px}.summary-stats strong{font-size:25px}}

  </style><main class="evwrap" dir="${lang==='he'?'rtl':'ltr'}"><div class="evtop">${d.is_admin?`<button id="ha-menu" class="settings-button" aria-label="${esc(x.menu)}">☰</button>`:''}<h1><img class="brand-icon" src="/ev_neighbor_charger/icon.png" alt=""> ${t[0]} <small class="version">v${esc(d.version||'…')}</small></h1>${d.can_start?`<button class="settings-button" id="profile-settings" aria-label="${lang==='ru'?'Настройки почты':lang==='he'?'הגדרות דוא״ל':'Email settings'}">@</button>`:''}<select id="language" aria-label="${t[22]}">${[['ru','Русский'],['en','English'],['he','עברית']].map(([k,v])=>`<option value="${k}" ${k===lang?'selected':''}>${v}</option>`).join('')}</select></div><div id="message" role="status">${esc(this._error||'')}</div>
  <section class="card charge-card"><h2 class="status" id="charge-status">${esc(this._statusText())}</h2>${d.busy&&(d.owner||a?.name)?`<div class="charging-owner"><div class="owner-label">${t[11]}</div><bdi class="owner-name">${esc(d.owner||a?.name)}</bdi></div>`:''}${a?`<p class="session-start">${t[9]} · ${esc(date(a.start))}</p>`:''}${d.reservation?`<p class="session-start">${esc(x.when)} · <b>${esc(date(d.reservation.start_at))}</b></p>`:''}${d.schedule_error?`<p role="alert">${esc(d.schedule_error)}</p>`:''}<div id="live" class="stats"></div><div class="session-footer"><span class="rate">₪${Number(a?.rate??d.rate??0).toFixed(2)} / kWh</span>${!d.busy&&!this._starting?`<button id="start" ${!d.can_start?'disabled':''}>${t[4]} <span aria-hidden="true">↗</span></button><button id="schedule" ${!d.can_start?'disabled':''}>${esc(x.schedule)}</button>`:''}${d.can_manage_reservation?`<button id="start-now">${esc(x.now)}</button><button id="edit-schedule">${esc(x.edit)}</button><button id="cancel-schedule">${esc(x.cancel)}</button>`:''}</div>${this._editingSchedule&&(!d.busy||d.can_manage_reservation)?`<div class="form" style="margin-top:20px"><label>${esc(x.when)} (${esc(x.local)})<br><input id="schedule-time" type="datetime-local" value="${esc(this._scheduleDraft||'')}"></label><button id="save-schedule" ${this._schedulePending?'disabled':''}>${esc(x.confirm)}</button><button id="close-schedule">${esc(x.close)}</button></div>`:''}</section>

  ${d.can_start&&(!d.profile?.email||this._editingEmail)?`<section class="card"><h2 class="section-title">${t[13]}</h2><div class="form"><label>${t[14]}<br><input id="email" type="email" dir="ltr" autocomplete="email" value="${esc(this._draft??d.profile?.email??d.suggested_email??'')}"></label><button id="save">${t[15]}</button></div><p class="mail-note">${t[22]}: ${lang==='he'?'עברית':lang==='ru'?'Русский':'English'}</p>${!d.email_enabled?`<p>${t[17]}</p>`:''}${d.mail_error?`<p>${t[27]}</p>`:''}</section>`:''}
  <section class="card"><h2 class="section-title">${t[12]}</h2><div class="stats summary-stats"><div><small>${t[5]}</small><strong>${Number(d.totals?.kwh||0).toFixed(3)} kWh</strong></div><div><small>${t[6]}</small><strong>₪${Number(d.totals?.cost||0).toFixed(2)}</strong></div></div></section>
  <section class="card"><h2 class="section-title">${t[8]}</h2><div class="history-filters"><label>${x.period}<br><select id="history-period">${['all','day','week','month','year'].map(k=>`<option value="${k}" ${(this._historyPeriod||'all')===k?'selected':''}>${x[k]}</option>`).join('')}</select></label>${d.is_admin?`<label>${x.name}<br><input id="history-name" type="search" value="${esc(this._historyName||'')}" placeholder="${x.name}"></label>`:''}</div><div class="scroll"><table><thead><tr><th>${t[9]}</th><th>${t[10]}</th>${d.is_admin?`<th>${t[11]}</th>`:''}<th>${t[26]}</th><th>kWh</th><th>₪</th></tr></thead><tbody id="history-rows"></tbody><tfoot id="history-total"></tfoot></table></div></section></main>`;
  this.querySelector('#language').onchange=e=>{this._lang=e.target.value;this._render();};
  const menu=this.querySelector('#ha-menu');if(menu)menu.onclick=()=>this._toggleMenu();
  const period=this.querySelector('#history-period');if(period)period.onchange=e=>{this._historyPeriod=e.target.value;this._renderHistory();};
  const name=this.querySelector('#history-name');if(name)name.oninput=e=>{this._historyName=e.target.value;this._renderHistory();};
  this._renderHistory();
  const start=this.querySelector('#start');if(start)start.onclick=()=>this._start();
  for(const id of ['schedule','edit-schedule']){const b=this.querySelector('#'+id);if(b)b.onclick=()=>this._openSchedule();}
  const when=this.querySelector('#schedule-time');if(when)when.oninput=e=>{this._scheduleDraft=e.target.value;};
  const saveSchedule=this.querySelector('#save-schedule');if(saveSchedule)saveSchedule.onclick=()=>this._scheduleAction();
  const cancelSchedule=this.querySelector('#cancel-schedule');if(cancelSchedule)cancelSchedule.onclick=()=>this._scheduleAction(true);
  const closeSchedule=this.querySelector('#close-schedule');if(closeSchedule)closeSchedule.onclick=()=>{this._editingSchedule=false;this._render();};
  const startNow=this.querySelector('#start-now');if(startNow)startNow.onclick=()=>this._start();
  const save=this.querySelector('#save');if(save)save.onclick=()=>this._save();const settings=this.querySelector('#profile-settings');if(settings)settings.onclick=()=>this._openEmailSettings();this._renderStats();
 }
 _esc(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
}
if(!customElements.get('ev-neighbor-charger-panel'))customElements.define('ev-neighbor-charger-panel',EVNeighborChargerPanel);

