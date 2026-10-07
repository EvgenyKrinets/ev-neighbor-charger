<p align="center">
  <img src="custom_components/ev_neighbor_charger/brand/logo.png" width="540" alt="EV Neighbor Charger">
</p>

<p align="center">A simple, accountable way to share an EV charger through Home Assistant.</p>

<p align="center">
  <img alt="Home Assistant" src="https://img.shields.io/badge/Home%20Assistant-2025.1%2B-41BDF5?logo=home-assistant&logoColor=white">
  <img alt="HACS" src="https://img.shields.io/badge/HACS-Custom%20Integration-41BDF5">
  <img alt="Setup" src="https://img.shields.io/badge/Setup-UI%20only-success">
  <img alt="Automatic shutoff" src="https://img.shields.io/badge/Automatic%20shutoff-Built%20in-16A085">
</p>

<p align="center">
  <img src="docs/ev-neighbor-charger-hero.jpg" width="100%" alt="EV charging at home with a mobile control panel">
</p>

<p align="center"><em>Presentation illustration; the live control panel is rendered inside Home Assistant.</em></p>

---

## Overview

**EV Neighbor Charger** adds a dedicated Home Assistant page for starting a shared charging session, tracking energy and cost, and switching the charger off automatically after it has been idle.

Choose the relay, sensors, allowed Home Assistant users, tariff and shutoff rules in the normal integration setup form. No YAML and no separate automation are required.

## Highlights

| Feature | What it does |
| --- | --- |
| **UI setup** | Select the charger switch, power sensor, energy meter and allowed users in Home Assistant. |
| **One-tap start** | A neighbor starts charging from the integration page using their own signed-in Home Assistant account. |
| **Automatic idle shutoff** | If power stays below the configured threshold for the configured delay, the integration switches the charger off. Defaults: **100 W for 2 minutes**. |
| **Session accounting** | Records the active user, energy used and cost at the configured price per kWh. |
| **Personal history** | Neighbors see their own sessions; an administrator can review all sessions. |
| **Optional read-only access** | Selected non-admin accounts automatically open the charging panel without navigation. Their general entity permissions are removed, with original groups saved for restoration. Kiosk navigation does not isolate every Home Assistant API; use a separate portal for complete isolation. |
| **English and Russian** | Setup labels and descriptions are available in both languages. |

## How a charging session works

<p align="center">
  <img src="docs/charging-flow.svg" width="100%" alt="Four steps from user authorization to automatic charger shutoff and session history">
</p>

## Installation

### Install with HACS

1. Open **HACS → Integrations**.
2. Open the menu **⋮ → Custom repositories**.
3. Add `EvgenyKrinets/ev-neighbor-charger` and choose **Integration** as the category.
4. Download **EV Neighbor Charger**.
5. Restart Home Assistant.
6. Open **Settings → Devices & services → Add integration** and select **EV Neighbor Charger**.

### Configure the integration

Select these items in the setup form:

| Setup field | Requirement |
| --- | --- |
| Charger switch | A `switch` entity. It must be **off** when a new session starts. |
| Cumulative energy sensor | A `sensor` in **kWh** or **Wh**. |
| Current power sensor | A `sensor` in **W** or **kW**. |
| Price per kWh | Cost rate used for session totals. Default: **₪0.65/kWh**. |
| Allowed users | Home Assistant accounts permitted to start charging. |
| Restrict selected users | Optional. Moves selected non-admin users to **Read Only**. Enabled by default. |
| Idle power threshold | Power at or below which the shutoff timer starts. Default: **100 W**. |
| Shutoff delay | How long power must remain below the threshold. Default: **120 seconds**. |

The same values can later be adjusted in **Settings → Devices & services → EV Neighbor Charger → Configure**.

## Dashboard behavior

- The integration adds **EV зарядка** to the Home Assistant sidebar.
- An administrator can start a session and see the full session history.
- An allowed neighbor can start a session and sees their own energy, cost and history.
- The logged-in Home Assistant user is determined by the authenticated connection; the page does not let someone choose another user's name.
- If another session is already active, the charger is shown as busy.

## Automatic shutoff

