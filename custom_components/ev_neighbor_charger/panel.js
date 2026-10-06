class EVNeighborChargerPanel extends HTMLElement {
  set hass(hass) { this._hass = hass; this._render(); }
  set panel(panel) { this._panel = panel; this._render(); }
  connectedCallback() { this._refresh(); this._timer = setInterval(() => this._refresh(), 5000); }
  disconnectedCallback() { clearInterval(this._timer); }
  async _refresh() {
    if (!this._hass?.connection) return;
    try { this._data = await this._hass.connection.sendMessagePromise({type: "ev_neighbor_charger/get"}); this._render(); }
    catch (e) { this._error = e.message || "Не удалось загрузить данные"; this._render(); }
  }
  async _start() {
    this._error = "";
    try { await this._hass.connection.sendMessagePromise({type: "ev_neighbor_charger/start"}); await this._refresh(); }
    catch (e) { this._error = e.message || "Не удалось начать зарядку"; this._render(); }
  }
  _render() {
    if (!this._hass || !this.isConnected) return;
    const d = this._data || {};
    const a = d.active;
    const fmt = (n, digits=2) => Number(n || 0).toLocaleString("ru-RU", {maximumFractionDigits:digits});
    const ownKwh = a && d.energy_kwh != null ? Math.max(0, d.energy_kwh - Number(a.start_kwh || 0)) : 0;
    const ownCost = ownKwh * Number(a?.rate ?? d.rate ?? 0);
    const sessions = (d.sessions || []).map(s => `<tr><td>${new Date(s.start).toLocaleString("ru-RU")}</td><td>${this._esc(s.name)}</td><td>${fmt(s.energy_kwh)} кВт·ч</td><td>₪${fmt(s.cost)}</td></tr>`).join("");
    this.innerHTML = `<style>
      :host{display:block;color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family,Arial)}
      main{max-width:760px;margin:24px auto;padding:20px}h1{font-size:26px}.card{background:var(--card-background-color);border-radius:16px;padding:22px;margin:16px 0;box-shadow:var(--ha-card-box-shadow)}
      .status{font-size:22px;font-weight:600;margin-bottom:14px}.muted{color:var(--secondary-text-color)}button{border:0;border-radius:12px;background:var(--primary-color);color:white;padding:15px 24px;font-size:17px;font-weight:bold;cursor:pointer;width:100%}button[disabled]{opacity:.5;cursor:default}
      .stats{display:flex;gap:26px;flex-wrap:wrap}.stat strong{display:block;font-size:22px;margin-top:5px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;padding:10px 6px;border-bottom:1px solid var(--divider-color)}.error{color:var(--error-color);margin:12px 0}
    </style><main><h1>🚗 Зарядка автомобиля</h1>
      <section class="card"><div class="status">${a ? `🔴 Заряжает: ${this._esc(a.name)}` : d.busy ? `🔴 Занято${d.owner ? ` — ${this._esc(d.owner)}` : ""}` : "🟢 Зарядка свободна"}</div>
      ${a ? `<div class="stats"><div class="stat muted">Сейчас получено<strong>${fmt(ownKwh)} кВт·ч</strong></div><div class="stat muted">Стоимость<strong>₪${fmt(ownCost)}</strong></div><div class="stat muted">Мощность<strong>${fmt((d.power_w||0)/1000)} кВт</strong></div></div>` : ""}
      <div class="error">${this._esc(this._error || "")}</div><button id="start" ${d.busy || !d.can_start ? "disabled" : ""}>НАЧАТЬ ЗАРЯДКУ</button>
      ${!d.can_start ? `<p class="muted">Чтобы начать зарядку, администратор должен добавить тебя в список разрешённых пользователей.</p>` : ""}</section>
      <section class="card"><h2>Моя статистика</h2><div class="stats"><div class="stat muted">Всего энергии<strong>${fmt(d.totals?.kwh)} кВт·ч</strong></div><div class="stat muted">Всего к оплате<strong>₪${fmt(d.totals?.cost)}</strong></div></div></section>
      <section class="card"><h2>${d.is_admin ? "История зарядок" : "Мои зарядки"}</h2><div style="overflow:auto"><table><thead><tr><th>Начало</th>${d.is_admin?"<th>Пользователь</th>":""}<th>Энергия</th><th>Стоимость</th></tr></thead><tbody>${sessions || `<tr><td colspan="4" class="muted">Записей пока нет</td></tr>`}</tbody></table></div></section></main>`;
    this.querySelector("#start")?.addEventListener("click", () => this._start());
  }
  _esc(value) { return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }
}
if (!customElements.get("ev-neighbor-charger-panel")) customElements.define("ev-neighbor-charger-panel", EVNeighborChargerPanel);
