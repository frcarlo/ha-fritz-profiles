"""Base entity for FritzBox Profile Manager."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import FritzProfilesCoordinator

_UNSET = object()


class FritzProfileBaseEntity(CoordinatorEntity[FritzProfilesCoordinator]):
    """Base class for FritzBox profile entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FritzProfilesCoordinator,
        device_uid: str,
        device_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_uid = device_uid
        self._device_name = device_name

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_uid)},
            name=self._device_name,
            manufacturer="AVM",
            model="FritzBox Network Device",
            via_device=(DOMAIN, self.coordinator.config_entry.entry_id),
        )

    def _get_device_data(self) -> dict[str, Any] | None:
        """Return the coordinator data entry for this device.

        The FritzBox reassigns UIDs on every profile change (e.g. user3561 in
        Kids becomes landevice671 in Standard, then user3563 back in Kids).
        We therefore match by stored UID first, then fall back to device name.
        """
        devices = self.coordinator.data.get("devices", [])
        for device in devices:
            if device["uid"] == self._device_uid:
                return device
        # UID changed — try name-based lookup (skip if name is ambiguous)
        matches = [d for d in devices if d["name"] == self._device_name]
        if len(matches) == 1:
            return matches[0]
        return None

    def _get_profile_name(self, profile_id: str) -> str | None:
        """Resolve a profile ID to its display name."""
        return self.coordinator.data.get("profiles", {}).get(profile_id)

    def _get_profile_id(self, profile_name: str) -> str | None:
        """Resolve a profile name to its ID."""
        for pid, pname in self.coordinator.data.get("profiles", {}).items():
            if pname == profile_name:
                return pid
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        device = self._get_device_data()
        if device is None:
            return {}
        remaining = device.get("time_remaining")
        if remaining is None:
            return {}
        return {"time_remaining_minutes": remaining}
