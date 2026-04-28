"""SelectEntity: choose a FritzBox profile per device."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_API, DATA_COORDINATOR, DOMAIN
from .entity import FritzProfileBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    entities = [
        FritzProfileSelectEntity(coordinator, device["uid"], device["name"])
        for device in coordinator.data.get("devices", [])
    ]
    async_add_entities(entities)


class FritzProfileSelectEntity(FritzProfileBaseEntity, SelectEntity):
    """Select entity to choose the internet access profile for a device."""

    _attr_icon = "mdi:shield-account"
    _attr_translation_key = "profile"

    def __init__(self, coordinator, device_uid: str, device_name: str) -> None:
        super().__init__(coordinator, device_uid, device_name)
        self._attr_unique_id = f"{DOMAIN}_{device_uid}_profile"
        self._attr_name = "Profil"

    @property
    def options(self) -> list[str]:
        return list(self.coordinator.data.get("profiles", {}).values())

    @property
    def current_option(self) -> str | None:
        device = self._get_device_data()
        if device is None:
            return None
        return self._get_profile_name(device["current_profile"])

    async def async_select_option(self, option: str) -> None:
        device = self._get_device_data()
        if device is None:
            _LOGGER.error("Device %s not found in coordinator data", self._device_name)
            return
        profile_id = self._get_profile_id(option)
        if profile_id is None:
            _LOGGER.error("Profile '%s' not found for device %s", option, self._device_name)
            return
        # Use device["uid"] — the current UID, which may differ from self._device_uid
        await self.coordinator.api.async_set_profile(device["uid"], profile_id)
        await self.coordinator.async_request_refresh()
