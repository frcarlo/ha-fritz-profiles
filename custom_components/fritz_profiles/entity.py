"""Base entity for FritzBox Profile Manager."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo, format_mac
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FritzProfilesCoordinator
from .identity import normalize_mac, stable_device_key


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
        device = next(d for d in coordinator.data.get("devices", []) if d["uid"] == device_uid)
        self._device_mac = normalize_mac(device.get("mac", ""))
        self._device_key = stable_device_key(device)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_key)},
            connections=(
                {(CONNECTION_NETWORK_MAC, format_mac(self._device_mac))}
                if self._device_mac else set()
            ),
            name=self._device_name,
            manufacturer="AVM",
            model="FritzBox Network Device",
            via_device=(DOMAIN, self.coordinator.config_entry.entry_id),
        )

    def _get_device_data(self) -> dict[str, Any] | None:
        """Return the coordinator data entry for this device.

        The FritzBox reassigns UIDs on every profile change (e.g. user3561 in
        Kids becomes landevice671 in Standard, then user3563 back in Kids).
        Match by hardware identity so duplicate names and reassigned UIDs cannot
        redirect profile changes to a different device.
        """
        devices = self.coordinator.data.get("devices", [])
        for device in devices:
            if stable_device_key(device) == self._device_key:
                return device
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
        attrs: dict[str, Any] = {"device_name": self._device_name}
        if self._device_mac:
            attrs["mac_address"] = self._device_mac
        remaining = device.get("time_remaining")
        if remaining is not None:
            attrs["time_remaining_minutes"] = remaining
        shared_budgets = self.coordinator.data.get("profile_shared_budgets", {})
        current_profile = device.get("current_profile", "")
        if current_profile in shared_budgets:
            attrs["shared_budget"] = shared_budgets[current_profile]
        return attrs
