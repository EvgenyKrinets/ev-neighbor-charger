const EV_TEXT = {
 en: ['EV charging','Available','Charging','Charger occupied','Start charging','Energy','Cost','Power','History','Start','End','User','Total','Email reports','Email','Save','Saved','Configure SMTP in integration options to enable emails.','No sessions yet','Loading…','Refresh failed','Charging failed','Report language','Low power automatic shutoff','Switch turned off','Completed','Duration (min)','Email delivery failed; retry pending'],
 ru: ['EV зарядка','Свободно','Идёт зарядка','Зарядка занята','Начать зарядку','Энергия','Стоимость','Мощность','История','Начало','Окончание','Пользователь','Всего','Отчёты по почте','Электронная почта','Сохранить','Сохранено','Настройте SMTP в параметрах интеграции для отправки писем.','Зарядок пока нет','Загрузка…','Ошибка обновления','Ошибка запуска','Язык отчётов','Автоотключение: низкая мощность','Выключатель отключён','Завершено','Длительность (мин)','Ошибка отправки почты; ожидается повтор'],
 he: ['טעינת רכב','פנוי','טעינה פעילה','המטען תפוס','התחלת טעינה','אנרגיה','עלות','הספק','היסטוריה','התחלה','סיום','משתמש','סך הכול','דוחות בדוא״ל','דוא״ל','שמירה','נשמר','יש להגדיר SMTP בהגדרות האינטגרציה לשליחת הודעות.','אין עדיין טעינות','טוען…','עדכון נכשל','התחלת טעינה נכשלה','שפת הדוחות','כיבוי אוטומטי עקב הספק נמוך','המתג כובה','הושלם','משך (דקות)','שליחת דוא״ל נכשלה; ניסיון חוזר ממתין']
};
class EVNeighborChargerPanel extends HTMLElement {
 set hass(hass) {
  const previous=this._hass; this._hass=hass;
  if(!this.isConnected)return;
  if(!this._data || previous?.connection!==hass.connection) this._refresh();
  else this._renderStats();
 }
 set panel(panel){this._panel=panel;}
 connectedCallback(){this._refresh();this._timer=setInterval(()=>this._refresh(),2000);}
 disconnectedCallback(){clearInterval(this._timer);this._requestGeneration=(this._requestGeneration||0)+1;}
 _language(){const l=(this._lang||this._hass?.language||'en').split('-')[0];return EV_TEXT[l]?l:'en';}
 async _refresh(){
  if(!this._hass?.connection||this._loading||!this.isConnected)return;
  this._loading=true;const generation=this._requestGeneration||0;
  try{
   const d=await this._hass.connection.sendMessagePromise({type:'ev_neighbor_charger/get'});
   if(!this._data&&!this._lang&&d.profile?.language)this._lang=d.profile.language;
   if(!this.isConnected||generation!==(this._requestGeneration||0))return;
   const changed=JSON.stringify([d.active?.start,d.busy,d.sessions,d.profile,d.email_enabled,d.mail_error,d.can_start,d.is_admin])!==JSON.stringify([this._data?.active?.start,this._data?.busy,this._data?.sessions,this._data?.profile,this._data?.email_enabled,this._data?.mail_error,this._data?.can_start,this._data?.is_admin]);
   this._data=d;this._error='';if(changed||!this.querySelector('#live'))this._render();else this._renderStats();
  }catch(e){this._error=e.message||EV_TEXT[this._language()][20];this._showMessage();}finally{this._loading=false;}
 }
 async _start(){
  const button=this.querySelector('#start');if(button)button.disabled=true;
  try{await this._hass.connection.sendMessagePromise({type:'ev_neighbor_charger/start'});await this._refresh();}
  catch(e){this._error=e.message||EV_TEXT[this._language()][21];this._showMessage();}
  finally{if(button&&button.isConnected)button.disabled=!!this._data?.busy||!this._data?.can_start;}
 }
 async _save(){
  try{await this._hass.connection.sendMessagePromise({type:'ev_neighbor_charger/profile',email:this.querySelector('#email').value,language:this._language()});this._draft=null;await this._refresh();this._error=EV_TEXT[this._language()][16];this._showMessage();}
  catch(e){this._error=e.message;this._showMessage();}
 }
 _showMessage(){const node=this.querySelector('#message');if(node)node.textContent=this._error||'';}
 _renderStats(){
  const node=this.querySelector('#live');if(!node||!this._data)return;
  const d=this._data,a=d.active,t=EV_TEXT[this._language()];
  // hass entity state updates arrive over Home Assistant's WebSocket.
  const energyState=this._hass.states[d.entities?.energy],powerState=this._hass.states[d.entities?.power];
  const energyValue=Number(energyState?.state),powerValue=Number(powerState?.state);
  const currentEnergy=energyState?(Number.isFinite(energyValue)?energyValue/(energyState.attributes.unit_of_measurement==='Wh'?1000:1):null):d.energy_kwh;
  const power=powerState?(Number.isFinite(powerValue)?powerValue*(powerState.attributes.unit_of_measurement==='kW'?1000:1):null):d.power_w;
  const used=a&&currentEnergy!=null?Math.max(0,currentEnergy-a.start_kwh):0;
  node.innerHTML=`<div><small>${t[5]}</small><strong>${used.toFixed(3)} kWh</strong></div><div><small>${t[6]}</small><strong>₪${(used*(a?.rate||d.rate||0)).toFixed(2)}</strong></div><div><small>${t[7]}</small><strong>${power==null?'—':power.toFixed(0)} W</strong></div>`;
 }
 _render(){
  if(!this.isConnected||!this._hass)return;
  const old=this.querySelector('#email');if(old)this._draft=old.value;
  const d=this._data||{},lang=this._language(),t=EV_TEXT[lang],a=d.active,esc=v=>this._esc(v),date=v=>v?new Date(v).toLocaleString(lang==='he'?'he-IL':lang==='ru'?'ru-RU':'en-GB'):'—';
  const rows=(d.sessions||[]).map(s=>`<tr><td>${esc(date(s.start))}</td><td>${esc(date(s.end))}</td>${d.is_admin?`<td>${esc(s.name)}</td>`:''}<td>${((new Date(s.end)-new Date(s.start))/60000).toFixed(1)}</td><td>${s.energy_kwh}</td><td>₪${Number(s.cost).toFixed(2)}</td></tr>`).join('');
  this.innerHTML=`<style>
  ev-neighbor-charger-panel{display:block;color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family,Arial)} .evwrap{max-width:1000px;margin:auto;padding:24px}.evtop{display:flex;align-items:center;justify-content:space-between;gap:12px}h1{font-size:26px}.card{background:var(--card-background-color,#fff);border-radius:18px;padding:22px;margin:18px 0;box-shadow:0 2px 8px #0001}.stats{display:flex;gap:24px;flex-wrap:wrap}.stats div{flex:1;min-width:120px}small{display:block;color:var(--secondary-text-color)}strong{display:block;font-size:28px;margin-top:8px}button{border:0;border-radius:12px;padding:14px 22px;background:var(--primary-color,#03a9f4);color:white;cursor:pointer}button:disabled{opacity:.45;cursor:default}input,select{padding:12px;border-radius:10px;border:1px solid var(--divider-color,#ddd);background:var(--card-background-color,#fff);color:inherit}input{max-width:100%;box-sizing:border-box;width:320px}.form{display:flex;gap:12px;flex-wrap:wrap;align-items:center}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;white-space:nowrap}td,th{text-align:start;padding:12px;border-bottom:1px solid var(--divider-color,#eee)}.status{color:var(--primary-color)}#message{color:var(--error-color,#d44)}@media(max-width:600px){.evwrap{padding:12px}.card{padding:16px}h1{font-size:22px}}
  </style><main class="evwrap" dir="${lang==='he'?'rtl':'ltr'}"><div class="evtop"><h1>⚡ ${t[0]}</h1><select id="language" aria-label="${t[22]}">${[['ru','Русский'],['en','English'],['he','עברית']].map(([k,v])=>`<option value="${k}" ${k===lang?'selected':''}>${v}</option>`).join('')}</select></div><div id="message" role="status">${esc(this._error||'')}</div>
  <section class="card"><h2 class="status">${!this._data?t[19]:a?t[2]:d.busy?t[3]:t[1]}</h2>${a?`<p>${t[9]}: ${esc(date(a.start))}</p>`:''}<div id="live" class="stats"></div><p>₪${Number(d.rate||0).toFixed(2)} / kWh</p><button id="start" ${d.busy||!d.can_start?'disabled':''}>${t[4]}</button></section>
  ${d.can_start?`<section class="card"><h2>${t[13]}</h2><div class="form"><label>${t[14]}<br><input id="email" type="email" dir="ltr" autocomplete="email" value="${esc(this._draft??d.profile?.email??'')}"></label><button id="save">${t[15]}</button></div><p>${t[22]}: ${lang==='he'?'עברית':lang==='ru'?'Русский':'English'}</p>${!d.email_enabled?`<p>${t[17]}</p>`:''}${d.mail_error?`<p>${t[27]}</p>`:''}</section>`:''}
  <section class="card"><h2>${t[12]}</h2><div class="stats"><div><small>${t[5]}</small><strong>${Number(d.totals?.kwh||0).toFixed(3)} kWh</strong></div><div><small>${t[6]}</small><strong>₪${Number(d.totals?.cost||0).toFixed(2)}</strong></div></div></section>
  <section class="card"><h2>${t[8]}</h2><div class="scroll"><table><thead><tr><th>${t[9]}</th><th>${t[10]}</th>${d.is_admin?`<th>${t[11]}</th>`:''}<th>${t[26]}</th><th>kWh</th><th>₪</th></tr></thead><tbody>${rows||`<tr><td colspan="6">${t[18]}</td></tr>`}</tbody></table></div></section></main>`;
  this.querySelector('#language').onchange=e=>{this._lang=e.target.value;this._render();};
  this.querySelector('#start').onclick=()=>this._start();
  const save=this.querySelector('#save');if(save)save.onclick=()=>this._save();this._renderStats();
 }
 _esc(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
}
if(!customElements.get('ev-neighbor-charger-panel'))customElements.define('ev-neighbor-charger-panel',EVNeighborChargerPanel);
