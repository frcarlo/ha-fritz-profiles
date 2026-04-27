"""SensorEntity: FritzBox ticket codes."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import FritzProfilesCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([FritzTicketSensor(coordinator)])


class FritzTicketSensor(CoordinatorEntity[FritzProfilesCoordinator], SensorEntity):
    """Sensor showing available FritzBox ticket codes."""

    _attr_icon = "mdi:ticket-confirmation"
    _attr_has_entity_name = True
    _attr_name = "Verfügbare Tickets"
    _attr_native_unit_of_measurement = "Tickets"

    def __init__(self, coordinator: FritzProfilesCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.config_entry.entry_id}_tickets"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="FritzBox Profile Manager",
            manufacturer="AVM",
        )

    @property
    def native_value(self) -> int:
        tickets = self.coordinator.data.get("tickets", [])
        return sum(1 for t in tickets if not t["used"])

    @property
    def extra_state_attributes(self) -> dict:
        tickets = self.coordinator.data.get("tickets", [])
        return {
            "available_codes": [t["code"] for t in tickets if not t["used"]],
            "used_codes": [t["code"] for t in tickets if t["used"]],
            "total": len(tickets),
        }