The idle timer starts when measured power falls to or below the configured threshold. If power rises above it before the delay expires, the timer is cancelled. If power remains low for the full delay, the integration turns the switch off and closes the session.

Automatic shutoff only applies to a session started by this integration. A switch that was already on before a session starts is treated as busy, so the integration will not take ownership of an unknown charging session.

## Access and limitations

When **Restrict selected users** is enabled, selected non-admin accounts are placed in Home Assistant's built-in **Read Only** group. Their previous group memberships are saved and restored if they are removed from the allow-list or the integration is removed.

Read Only blocks direct control of entities across Home Assistant, but it does not hide other entity states or make the account a strict single-dashboard account. Home Assistant does not provide a per-user setting that limits an account to only this page.

This first version supports one charger per Home Assistant instance. Test the selected switch and sensors while present before relying on automatic shutoff.

## Current version

**v0.2.1** — fixes duplicate registration of the panel's JavaScript route after a failed setup or integration reload.

## Project links

- **Repository:** https://github.com/EvgenyKrinets/ev-neighbor-charger
- **Issues:** https://github.com/EvgenyKrinets/ev-neighbor-charger/issues


## Версия 0.3.0 — живые данные, языки и email

- Мощность, энергия и стоимость обновляются при поступлении новых состояний Home Assistant. Статус сессии и история проверяются каждые 2 секунды, пока страница открыта. Точность и частота зависят от датчиков.
- Страница и настройки поддерживают русский, английский и иврит; для иврита используется RTL. Язык страницы первоначально берётся из Home Assistant; переключатель находится сверху.
- Пользователь указывает свою почту в блоке «Отчёты по почте», выбирает язык и нажимает «Сохранить». Сохранённый язык используется в письмах.
- Администратор: **Настройки → Устройства и службы → EV Neighbor Charger → Настроить**. Включите почту, укажите SMTP-сервер, порт (обычно 587 для STARTTLS или 465 для SSL), почту отправителя, логин и пароль приложения SMTP. Пароль вводится в скрытом поле и хранится в конфигурации Home Assistant; сделайте его резервную копию безопасной.
- Письма отправляются после начала и окончания зарядки. Итог содержит начало, конец, длительность, энергию, тариф, стоимость и причину завершения.
- Ежемесячное письмо отправляется в первые 5 минут нового месяца по часовому поясу Home Assistant. В него входят все сессии клиента, **завершившиеся в предыдущем месяце**, суммы и CSV с подробностями. При запуске после простоя отправляются также пропущенные месяцы с зарядками. При первом включении почты могут отправиться отчёты за сохранённые прошлые месяцы. Пустые месяцы не отправляются.
- История больше не обрезается до 1000 сессий; на странице отображаются последние 100. Архив хранится локально в Home Assistant.
- Сбой почты не блокирует зарядку: письма остаются в локальной очереди, попытка повторяется каждые 5 минут. SMTP не гарантирует строго однократную доставку: при обрыве после принятия письма сервером возможен повтор. Администратор видит ошибку доставки на странице; подробности — в журнале Home Assistant.
- После установки обновления перезапустите Home Assistant и обновите страницу. Почта необязательна: без SMTP зарядка продолжает работать.


## Версия 0.3.1 — отображение версии и почта аккаунта

На странице зарядки отображаются версия работающего сервера и локальная иконка. Для HACS публикуется GitHub Release: выберите релиз `v0.3.1` вместо ветки `main`, чтобы в обновлениях отображался номер версии вместо SHA коммита.

У стандартного локального пользователя Home Assistant нет отдельного поля email. Если его собственный логин имеет вид email, интеграция предлагает этот адрес в форме. Пользователь проверяет его и нажимает «Сохранить» перед использованием для отчётов. Уже сохранённый адрес имеет приоритет. Почта Home Assistant Cloud не используется как почта соседей.

Иконка страницы интеграции поставляется в `brand/` (локальные бренд-иконки поддерживаются Home Assistant 2026.3+). Карточка обновления HACS — отдельный интерфейс: версии HACS с жёстко заданным URL `brands.home-assistant.io` игнорируют локальные изображения. Это ограничение HACS, и локальная иконка панели его не исправляет.
