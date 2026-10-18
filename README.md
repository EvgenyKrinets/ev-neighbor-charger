<p align="center"><img src="https://raw.githubusercontent.com/EvgenyKrinets/ev-neighbor-charger/main/custom_components/ev_neighbor_charger/brand/logo.png" width="540" alt="EV Neighbor Charger"></p>

# EV Neighbor Charger

Share one EV charger through Home Assistant. Each allowed user starts their own session and sees energy, cost and history. Setup, access, automatic shutoff and email delivery are configured in the UI.

[![HACS validation](https://github.com/EvgenyKrinets/ev-neighbor-charger/actions/workflows/validate.yml/badge.svg)](https://github.com/EvgenyKrinets/ev-neighbor-charger/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/EvgenyKrinets/ev-neighbor-charger)](https://github.com/EvgenyKrinets/ev-neighbor-charger/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

<p align="center"><img src="https://raw.githubusercontent.com/EvgenyKrinets/ev-neighbor-charger/main/docs/ev-neighbor-charger-hero.jpg" width="100%" alt="Shared EV charging with a mobile control panel"></p>

*Presentation illustration; the actual panel is rendered inside Home Assistant.*

## Features

- One charger with a switch, cumulative energy meter (Wh/kWh) and power sensor (W/kW).
- UI configuration, tariff in ILS, selected Home Assistant users and automatic shutoff.
- Live power, session energy and cost, with preparing / charging / finishing states.
- History for today, last 7 calendar days, this month, this year or all time; admin name search and filtered duration, energy and cost totals.
- English, Russian and Hebrew, including right-to-left layout.
- Optional email for session start/end and monthly per-user reports with CSV attachments.
- SMTP presets for Gmail, Yahoo, iCloud, Brevo and Mailjet, plus custom SMTP. Test sending from integration settings.
- One instance per Home Assistant installation. Minimum Home Assistant: 2025.1.0.

## Install with HACS

The application for inclusion in the default HACS catalogue is being prepared. Until accepted, add this as a custom repository:

1. Open **HACS → ⋮ → Custom repositories**.
2. Add `https://github.com/EvgenyKrinets/ev-neighbor-charger`; category **Integration**.
3. Download **EV Neighbor Charger** and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → EV Neighbor Charger**.
5. Select the charger switch, energy and power sensors, tariff, allowed users and shutoff settings.
6. Open **EV зарядка** in the sidebar.

The charger must be off and the energy sensor numeric before starting a session. Settings can later be changed using **Settings → Devices & services → EV Neighbor Charger → Configure**. No YAML or external shutoff automation is needed.

## Automatic shutoff and accounting

The configured threshold is used both for the live status and the shutoff timer (defaults: **100 W, 120 seconds**).

After starting, the panel shows **Preparing to charge** until measured power exceeds the threshold. It then shows **Charging**. When power falls to/below the threshold it shows **Finishing charging** and the idle timer runs. Renewed load cancels the timer and returns to Charging. If the power sensor is unavailable, the panel shows that fact.

For an immediate start, the same idle timer also applies while preparing, so connect the vehicle within the configured delay. For scheduled starts, automatic low-power shutoff begins only after the first load above the threshold; there is no timeout while waiting for the vehicle. Only sessions started through this integration are managed. A completed session records its user, start/end, duration, energy difference, tariff, cost and stop reason.

Period filters use the viewing device's local timezone and session start date. Monthly reports use the Home Assistant timezone and session end date.

<p align="center"><img src="https://raw.githubusercontent.com/EvgenyKrinets/ev-neighbor-charger/main/docs/charging-flow.svg" width="100%" alt="Authorization, charging, automatic shutoff and session history"></p>

## User access

Administrators see all history and can open the normal Home Assistant menu. Allowed users see only their own charging history and save their own email through the **@** button.

The optional restriction removes selected non-admin users' general Home Assistant group permissions, saves their previous groups and restores them when a user is removed from the allowed list, restrictions are disabled, or the integration is removed. Authorized charging uses the integration's own authenticated commands.

A frontend navigation guard opens the charging page and hides normal navigation for restricted users. **This is not complete isolation from every Home Assistant API.** Use dedicated neighbor accounts and a separate portal if full API isolation is required. Administrators are never restricted.

## Email setup

Open **Configure → Outgoing email**, select a provider and enter its credentials. Use **Test sending**, choose or type a recipient, inspect the result, then save.

| Provider | Username | Password | Sender |
| --- | --- | --- | --- |
| Gmail / Yahoo / iCloud | Full email address | App password | Account email |
| Brevo | SMTP login from Brevo | SMTP key | Verified sender email |
| Mailjet | API Key | Secret Key | Verified sender email |
| Custom SMTP | SMTP username, if required | SMTP password | Sender email |

Gmail app passwords require Google two-step verification. Microsoft password-only SMTP is not supported; OAuth is required. Registration and sender verification take place on the provider's website.

Users save their recipient email and report language from the panel. Home Assistant local users have no separate email field; an email-shaped local username can be suggested, but must be confirmed by saving.

Start and end notifications include the session details available at that time. Monthly reports contain completed sessions from the previous month, totals and a CSV attachment. Missed months are caught up after restart; empty months are skipped. Failed mail stays in a local retry queue (checked every five minutes). SMTP acceptance does not guarantee inbox delivery; check spam. A connection failure after acceptance can cause a duplicate on retry.

Session history and email profiles are stored locally in Home Assistant. SMTP credentials are stored in its integration configuration; they are not uploaded to GitHub.

## Updates and support

Update through HACS, restart Home Assistant and reopen the panel. The panel displays the running integration version. Local brand images are included; their display in integration views depends on Home Assistant version. Some HACS update cards use the external Home Assistant brands service.

[Releases](https://github.com/EvgenyKrinets/ev-neighbor-charger/releases) · [Report an issue](https://github.com/EvgenyKrinets/ev-neighbor-charger/issues) · [MIT license](LICENSE)

## Краткая инструкция на русском

1. Добавьте репозиторий в **HACS → ⋮ → Пользовательские репозитории**, тип **Интеграция**.
2. Установите, перезапустите HA и добавьте **EV Neighbor Charger** в **Настройки → Устройства и службы**.
3. Выберите выключатель, накопительный счётчик энергии, мощность, цену, пользователей и задержку отключения.
4. Пользователь запускает зарядку под своим аккаунтом; история и email привязаны к нему.
5. Кнопка **@** открывает почту пользователя. SMTP и тест отправки находятся в настройках интеграции.
6. В истории доступны день, неделя, месяц, год и всё время; внизу — сумма времени, энергии и стоимости.

Ограничение пользователей скрывает навигацию и убирает общие права на сущности, но не обеспечивает полную изоляцию всех API Home Assistant.

## Scheduled charging (0.4.16)

Choose **Schedule charging**, select a future date/time (shown in the device’s local timezone), and save. The station is immediately reserved and shows the owner and planned start to all allowed users. Only one reservation is supported; occupied stations cannot be reserved. The switch stays off until launch.

The owner or an administrator can change/cancel the reservation or choose **Start now**. Launch runs inside Home Assistant, without an open app. Reservations survive integration reloads and HA restarts. An overdue reservation starts after HA recovers and the switch/energy sensor are ready. Launch errors are displayed to the owner/admin, the reservation is retained, and HA retries when available. Removed or disabled users cannot launch.

Session time, energy and cost start at actual switch activation, excluding reservation waiting time. A scheduled session has **no timeout before the first charging load**. After load appears, the existing finishing/low-power timer applies. Scheduling does not override the vehicle’s own charging settings.

**Русский:** «Запланировать зарядку» резервирует станцию сразу. Владелец или администратор может изменить время, отменить бронь или начать сейчас. Расписание сохраняется после перезапуска HA. Отдельного таймера отмены при отсутствии нагрузки нет.

**עברית:** תזמון טעינה שומר את המטען עבור המשתמש מיד. המשתמש או מנהל יכולים לשנות את השעה, לבטל או להתחיל עכשיו. ההזמנה נשמרת לאחר הפעלה מחדש. אין ביטול אוטומטי בזמן ההמתנה לצריכת החשמל הראשונה.
