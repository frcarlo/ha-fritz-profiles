"""BinarySensorEntity: actual internet access state per device."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BLOCKED_PROFILE_NAMES, DATA_COORDINATOR, DOMAIN
from .entity import FritzProfileBaseEntity
from .coordinator import FritzProfilesCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    entities = [
        FritzInternetAccessSensor(coordinator, device["uid"], device["name"])
        for device in coordinator.data.get("devices", [])
    ]
    async_add_entities(entities)


class FritzInternetAccessSensor(FritzProfileBaseEntity, BinarySensorEntity):
    """Binary sensor: True = internet accessible, False = blocked (any reason)."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:web"

    def __init__(self, coordinator: FritzProfilesCoordinator, device_uid: str, device_name: str) -> None:
        super().__init__(coordinator, device_uid, device_name)
        self._attr_unique_id = f"{DOMAIN}_{device_uid}_connectivity"
        self._attr_name = "Internet Status"

    @property
    def is_on(self) -> bool | None:
        device = self._get_device_data()
        if device is None:
            return None
        return not device.get("internet_blocked", False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = super().extra_state_attributes
        device = self._get_device_data()
        if device is None:
            return attrs
        if not device.get("internet_blocked", False):
            attrs["blocked_reason"] = "none"
        else:
            profile_name = self._get_profile_name(device["current_profile"]) or ""
            if profile_name.lower() in BLOCKED_PROFILE_NAMES:
                attrs["blocked_reason"] = "profile"
            else:
                attrs["blocked_reason"] = "time_budget"
        return attrs
