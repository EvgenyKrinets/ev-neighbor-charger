from __future__ import annotations

from datetime import datetime, timezone, timedelta
import asyncio
import math
import voluptuous as vol
from homeassistant.util import dt as dt_util
from .reporting import valid_email, send_mail
from .profile import suggested_email
import logging
from pathlib import Path

from homeassistant.components import websocket_api
from homeassistant.components.frontend import async_register_built_in_panel, add_extra_js_url
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import Context

from .const import (
    CONF_ENERGY, CONF_IDLE_SECONDS, CONF_IDLE_W, CONF_POWER, CONF_RATE,
    CONF_SWITCH, CONF_USERS, CONF_READ_ONLY_USERS, DOMAIN, PANEL_ELEMENT, PANEL_PATH, STORAGE_KEY,
    STORAGE_VERSION, VERSION,
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
    # Normalize the legacy setup title without changing the config entry ID.
    if entry.title == "EV Neighbor Charger":
        hass.config_entries.async_update_entry(entry, title="EV Charger")
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored = await store.async_load() or {"sessions": [], "active": None}
    managed_users = stored.get("managed_users", {})
    allowed_users = set(settings.get(CONF_USERS, []))
    restrict_users = bool(settings.get(CONF_READ_ONLY_USERS, True))

    # Restricted neighbors have no general entity permissions. Charging uses
    # explicitly authorized integration commands. Preserve original groups.
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
            if user.groups:
                await hass.auth.async_update_user(user, group_ids=[])

    data = {"entry": entry, "store": store, "sessions": stored.get("sessions", []), "active": stored.get("active"), "reservation": stored.get("reservation"), "schedule_error": None, "timer": None, "closing": False, "managed_users": managed_users,
            "profiles": stored.get("profiles", {}), "outbox": stored.get("outbox", []), "monthly": stored.get("monthly", []), "mail_error": None, "mail_lock": asyncio.Lock(), "starting": False, "stopped": False}
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data[entry.entry_id] = data

    async def persist():
        await store.async_save({key: data[key] for key in ("sessions", "active", "reservation", "managed_users", "profiles", "outbox", "monthly")})
        async_dispatcher_send(hass, f"{DOMAIN}_updated")

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
        if power is not None and power > float(settings.get(CONF_IDLE_W, 100)) and not data["active"].get("has_load"):
            data["active"]["has_load"] = True
            hass.async_create_task(persist())
        below = power is not None and power <= float(settings.get(CONF_IDLE_W, 100))
        if below and data["timer"] is None and (data["active"].get("has_load") or not data["active"].get("scheduled")):
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
    # A restored session is ours only while the actual switch remains on.
    # Do not mistake unknown/unavailable states for an external start.
    restored_switch = hass.states.get(settings[CONF_SWITCH])
    if data["active"] and restored_switch and restored_switch.state == "off":
        await close_session("switch_off")
    if data["active"]:
        # Recover a session after a restart and resume its idle timer if needed.
        power = _num(hass.states.get(settings[CONF_POWER]), "w") if hass.states.get(settings[CONF_POWER]) else None
        if power is not None and power > float(settings.get(CONF_IDLE_W, 100)):
            data["active"]["has_load"] = True
            await persist()
        if power is not None and power <= float(settings.get(CONF_IDLE_W, 100)) and (data["active"].get("has_load") or not data["active"].get("scheduled")):
            data["timer"] = async_call_later(hass, int(settings.get(CONF_IDLE_SECONDS, 120)), low_power_callback)

    @callback
    def snapshot(user):
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
        session = data["active"]
        reservation = data.get("reservation")
        switch_state = hass.states.get(settings[CONF_SWITCH])
        external_control = bool(switch_state and switch_state.state == "on" and not session)
        phase = "external" if external_control else ("scheduled" if reservation else "available")
        if session:
            if current_power is None:
                phase = "unavailable"
            elif current_power > float(settings.get(CONF_IDLE_W, 100)):
                phase = "charging"
            else:
                phase = "finishing" if session.get("has_load") else "preparing"
        return {"active": active, "sessions": list(reversed(visible)), "totals": totals, "charge_phase": phase, "power_w": current_power, "power_updated": power_state.last_updated.isoformat() if power_state else None, "energy_updated": energy_state.last_updated.isoformat() if energy_state else None, "energy_kwh": current_energy, "reservation": reservation, "schedule_error": data.get("schedule_error") if is_admin or (reservation and user and reservation["user_id"] == user.id) else None, "can_manage_reservation": bool(reservation and user and (is_admin or reservation["user_id"] == user.id)), "busy": bool(data["active"] or reservation or external_control), "external_control": external_control, "owner": (data["active"] or reservation or {}).get("name"), "is_admin": is_admin, "config_entry_id": entry.entry_id if is_admin else None, "can_start": can_start, "rate": float(settings.get(CONF_RATE, 0)), "version": VERSION, "suggested_email": suggested_email(user), "profile": data["profiles"].get(user.id, {}) if user else {}, "entities": {"power": settings[CONF_POWER], "energy": settings[CONF_ENERGY]}, "email_enabled": bool(settings.get("smtp_enabled")), "mail_error": data["mail_error"] if is_admin else None}

    @callback
    def authorized(connection, msg):
        user = connection.user
        if user and (user.is_admin or user.id in settings.get(CONF_USERS, [])):
            return True
        connection.send_error(msg["id"], websocket_api.ERR_UNAUTHORIZED, "User not allowed")
        return False

    @websocket_api.websocket_command({"type": f"{DOMAIN}/access"})
    @websocket_api.async_response
    async def ws_access(hass, connection, msg):
        user = connection.user
        connection.send_result(msg["id"], {
            "restricted": bool(user and not user.is_admin and
                user.id in settings.get(CONF_USERS, []) and
                settings.get(CONF_READ_ONLY_USERS, True)),
            "path": f"/{PANEL_PATH}",
        })

    websocket_api.async_register_command(hass, ws_access)

    @websocket_api.websocket_command({"type": f"{DOMAIN}/get"})
    @websocket_api.async_response
    async def ws_get(hass, connection, msg):
        if authorized(connection, msg):
            connection.send_result(msg["id"], snapshot(connection.user))

    @websocket_api.websocket_command({"type": f"{DOMAIN}/subscribe"})
    @callback
    def ws_subscribe(hass, connection, msg):
        if not authorized(connection, msg):
            return
        @callback
        def send_update(*_args):
            if not authorized(connection, msg):
                return
            connection.send_event(msg["id"], snapshot(connection.user))

        unsubs = [
            async_track_state_change_event(hass, [settings[CONF_POWER], settings[CONF_ENERGY], settings[CONF_SWITCH]], send_update),
            async_dispatcher_connect(hass, f"{DOMAIN}_updated", send_update),
        ]
        @callback
        def unsubscribe():
            for unsub in unsubs:
                unsub()
            unsubs.clear()
            data["live_subscriptions"].discard(unsubscribe)

        @callback
        def reloading():
            connection.send_event(msg["id"], {"reload": True})
            unsubscribe()

        data.setdefault("live_subscriptions", set()).add(unsubscribe)
        unsubs.append(async_dispatcher_connect(hass, f"{DOMAIN}_unloading", reloading))
        connection.subscriptions[msg["id"]] = unsubscribe
        connection.send_result(msg["id"])
        send_update()


    async def start_session(user_id, name, scheduled=False):
        switch_state = hass.states.get(settings[CONF_SWITCH])
        energy_state = hass.states.get(settings[CONF_ENERGY])
        if not switch_state or switch_state.state != "off" or not energy_state:
            raise ValueError("Charger must be off and energy sensor available")
        start_kwh = _num(energy_state, "kwh")
        if start_kwh is None:
            raise ValueError("Energy sensor has no numeric reading")
        reservation = data.get("reservation")
        data["starting"] = True
        data["active"] = {"user_id": user_id, "name": name, "start": datetime.now(timezone.utc).isoformat(), "start_kwh": start_kwh, "rate": float(settings.get(CONF_RATE, 0)), "scheduled": scheduled}
        data["reservation"] = None
        try:
            await persist()
            await hass.services.async_call("switch", "turn_on", {"entity_id": settings[CONF_SWITCH]}, blocking=True, context=Context())
        except Exception:
            data["active"] = None
            data["reservation"] = reservation
            await persist()
            raise
        finally:
            data["starting"] = False
        data["schedule_error"] = None
        data["schedule_retry_after"] = None
        if data["active"]:
            queue_mail("start", data["active"])
            power_state = hass.states.get(settings[CONF_POWER])
            power = _num(power_state, "w") if power_state else None
            if power is not None and power > float(settings.get(CONF_IDLE_W, 100)):
                data["active"]["has_load"] = True
            if not scheduled and power is not None and power <= float(settings.get(CONF_IDLE_W, 100)) and data["timer"] is None:
                data["timer"] = async_call_later(hass, int(settings.get(CONF_IDLE_SECONDS, 120)), low_power_callback)
            await persist()
            hass.async_create_task(deliver())

    @websocket_api.websocket_command({"type": f"{DOMAIN}/start"})
    @websocket_api.async_response
    async def ws_start(hass, connection, msg):
        if not authorized(connection, msg):
            return
        reservation = data.get("reservation")
        user = connection.user
        switch_state = hass.states.get(settings[CONF_SWITCH])
        if data["active"] or data["starting"] or not switch_state or switch_state.state != "off" or (reservation and not (user.is_admin or reservation["user_id"] == user.id)):
            connection.send_error(msg["id"], "busy", "Charger is busy")
            return
        try:
            await start_session(reservation["user_id"] if reservation else user.id, reservation["name"] if reservation else user.name or user.id, bool(reservation))
        except Exception as err:
            connection.send_error(msg["id"], "start_failed", str(err))
            return
        connection.send_result(msg["id"], {"started": True})

    @websocket_api.websocket_command({"type": f"{DOMAIN}/schedule", vol.Required("start_at"): str})
    @websocket_api.async_response
    async def ws_schedule(hass, connection, msg):
        if not authorized(connection, msg):
            return
        user = connection.user
        reservation = data.get("reservation")
        switch_state = hass.states.get(settings[CONF_SWITCH])
        if data["active"] or data["starting"] or (switch_state and switch_state.state == "on") or (reservation and not (user.is_admin or reservation["user_id"] == user.id)):
            connection.send_error(msg["id"], "busy", "Charger is busy")
            return
        try:
            start_at = datetime.fromisoformat(msg["start_at"])
            if start_at.tzinfo is None or start_at <= datetime.now(timezone.utc):
                raise ValueError()
        except (ValueError, TypeError, OverflowError):
            connection.send_error(msg["id"], "invalid_time", "Choose a future date and time")
            return
        switch_state = hass.states.get(settings[CONF_SWITCH])
        if not switch_state or switch_state.state != "off":
            connection.send_error(msg["id"], "busy", "Charger must be off")
            return
        data["reservation"] = {"user_id": reservation["user_id"] if reservation else user.id, "name": reservation["name"] if reservation else user.name or user.id, "start_at": start_at.astimezone(timezone.utc).isoformat()}
        data["schedule_error"] = None
        data["schedule_retry_after"] = None
        await persist()
        connection.send_result(msg["id"], {"scheduled": True})

    @websocket_api.websocket_command({"type": f"{DOMAIN}/cancel_schedule"})
    @websocket_api.async_response
    async def ws_cancel_schedule(hass, connection, msg):
        if not authorized(connection, msg):
            return
        reservation = data.get("reservation")
        if data["starting"] or (reservation and not (connection.user.is_admin or reservation["user_id"] == connection.user.id)):
            connection.send_error(msg["id"], "busy", "Reservation belongs to another user or is starting")
            return
        data["reservation"] = None
        data["schedule_error"] = None
        data["schedule_retry_after"] = None
        await persist()
        connection.send_result(msg["id"], {"cancelled": True})

    async def scheduled_tick(_now=None):
        reservation = data.get("reservation")
        if data["stopped"] or data["starting"] or data["active"] or not reservation:
            return
        if datetime.fromisoformat(reservation["start_at"]) > datetime.now(timezone.utc):
            return
        retry_after = data.get("schedule_retry_after")
        if retry_after and retry_after > datetime.now(timezone.utc):
            return
        # Claim before resolving the user to prevent concurrent starts/edits.
        data["starting"] = True
        try:
            user = await hass.auth.async_get_user(reservation["user_id"])
            if data["stopped"]:
                return
            if not user or not user.is_active or (not user.is_admin and user.id not in settings.get(CONF_USERS, [])):
                raise ValueError("Reservation owner is no longer authorized")
            await start_session(reservation["user_id"], reservation["name"], True)
        except Exception as err:
            data["schedule_error"] = str(err)
            data["schedule_retry_after"] = datetime.now(timezone.utc) + timedelta(seconds=30)
            await persist()
        finally:
            data["starting"] = False

    for command in (ws_schedule, ws_cancel_schedule):
        websocket_api.async_register_command(hass, command)
    data["unsubs"].append(async_track_time_interval(hass, scheduled_tick, timedelta(seconds=1)))
    hass.async_create_task(scheduled_tick())

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

    websocket_api.async_register_command(hass, ws_subscribe)
    websocket_api.async_register_command(hass, ws_get)
    websocket_api.async_register_command(hass, ws_start)

    if not domain_data.get("_kiosk_registered"):
        await hass.http.async_register_static_paths([
            StaticPathConfig(f"/{DOMAIN}/kiosk.js", Path(__file__).parent / "kiosk.js", cache_headers=False)
        ])
        add_extra_js_url(hass, f"/{DOMAIN}/kiosk.js?v={VERSION}")
        domain_data["_kiosk_registered"] = True

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
    if not domain_data.get("_panel_icon_registered"):
        try:
            await hass.http.async_register_static_paths([
                StaticPathConfig(f"/{DOMAIN}/icon.png", Path(__file__).parent / "brand" / "icon.png", cache_headers=True)
            ])
        except RuntimeError as err:
            if "method GET is already registered" not in str(err):
                raise
        domain_data["_panel_icon_registered"] = True
    if PANEL_PATH not in hass.data.get("frontend_panels", {}):
        async_register_built_in_panel(
            hass,
            component_name="custom",
            sidebar_title="EV зарядка",
            sidebar_icon="mdi:ev-station",
            frontend_url_path=PANEL_PATH,
            config={"_panel_custom": {
                "name": PANEL_ELEMENT,
                "js_url": f"/{DOMAIN}/panel.js?v={VERSION}",
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
        async_dispatcher_send(hass, f"{DOMAIN}_unloading")
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

