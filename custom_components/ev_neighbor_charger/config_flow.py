from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .reporting import valid_email, send_mail, smtp_error_detail
from homeassistant.util import dt as dt_util
from .mail_config import mail_settings, PRESETS

from .const import (
    CONF_ENERGY, CONF_IDLE_SECONDS, CONF_IDLE_W, CONF_POWER, CONF_RATE,
    CONF_SWITCH, CONF_USERS, CONF_READ_ONLY_USERS, DEFAULT_IDLE_SECONDS, DEFAULT_IDLE_W, DEFAULT_RATE,
    DOMAIN,
)

async def _allowed_users_selector(hass):
    users = await hass.auth.async_get_users()
    options = [
        {"label": user.name or user.id, "value": user.id}
        for user in users
        if user.is_active and not user.system_generated and not user.is_admin
    ]
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            multiple=True,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )

def _validate_entities(hass, values):
    errors = {}
    switch = hass.states.get(values.get(CONF_SWITCH))
    energy = hass.states.get(values.get(CONF_ENERGY))
    power = hass.states.get(values.get(CONF_POWER))
    if switch is None:
        errors[CONF_SWITCH] = "entity_not_found"
    if energy is None:
        errors[CONF_ENERGY] = "entity_not_found"
    elif energy.attributes.get("unit_of_measurement") not in ("kWh", "Wh"):
        errors[CONF_ENERGY] = "energy_unit"
    if power is None:
        errors[CONF_POWER] = "entity_not_found"
    elif power.attributes.get("unit_of_measurement") not in ("W", "kW"):
        errors[CONF_POWER] = "power_unit"
    return errors

class EVNeighborChargerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        errors = {}
        if user_input is not None:
            switch = self.hass.states.get(user_input[CONF_SWITCH])
            energy = self.hass.states.get(user_input[CONF_ENERGY])
            power = self.hass.states.get(user_input[CONF_POWER])
            if switch is None:
                errors[CONF_SWITCH] = "entity_not_found"
            if energy is None:
                errors[CONF_ENERGY] = "entity_not_found"
            elif energy.attributes.get("unit_of_measurement") not in ("kWh", "Wh"):
                errors[CONF_ENERGY] = "energy_unit"
            if power is None:
                errors[CONF_POWER] = "entity_not_found"
            elif power.attributes.get("unit_of_measurement") not in ("W", "kW"):
                errors[CONF_POWER] = "power_unit"
            if not errors:
                return self.async_create_entry(title="EV Neighbor Charger", data=user_input)
        users_selector = await _allowed_users_selector(self.hass)
        schema = vol.Schema({
            vol.Required(CONF_SWITCH): selector.EntitySelector(selector.EntitySelectorConfig(domain="switch")),
            vol.Required(CONF_ENERGY): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Required(CONF_POWER): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Required(CONF_RATE, default=DEFAULT_RATE): selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=10, step=0.01, mode=selector.NumberSelectorMode.BOX)),
            vol.Required(CONF_USERS): users_selector,
            vol.Required(CONF_READ_ONLY_USERS, default=True): selector.BooleanSelector(),
            vol.Required(CONF_IDLE_W, default=DEFAULT_IDLE_W): selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=2000, step=10, mode=selector.NumberSelectorMode.BOX)),
            vol.Required(CONF_IDLE_SECONDS, default=DEFAULT_IDLE_SECONDS): selector.NumberSelector(selector.NumberSelectorConfig(min=30, max=1800, step=10, mode=selector.NumberSelectorMode.BOX)),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return EVNeighborChargerOptionsFlow()

