"""ButtonEntity: reset FritzBox ticket list."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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


class FritzTicketResetButton(ButtonEntity):
    """Button to reset the FritzBox ticket list (generates 12 new codes)."""

    _attr_icon = "mdi:ticket-confirmation-outline"
    _attr_has_entity_name = True
    _attr_name = "Tickets zurücksetzen"

    def __init__(self, api, coordinator: FritzProfilesCoordinator) -> None:
        self._api = api
        self._coordinator = coordinator
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_reset_tickets"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "FritzBox Profile Manager",
            "manufacturer": "AVM",
        }

    async def async_press(self) -> None:
        await self._api.async_reset_tickets()
        await self._coordinator.async_request_refresh()
