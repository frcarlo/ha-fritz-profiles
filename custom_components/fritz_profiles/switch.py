"""SwitchEntity: quick internet block/unblock toggle per device."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BLOCKED_PROFILE_NAMES, DATA_COORDINATOR, DOMAIN, STANDARD_PROFILE_NAMES
from .entity import FritzProfileBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    entities = [
        FritzProfileSwitchEntity(coordinator, device["uid"], device["name"])
        for device in coordinator.data.get("devices", [])
    ]
    async_add_entities(entities)


class FritzProfileSwitchEntity(FritzProfileBaseEntity, SwitchEntity):
    """Switch that is ON when the device has unrestricted internet access."""

    _attr_icon = "mdi:web"
    _attr_translation_key = "internet_access"

    def __init__(self, coordinator, device_uid: str, device_name: str) -> None:
        super().__init__(coordinator, device_uid, device_name)
        self._attr_unique_id = f"{DOMAIN}_{device_uid}_internet"
        self._attr_name = "Internet"

    @property
    def is_on(self) -> bool | None:
        device = self._get_device_data()
        if device is None:
            return None
        if device.get("internet_blocked"):
            return False
        profile_name = self._get_profile_name(device["current_profile"]) or ""
        return profile_name.lower() not in BLOCKED_PROFILE_NAMES

    async def async_turn_on(self, **kwargs) -> None:
        """Set the standard/unrestricted profile."""
        device = self._get_device_data()
        if device is None:
            return
        profile_id = self._find_profile_id(STANDARD_PROFILE_NAMES)
        if profile_id is None:
            _LOGGER.error(
                "No standard profile found for device %s. Available: %s",
                self._device_name,
                list(self.coordinator.data.get("profiles", {}).values()),
            )
            return
        await self.coordinator.api.async_set_profile(device["uid"], profile_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Set the blocked profile."""
        device = self._get_device_data()
        if device is None:
            return
        profile_id = self._find_profile_id(BLOCKED_PROFILE_NAMES)
        if profile_id is None:
            _LOGGER.error(
                "No blocked profile found for device %s. Available: %s",
                self._device_name,
                list(self.coordinator.data.get("profiles", {}).values()),
            )
            return
        await self.coordinator.api.async_set_profile(device["uid"], profile_id)
        await self.coordinator.async_request_refresh()

    def _find_profile_id(self, name_candidates: list[str]) -> str | None:
        """Find the first profile whose name matches one of the candidates (case-insensitive)."""
        profiles = self.coordinator.data.get("profiles", {})
        for pid, pname in profiles.items():
            if pname.lower() in name_candidates:
                return pid
        return None
