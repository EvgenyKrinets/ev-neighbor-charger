from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .reporting import valid_email

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
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            if user_input.get("smtp_enabled") and (not user_input.get("smtp_host", "").strip() or not valid_email(user_input.get("smtp_sender", ""))):
                errors["base"] = "smtp_config"
            else:
                return self.async_create_entry(title="", data=user_input)
        data = {**self.config_entry.data, **self.config_entry.options}
        users_selector = await _allowed_users_selector(self.hass)
        schema = vol.Schema({
            vol.Required(CONF_RATE, default=data.get(CONF_RATE, DEFAULT_RATE)): selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=10, step=0.01, mode=selector.NumberSelectorMode.BOX)),
            vol.Required(CONF_USERS, default=data.get(CONF_USERS, [])): users_selector,
            vol.Required(CONF_READ_ONLY_USERS, default=data.get(CONF_READ_ONLY_USERS, True)): selector.BooleanSelector(),
            vol.Required(CONF_IDLE_W, default=data.get(CONF_IDLE_W, DEFAULT_IDLE_W)): selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=2000, step=10, mode=selector.NumberSelectorMode.BOX)),
            vol.Required(CONF_IDLE_SECONDS, default=data.get(CONF_IDLE_SECONDS, DEFAULT_IDLE_SECONDS)): selector.NumberSelector(selector.NumberSelectorConfig(min=30, max=1800, step=10, mode=selector.NumberSelectorMode.BOX)),
            vol.Required("smtp_enabled", default=data.get("smtp_enabled", False)): selector.BooleanSelector(),
            vol.Optional("smtp_host", default=data.get("smtp_host", "")): selector.TextSelector(),
            vol.Required("smtp_port", default=data.get("smtp_port", 587)): selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=65535, mode=selector.NumberSelectorMode.BOX)),
            vol.Required("smtp_security", default=data.get("smtp_security", "starttls")): selector.SelectSelector(selector.SelectSelectorConfig(options=["starttls", "ssl"])),
            vol.Optional("smtp_sender", default=data.get("smtp_sender", "")): selector.TextSelector(),
            vol.Optional("smtp_username", default=data.get("smtp_username", "")): selector.TextSelector(),
            vol.Optional("smtp_password", default=data.get("smtp_password", "")): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
        })
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
