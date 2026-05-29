"""Config flow — minimal: Z2M topic + boiler entity."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_BOILER_ENTITY, CONF_PERSON_ENTITIES, CONF_Z2M_BASE_TOPIC, DEFAULT_Z2M_BASE_TOPIC, DOMAIN


class HiveLocalTRVConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not mqtt.async_get_mqtt_data(self.hass):
                errors["base"] = "mqtt_unavailable"
            else:
                base = user_input[CONF_Z2M_BASE_TOPIC].rstrip("/")
                await self.async_set_unique_id(base)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Hive TRVs ({base})",
                    data={
                        CONF_Z2M_BASE_TOPIC:  base,
                        CONF_BOILER_ENTITY:   user_input.get(CONF_BOILER_ENTITY) or None,
                        CONF_PERSON_ENTITIES: user_input.get(CONF_PERSON_ENTITIES) or [],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_Z2M_BASE_TOPIC, default=DEFAULT_Z2M_BASE_TOPIC): str,
                vol.Optional(CONF_BOILER_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["climate", "switch", "input_boolean"])
                ),
                vol.Optional(CONF_PERSON_ENTITIES): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="person", multiple=True)
                ),
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: config_entries.ConfigEntry) -> HiveLocalTRVOptionsFlow:
        return HiveLocalTRVOptionsFlow(entry)


class HiveLocalTRVOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> config_entries.FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data={
                CONF_BOILER_ENTITY:   user_input.get(CONF_BOILER_ENTITY) or None,
                CONF_PERSON_ENTITIES: user_input.get(CONF_PERSON_ENTITIES) or [],
            })

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(CONF_BOILER_ENTITY, default=self._entry.data.get(CONF_BOILER_ENTITY)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["climate", "switch", "input_boolean"])
                ),
                vol.Optional(CONF_PERSON_ENTITIES, default=self._entry.data.get(CONF_PERSON_ENTITIES, [])): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="person", multiple=True)
                ),
            }),
        )
