from __future__ import annotations

from datetime import datetime, timezone, timedelta
import asyncio
import math
import voluptuous as vol
from homeassistant.util import dt as dt_util
from .reporting import valid_email, send_mail
import logging
from pathlib import Path

from homeassistant.components import websocket_api
from homeassistant.components.frontend import async_register_built_in_panel
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.components.http import StaticPathConfig
from homeassistant.auth.const import GROUP_ID_READ_ONLY
from homeassistant.core import Context

from .const import (
    CONF_ENERGY, CONF_IDLE_SECONDS, CONF_IDLE_W, CONF_POWER, CONF_RATE,
    CONF_SWITCH, CONF_USERS, CONF_READ_ONLY_USERS, DOMAIN, PANEL_ELEMENT, PANEL_PATH, STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


def _settings(entry):
    return {**entry.data, **entry.options}


def _num(state, unit):
    try:
        value = float(state.state)
    except (ValueError, TypeError):
        return None
    if not math.isfinite(value):
        return None
    source_unit = state.attributes.get("unit_of_measurement")
    if unit == "kwh":
        return value / 1000 if source_unit == "Wh" else value
    return value * 1000 if source_unit == "kW" else value


async def async_setup_entry(hass: HomeAssistant, entry):
    settings = _settings(entry)
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored = await store.async_load() or {"sessions": [], "active": None}
    managed_users = stored.get("managed_users", {})
    allowed_users = set(settings.get(CONF_USERS, []))
    restrict_users = bool(settings.get(CONF_READ_ONLY_USERS, True))

    # Selected neighbors are placed in Home Assistant's built-in read-only
    # group. Keep their original groups so changes/removal can restore them.
    for user_id in list(managed_users):
        if user_id not in allowed_users or not restrict_users:
            user = await hass.auth.async_get_user(user_id)
            if user and not user.is_admin:
                await hass.auth.async_update_user(user, group_ids=managed_users[user_id])
            managed_users.pop(user_id, None)
    if restrict_users:
        for user_id in allowed_users:
            user = await hass.auth.async_get_user(user_id)
            if user is None or user.is_admin:
                continue
            if user_id not in managed_users:
                managed_users[user_id] = [group.id for group in user.groups]
            if [group.id for group in user.groups] != [GROUP_ID_READ_ONLY]:
                await hass.auth.async_update_user(user, group_ids=[GROUP_ID_READ_ONLY])

    data = {"entry": entry, "store": store, "sessions": stored.get("sessions", []), "active": stored.get("active"), "timer": None, "closing": False, "managed_users": managed_users,
            "profiles": stored.get("profiles", {}), "outbox": stored.get("outbox", []), "monthly": stored.get("monthly", []), "mail_error": None, "mail_lock": asyncio.Lock(), "starting": False, "stopped": False}
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data[entry.entry_id] = data

    async def persist():
        await store.async_save({key: data[key] for key in ("sessions", "active", "managed_users", "profiles", "outbox", "monthly")})

    async def deliver():
        if not settings.get("smtp_enabled") or data["stopped"]:
            return
        async with data["mail_lock"]:
            for job in list(data["outbox"]):
                if data["stopped"]:
                    break
                try:
                    await hass.async_add_executor_job(send_mail, settings, job, dt_util.get_time_zone(hass.config.time_zone))
                except Exception:
                    data["mail_error"] = "smtp_failed"
                    _LOGGER.warning("Charging email delivery failed; queued for retry", exc_info=True)
                    break
                data["outbox"].remove(job)
                data["mail_error"] = None
                await persist()

    def queue_mail(kind, record):
        profile = data["profiles"].get(record["user_id"], {})
        if settings.get("smtp_enabled") and profile.get("email"):
            data["outbox"].append({"kind": kind, "email": profile["email"], "language": profile.get("language", "en"), "name": record.get("name"), "records": [dict(record)]})

    async def monthly_tick(_now=None):
        if data["stopped"]:
            return
        current = dt_util.now().strftime("%Y-%m")
        tz = dt_util.get_time_zone(hass.config.time_zone)
        groups = {}
        for record in data["sessions"]:
            month = datetime.fromisoformat(record["end"]).astimezone(tz).strftime("%Y-%m")
            if month < current:
                groups.setdefault((record["user_id"], month), []).append(record)
        if settings.get("smtp_enabled"):
            for (uid, month), records in groups.items():
                key = uid + ":" + month
                profile = data["profiles"].get(uid, {})
                if key not in data["monthly"] and profile.get("email"):
                    data["outbox"].append({"kind": "monthly", "email": profile["email"], "language": profile.get("language", "en"), "name": records[0].get("name"), "month": month, "records": records})
                    data["monthly"].append(key)
            await persist()
        await deliver()

    await persist()

    async def close_session(reason="completed"):
        active = data["active"]
        if not active or data["closing"]:
            return
        data["closing"] = True
        now = datetime.now(timezone.utc)
        energy_state = hass.states.get(settings[CONF_ENERGY])
        end_energy = _num(energy_state, "kwh") if energy_state else None
        used = max(0, end_energy - active["start_kwh"]) if end_energy is not None else 0
        record = {**active, "end": now.isoformat(), "end_kwh": end_energy, "energy_kwh": round(used, 3), "cost": round(used * float(active.get("rate", settings.get(CONF_RATE, 0))), 2), "reason": reason}
        data["sessions"].append(record)
        queue_mail("end", record)
        data["active"] = None
        if data["timer"]:
            data["timer"]()
            data["timer"] = None
        await persist()
        data["closing"] = False
        hass.async_create_task(deliver())

    async def turn_off_and_close(reason):
        active = data["active"]
        if not active:
            return
        switch_state = hass.states.get(settings[CONF_SWITCH])
        if switch_state and switch_state.state != "off":
            await hass.services.async_call("switch", "turn_off", {"entity_id": settings[CONF_SWITCH]}, blocking=True, context=Context())
        await close_session(reason)

    async def low_power_elapsed(_now):
        data["timer"] = None
        power_state = hass.states.get(settings[CONF_POWER])
        power = _num(power_state, "w") if power_state else None
        if data["active"] and power is not None and power <= float(settings.get(CONF_IDLE_W, 100)):
            await turn_off_and_close("idle_timeout")

    @callback
    def low_power_callback(now):
        hass.async_create_task(low_power_elapsed(now))

    @callback
    def power_changed(event):
        if not data["active"]:
            return
        new_state = event.data.get("new_state")
        power = _num(new_state, "w") if new_state else None
        below = power is not None and power <= float(settings.get(CONF_IDLE_W, 100))
        if below and data["timer"] is None:
            data["timer"] = async_call_later(hass, int(settings.get(CONF_IDLE_SECONDS, 120)), low_power_callback)
        elif not below and data["timer"] is not None:
            data["timer"]()
            data["timer"] = None

    @callback
    def switch_changed(event):
        old, new = event.data.get("old_state"), event.data.get("new_state")
        if data["active"] and old and new and old.state != "off" and new.state == "off":
            hass.async_create_task(close_session("switch_off"))

    data["unsubs"] = [
        async_track_state_change_event(hass, [settings[CONF_POWER]], power_changed),
        async_track_state_change_event(hass, [settings[CONF_SWITCH]], switch_changed),
    ]
    if data["active"]:
        # Recover a session after a restart and resume its idle timer if needed.
        power = _num(hass.states.get(settings[CONF_POWER]), "w") if hass.states.get(settings[CONF_POWER]) else None
        if power is not None and power <= float(settings.get(CONF_IDLE_W, 100)):
            data["timer"] = async_call_later(hass, int(settings.get(CONF_IDLE_SECONDS, 120)), low_power_callback)

    @websocket_api.websocket_command({"type": f"{DOMAIN}/get"})
    @websocket_api.async_response
    async def ws_get(hass, connection, msg):
        user = connection.user
        is_admin = bool(user and user.is_admin)
        sessions = data["sessions"]
        if is_admin:
            visible = sessions
            active = data["active"]
        else:
            uid = user.id if user else None
            visible = [s for s in sessions if s.get("user_id") == uid]
            active = data["active"] if data["active"] and data["active"].get("user_id") == uid else None
        power_state = hass.states.get(settings[CONF_POWER])
        energy_state = hass.states.get(settings[CONF_ENERGY])
        current_power = _num(power_state, "w") if power_state else None
        current_energy = _num(energy_state, "kwh") if energy_state else None
        totals = {"kwh": round(sum(s.get("energy_kwh", 0) for s in visible), 3), "cost": round(sum(s.get("cost", 0) for s in visible), 2)}
        allowed = settings.get(CONF_USERS, [])
        can_start = is_admin or bool(user and user.id in allowed)
        connection.send_result(msg["id"], {"active": active, "sessions": list(reversed(visible[-100:])), "totals": totals, "power_w": current_power, "energy_kwh": current_energy, "busy": bool(data["active"]), "owner": data["active"].get("name") if data["active"] else None, "is_admin": is_admin, "can_start": can_start, "rate": float(settings.get(CONF_RATE, 0)), "profile": data["profiles"].get(user.id, {}) if user else {}, "entities": {"power": settings[CONF_POWER], "energy": settings[CONF_ENERGY]}, "email_enabled": bool(settings.get("smtp_enabled")), "mail_error": data["mail_error"] if is_admin else None})

    @websocket_api.websocket_command({"type": f"{DOMAIN}/start"})
    @websocket_api.async_response
    async def ws_start(hass, connection, msg):
        user = connection.user
        uid = user.id if user else None
        allowed = settings.get(CONF_USERS, [])
        if not user or (not user.is_admin and uid not in allowed):
            connection.send_error(msg["id"], websocket_api.ERR_UNAUTHORIZED, "User is not allowed to start charging")
            return
        if data["active"] or data["starting"]:
            connection.send_error(msg["id"], websocket_api.ERR_HOME_ASSISTANT_ERROR, "Charger is busy")
            return
        switch_state = hass.states.get(settings[CONF_SWITCH])
        energy_state = hass.states.get(settings[CONF_ENERGY])
        if not switch_state or switch_state.state != "off" or not energy_state:
            connection.send_error(msg["id"], websocket_api.ERR_HOME_ASSISTANT_ERROR, "Charger must be off and energy sensor available")
            return
        start_kwh = _num(energy_state, "kwh")
        if start_kwh is None:
            connection.send_error(msg["id"], websocket_api.ERR_HOME_ASSISTANT_ERROR, "Energy sensor has no numeric reading")
            return
        data["starting"] = True
        data["active"] = {"user_id": uid, "name": user.name or user.username, "start": datetime.now(timezone.utc).isoformat(), "start_kwh": start_kwh, "rate": float(settings.get(CONF_RATE, 0))}
        await persist()
        try:
            await hass.services.async_call("switch", "turn_on", {"entity_id": settings[CONF_SWITCH]}, blocking=True, context=Context())
        except Exception:
            data["active"] = None
            await persist()
            data["starting"] = False
            raise
        data["starting"] = False
        if data["active"]:
            queue_mail("start", data["active"])
            await persist()
            hass.async_create_task(deliver())
        power_state = hass.states.get(settings[CONF_POWER])
        power = _num(power_state, "w") if power_state else None
        if power is not None and power <= float(settings.get(CONF_IDLE_W, 100)):
            data["timer"] = async_call_later(hass, int(settings.get(CONF_IDLE_SECONDS, 120)), low_power_callback)
        connection.send_result(msg["id"], {"started": True})

    @websocket_api.websocket_command({"type": f"{DOMAIN}/profile", vol.Required("email"): str, vol.Required("language"): vol.In(["ru", "en", "he"])})
    @websocket_api.async_response
    async def ws_profile(hass, connection, msg):
        user = connection.user
        if not user or (not user.is_admin and user.id not in settings.get(CONF_USERS, [])):
            connection.send_error(msg["id"], websocket_api.ERR_UNAUTHORIZED, "User not allowed")
            return
        email = msg["email"].strip()
        if email and not valid_email(email):
            connection.send_error(msg["id"], "invalid_email", "Invalid email")
            return
        data["profiles"][user.id] = {"email": email, "language": msg["language"]}
        await persist()
        connection.send_result(msg["id"], {"saved": True})
        hass.async_create_task(monthly_tick())

    websocket_api.async_register_command(hass, ws_profile)
    data["unsubs"].append(async_track_time_interval(hass, monthly_tick, timedelta(minutes=5)))
    hass.async_create_task(monthly_tick())

    websocket_api.async_register_command(hass, ws_get)
    websocket_api.async_register_command(hass, ws_start)

    js_path = Path(__file__).parent / "panel.js"
    if not domain_data.get("_panel_static_path_registered"):
        try:
            await hass.http.async_register_static_paths(
                [StaticPathConfig(f"/{DOMAIN}/panel.js", js_path, cache_headers=False)]
            )
        except RuntimeError as err:
            # The HTTP route remains registered after a failed setup/reload.
            # Home Assistant's HTTP API does not make this call idempotent.
            if "method GET is already registered" not in str(err):
                raise
            _LOGGER.debug("Panel JavaScript route was already registered")
        domain_data["_panel_static_path_registered"] = True
    if PANEL_PATH not in hass.data.get("frontend_panels", {}):
        async_register_built_in_panel(
            hass,
            component_name="custom",
            sidebar_title="EV зарядка",
            sidebar_icon="mdi:ev-station",
            frontend_url_path=PANEL_PATH,
            config={"_panel_custom": {
                "name": PANEL_ELEMENT,
                "js_url": f"/{DOMAIN}/panel.js?v=0.3.0",
                "embed_iframe": False,
                "trust_external": False,
            }},
            require_admin=False,
        )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry):
    data = hass.data[DOMAIN].pop(entry.entry_id, None)
    if data:
        data["stopped"] = True
        for unsub in data.get("unsubs", []):
            unsub()
        if data.get("timer"):
            data["timer"]()
    return True


async def async_remove_entry(hass: HomeAssistant, entry):
    """Restore original Home Assistant groups when the integration is removed."""
    stored = await Store(hass, STORAGE_VERSION, STORAGE_KEY).async_load() or {}
    for user_id, group_ids in stored.get("managed_users", {}).items():
        user = await hass.auth.async_get_user(user_id)
        if user and not user.is_admin:
            await hass.auth.async_update_user(user, group_ids=group_ids)
    stored["managed_users"] = {}
    await Store(hass, STORAGE_VERSION, STORAGE_KEY).async_save(stored)
