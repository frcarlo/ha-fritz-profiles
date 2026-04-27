"""SensorEntity: FritzBox ticket codes."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import FritzProfilesCoordinator
from .entity import FritzProfileBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([FritzTicketSensor(coordinator)])


class FritzTicketSensor(SensorEntity):
    """Sensor showing available FritzBox ticket codes (45 min extra online time each)."""

    _attr_icon = "mdi:ticket-confirmation"
    _attr_has_entity_name = True
    _attr_name = "Verfügbare Tickets"
    _attr_native_unit_of_measurement = "Tickets"

    def __init__(self, coordinator: FritzProfilesCoordinator) -> None:
        self._coordinator = coordinator
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_tickets"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "FritzBox Profile Manager",
            "manufacturer": "AVM",
        }

    @property
    def should_poll(self) -> bool:
        return False

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def native_value(self) -> int:
        tickets = self._coordinator.data.get("tickets", [])
        return sum(1 for t in tickets if not t["used"])

    @property
    def extra_state_attributes(self) -> dict:
        tickets = self._coordinator.data.get("tickets", [])
        available = [t["code"] for t in tickets if not t["used"]]
        used = [t["code"] for t in tickets if t["used"]]
        return {
            "available_codes": available,
            "used_codes": used,
            "total": len(tickets),
        }
