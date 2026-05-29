"""Button platform — adaptation run and mounting mode."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
            es = [HiveAdaptationButton(coord), HiveMountingButton(coord)]
            _entities[coord.friendly_name] = es
            async_add_entities(es)

    def _remove(name: str) -> None:
        for e in _entities.pop(name, []):
            hass.async_create_task(e.async_remove())

    hub.register_add_entities("button", _add, _remove)


class HiveAdaptationButton(HiveTRVEntity, ButtonEntity):
    _attr_name = "Run Adaptation"
    _attr_icon = "mdi:cog-sync"

    def __init__(self, coord: HiveTRVCoordinator) -> None:
        super().__init__(coord, "adaptation_run")

    async def async_press(self) -> None:
        await self.coordinator.async_trigger_adaptation_run()


class HiveMountingButton(HiveTRVEntity, ButtonEntity):
    _attr_name = "Enter Mounting Mode"
    _attr_icon = "mdi:wrench"

    def __init__(self, coord: HiveTRVCoordinator) -> None:
        super().__init__(coord, "mounting_mode")

    async def async_press(self) -> None:
        await self.coordinator.async_set_mounted(False)
