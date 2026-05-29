"""Select platform — keypad lockout (mode is on the climate entity)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_HUB, DOMAIN
from .coordinator import HiveTRVCoordinator, HiveTRVHub
from .entity import HiveTRVEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    hub: HiveTRVHub = hass.data[DOMAIN][entry.entry_id][DATA_HUB]
    _entities: dict[str, list] = {}

    def _add(coord: HiveTRVCoordinator) -> None:
        if coord.friendly_name not in _entities:
            es = [HiveKeypadLockoutSelect(coord)]
            _entities[coord.friendly_name] = es
            async_add_entities(es)

    def _remove(name: str) -> None:
        for e in _entities.pop(name, []):
            hass.async_create_task(e.async_remove())

    hub.register_add_entities("select", _add, _remove)


class HiveKeypadLockoutSelect(HiveTRVEntity, SelectEntity):
    _attr_name    = "Keypad Lock"
    _attr_icon    = "mdi:lock"
    _attr_options = ["unlock", "lock1", "lock2"]

    def __init__(self, coord: HiveTRVCoordinator) -> None:
        super().__init__(coord, "keypad_lockout")

    @property
    def current_option(self) -> str | None:
        return self.coordinator.get("keypad_lockout")

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_keypad_lockout(option)
