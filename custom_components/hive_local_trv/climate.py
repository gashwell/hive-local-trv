"""Climate platform — individual TRV entities and room group entities."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DATA_HUB,
    DEFAULT_FROST_TEMP,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_TEMP_STEP,
    DOMAIN,
    MODE_AWAY,
    MODE_BOOST,
    MODE_HOLIDAY,
    MODE_MANUAL,
    MODE_OFF,
    MODE_SCHEDULE,
)
from .coordinator import HiveTRVCoordinator, HiveTRVHub
from .entity import HiveTRVEntity
from .room import HiveRoomCoordinator

_LOGGER = logging.getLogger(__name__)

_HVAC_MODES  = [HVACMode.HEAT, HVACMode.OFF]
_PRESET_MODES = [MODE_MANUAL, MODE_SCHEDULE, MODE_BOOST, MODE_AWAY]   # holiday shown as attribute
_FEATURES = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.TURN_ON
    | ClimateEntityFeature.TURN_OFF
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub: HiveTRVHub = hass.data[DOMAIN][entry.entry_id][DATA_HUB]
    _trv_entities: dict[str, HiveTRVClimate]  = {}
    _room_entities: dict[str, HiveRoomClimate] = {}

    # ── Individual TRVs ───────────────────────────────────────────────────────
    def _add_trv(coord: HiveTRVCoordinator) -> None:
        if coord.friendly_name not in _trv_entities:
            e = HiveTRVClimate(coord)
            _trv_entities[coord.friendly_name] = e
            async_add_entities([e])

    def _remove_trv(friendly_name: str) -> None:
        e = _trv_entities.pop(friendly_name, None)
        if e:
            hass.async_create_task(e.async_remove())

    hub.register_add_entities("climate", _add_trv, _remove_trv)

    # ── Room groups — listen for dynamic creation/removal ─────────────────────
    @callback
    def _on_room_added(event: Any) -> None:
        if event.data.get("entry_id") != entry.entry_id:
            return
        room_id    = event.data["room_id"]
        room_coord = event.data["coordinator"]
        if room_id not in _room_entities:
            e = HiveRoomClimate(room_coord)
            _room_entities[room_id] = e
            async_add_entities([e])

    @callback
    def _on_room_removed(event: Any) -> None:
        room_id = event.data.get("room_id")
        e = _room_entities.pop(room_id, None)
        if e:
            hass.async_create_task(e.async_remove())

    entry.async_on_unload(
        hass.bus.async_listen(f"{DOMAIN}_room_added",   _on_room_added)
    )
    entry.async_on_unload(
        hass.bus.async_listen(f"{DOMAIN}_room_removed", _on_room_removed)
    )


# ── Individual TRV climate entity ─────────────────────────────────────────────

class HiveTRVClimate(HiveTRVEntity, ClimateEntity):
    """Climate entity for a single Hive TRV valve.

    HVAC modes:  heat | off
    Preset modes: manual | schedule | boost
    """

    _attr_name            = None   # device name is the entity name
    _attr_hvac_modes      = _HVAC_MODES
    _attr_preset_modes    = _PRESET_MODES
    _attr_supported_features = _FEATURES
    _attr_temperature_unit   = UnitOfTemperature.CELSIUS
    _attr_min_temp           = DEFAULT_MIN_TEMP
    _attr_max_temp           = DEFAULT_MAX_TEMP
    _attr_target_temperature_step = DEFAULT_TEMP_STEP

    def __init__(self, coordinator: HiveTRVCoordinator) -> None:
        super().__init__(coordinator, "climate")

    # ── State ─────────────────────────────────────────────────────────────────

    @property
    def hvac_mode(self) -> HVACMode:
        m = self.coordinator.mode
        return HVACMode.OFF if m in (MODE_OFF, MODE_AWAY, MODE_HOLIDAY) else HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        if self.coordinator.running_state == "heat":
            return HVACAction.HEATING
        if self.coordinator.mode in (MODE_OFF, MODE_AWAY, MODE_HOLIDAY):
            return HVACAction.OFF
        return HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        m = self.coordinator.mode
        if m in (MODE_OFF, MODE_HOLIDAY):
            return None
        return m  # manual | schedule | boost | away

    @property
    def current_temperature(self) -> float | None:
        return self.coordinator.local_temperature

    @property
    def target_temperature(self) -> float | None:
        return self.coordinator.setpoint

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self.coordinator
        attrs: dict[str, Any] = {
            "mode":              c.mode,
            "pi_heating_demand": c.pi_heating_demand,
            "heat_required":     c.heat_required,
            "battery":           c.battery,
            "window_open":       c.get("window_open_internal"),
            "running_state":     c.running_state,
        }
        if c.mode == MODE_BOOST:
            attrs["boost_ends"]              = c.boost_end_time
            attrs["boost_remaining_minutes"] = c.boost_remaining_minutes
        if c.mode == MODE_HOLIDAY:
            attrs["holiday_active"] = True
        if c.mode == MODE_AWAY:
            attrs["away_active"] = True
        return attrs

    # ── Commands ──────────────────────────────────────────────────────────────

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_set_mode(MODE_OFF)
        else:
            # Restore to manual if coming from off
            await self.coordinator.async_set_mode(MODE_MANUAL)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.coordinator.async_set_mode(preset_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self.coordinator.async_set_manual_temperature(float(temp))

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)


# ── Room group climate entity ─────────────────────────────────────────────────

class HiveRoomClimate(CoordinatorEntity[HiveRoomCoordinator], ClimateEntity):
    """Single climate entity representing a room group of TRVs."""

    _attr_has_entity_name    = True
    _attr_hvac_modes         = _HVAC_MODES
    _attr_preset_modes       = _PRESET_MODES
    _attr_supported_features = _FEATURES
    _attr_temperature_unit   = UnitOfTemperature.CELSIUS
    _attr_min_temp           = DEFAULT_MIN_TEMP
    _attr_max_temp           = DEFAULT_MAX_TEMP
    _attr_target_temperature_step = DEFAULT_TEMP_STEP

    def __init__(self, coordinator: HiveRoomCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"room_{coordinator.room_id}_climate"
        self._attr_name      = coordinator.room_name
        from homeassistant.helpers.device_registry import DeviceInfo
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"room_{coordinator.room_id}")},
            name=f"{coordinator.room_name} (Room)",
            manufacturer="Hive Local TRV",
            model="Room Group",
        )

    @property
    def hvac_mode(self) -> HVACMode:
        return HVACMode.OFF if self.coordinator.mode == MODE_OFF else HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        if self.coordinator.heat_required:
            return HVACAction.HEATING
        if self.coordinator.mode == MODE_OFF:
            return HVACAction.OFF
        return HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        m = self.coordinator.mode
        return None if m == MODE_OFF else m

    @property
    def current_temperature(self) -> float | None:
        return self.coordinator.current_temperature

    @property
    def target_temperature(self) -> float | None:
        return self.coordinator.setpoint

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self.coordinator
        attrs: dict[str, Any] = {
            "mode":         c.mode,
            "member_trvs":  c.member_trv_names,
            "temp_sensors": c.temp_sensor_ids,
            "heat_required": c.heat_required,
        }
        if c.mode == MODE_BOOST:
            attrs["boost_ends"]              = c.boost_end_time
            attrs["boost_remaining_minutes"] = c.boost_remaining_minutes
        return attrs

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self.coordinator.async_set_mode(
            MODE_OFF if hvac_mode == HVACMode.OFF else MODE_MANUAL
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.coordinator.async_set_mode(preset_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self.coordinator.async_set_temperature(float(temp))

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)