class EVNeighborChargerOptionsFlow(config_entries.OptionsFlow):
    def _current(self):
        return {**self.config_entry.data, **self.config_entry.options}

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(step_id="init", menu_options=["charger", "mail", "mail_test"])

    async def async_step_charger(self, user_input=None):
        data = self._current()
        errors = {}
        if user_input is not None:
            errors = _validate_entities(self.hass, user_input)
            if not errors:
                return self.async_create_entry(title="", data={**self.config_entry.options, **user_input})
        users_selector = await _allowed_users_selector(self.hass)
        schema = vol.Schema({
            vol.Required(CONF_SWITCH, default=data.get(CONF_SWITCH, "")): selector.EntitySelector(selector.EntitySelectorConfig(domain="switch")),
            vol.Required(CONF_ENERGY, default=data.get(CONF_ENERGY, "")): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Required(CONF_POWER, default=data.get(CONF_POWER, "")): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Required(CONF_RATE, default=data.get(CONF_RATE, DEFAULT_RATE)): selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=10, step=0.01, mode=selector.NumberSelectorMode.BOX)),
            vol.Required(CONF_USERS, default=data.get(CONF_USERS, [])): users_selector,
            vol.Required(CONF_READ_ONLY_USERS, default=data.get(CONF_READ_ONLY_USERS, True)): selector.BooleanSelector(),
            vol.Required(CONF_IDLE_W, default=data.get(CONF_IDLE_W, DEFAULT_IDLE_W)): selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=2000, step=10, mode=selector.NumberSelectorMode.BOX)),
            vol.Required(CONF_IDLE_SECONDS, default=data.get(CONF_IDLE_SECONDS, DEFAULT_IDLE_SECONDS)): selector.NumberSelector(selector.NumberSelectorConfig(min=30, max=1800, step=10, mode=selector.NumberSelectorMode.BOX)),
        })
        return self.async_show_form(step_id="charger", data_schema=schema, errors=errors)

    async def async_step_mail(self, user_input=None):
        data = self._current()
        errors = {}
        if user_input is not None:
            self._provider = user_input["smtp_provider"]
            if self._provider == "disabled":
                return self.async_create_entry(title="", data={**self.config_entry.options, "smtp_enabled": False})
            if self._provider == "microsoft":
                errors["base"] = "microsoft_oauth"
            else:
                return await self.async_step_mail_account()
        default = data.get("smtp_provider", "custom") if data.get("smtp_enabled") else "disabled"
        schema = vol.Schema({vol.Required("smtp_provider", default=default): selector.SelectSelector(selector.SelectSelectorConfig(options=["disabled", "gmail", "yahoo", "icloud", "brevo", "mailjet", "microsoft", "custom"], translation_key="mail_provider", mode=selector.SelectSelectorMode.DROPDOWN))})
        return self.async_show_form(step_id="mail", data_schema=schema, errors=errors)

    async def async_step_mail_account(self, user_input=None):
        data = self._current()
        errors = {}
        if user_input is not None:
            try:
                mail = mail_settings(self._provider, user_input, data)
            except ValueError as err:
                errors["base"] = str(err)
            else:
                if user_input.get("mail_action", "save") == "test":
                    self._pending_mail = mail
                    self._test_status = ""
                    return await self.async_step_mail_test()
                return self.async_create_entry(title="", data={**self.config_entry.options, **mail})
        fields = {
            vol.Required("smtp_username", default=(user_input or data).get("smtp_username", "")): selector.TextSelector(),
            vol.Optional("smtp_password"): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
            vol.Required("mail_action", default="test"): selector.SelectSelector(selector.SelectSelectorConfig(options=["save", "test"], translation_key="mail_action")),
        }
        if self._provider in ("brevo", "mailjet"):
            fields[vol.Required("smtp_sender", default=(user_input or data).get("smtp_sender", ""))] = selector.TextSelector()
        if self._provider == "custom":
            fields.update({
                vol.Required("smtp_host", default=data.get("smtp_host", "")): selector.TextSelector(),
                vol.Required("smtp_port", default=data.get("smtp_port", 587)): selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=65535, mode=selector.NumberSelectorMode.BOX)),
                vol.Required("smtp_security", default=data.get("smtp_security", "starttls")): selector.SelectSelector(selector.SelectSelectorConfig(options=["starttls", "ssl"])),
                vol.Required("smtp_sender", default=data.get("smtp_sender", "")): selector.TextSelector(),
            })
        return self.async_show_form(step_id="mailjet_account" if self._provider == "mailjet" else "mail_account", data_schema=vol.Schema(fields), errors=errors)

    async def async_step_mailjet_account(self, user_input=None):
        self._provider = "mailjet"
        return await self.async_step_mail_account(user_input)


    async def async_step_mail_test(self, user_input=None):
        settings = {**self._current(), **getattr(self, "_pending_mail", {})}
        errors = {}
        self._test_status = ""
        tested = False
        if user_input is not None:
            action = user_input.get("test_action", "test")
            if action == "save":
                return self.async_create_entry(title="", data={**self.config_entry.options, **getattr(self, "_pending_mail", {})})
            if action == "back":
                return await self.async_step_mail_account() if getattr(self, "_pending_mail", None) else await self.async_step_init()
            recipient = user_input.get("test_recipient", "").strip()
            if not valid_email(recipient):
                errors["test_recipient"] = "invalid_email"
            elif not settings.get("smtp_enabled"):
                errors["base"] = "mail_disabled"
            else:
                tested = True
                language = self.hass.config.language
                language = language if language in ("ru", "en", "he") else "en"
                try:
                    await self.hass.async_add_executor_job(send_mail, settings, {"kind": "test", "email": recipient, "language": language}, dt_util.get_time_zone(self.hass.config.time_zone))
                except Exception as err:
                    errors["base"] = "mail_test_failed"
                    self._test_status = smtp_error_detail(err, settings)
                else:
                    self._test_status = {"ru": "SMTP-сервер принял тестовое письмо. Проверьте входящие и спам.", "en": "SMTP accepted the test email. Check your inbox and spam folder.", "he": "שרת SMTP קיבל את הודעת הבדיקה. בדקו את תיבת הדואר ואת תיקיית הספאם."}[language]
        runtime = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id, {})
        recipients = {profile.get("email") for profile in runtime.get("profiles", {}).values() if valid_email(profile.get("email"))}
        if valid_email(settings.get("smtp_sender")):
            recipients.add(settings["smtp_sender"])
        fields = {
            vol.Required("test_recipient", default=(user_input or {}).get("test_recipient", settings.get("smtp_sender", ""))): selector.SelectSelector(selector.SelectSelectorConfig(options=sorted(recipients), custom_value=True, mode=selector.SelectSelectorMode.DROPDOWN)),
            vol.Required("test_action", default="test"): selector.SelectSelector(selector.SelectSelectorConfig(options=["test", "save", "back"], translation_key="test_action")),
        }
        return self.async_show_form(step_id="mail_test_result" if tested else "mail_test", data_schema=vol.Schema(fields), errors=errors, description_placeholders={"result": getattr(self, "_test_status", "")})

    async def async_step_mail_test_result(self, user_input=None):
        return await self.async_step_mail_test(user_input)
