"""ButtonEntity: reset FritzBox ticket list."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_API, DATA_COORDINATOR, DOMAIN
from .coordinator import FritzProfilesCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    api = hass.data[DOMAIN][entry.entry_id][DATA_API]
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([FritzTicketResetButton(api, coordinator)])


class FritzTicketResetButton(CoordinatorEntity[FritzProfilesCoordinator], ButtonEntity):
    """Button to reset the FritzBox ticket list."""

    _attr_icon = "mdi:ticket-confirmation-outline"
    _attr_has_entity_name = True
    _attr_name = "Tickets zurücksetzen"

    def __init__(self, api, coordinator: FritzProfilesCoordinator) -> None:
        super().__init__(coordinator)
        self._api = api
        self._attr_unique_id = f"{DOMAIN}_{coordinator.config_entry.entry_id}_reset_tickets"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="FritzBox Profile Manager",
            manufacturer="AVM",
        )

    async def async_press(self) -> None:
        await self._api.async_reset_tickets()
        await self.coordinator.async_request_refresh()
