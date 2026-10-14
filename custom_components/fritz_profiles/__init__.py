"""FritzBox Profile Manager integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DATA_API, DATA_COORDINATOR, DOMAIN, PLATFORMS
from .coordinator import FritzProfilesCoordinator
from .entity import stable_device_key

_LOGGER = logging.getLogger(__name__)

_DEVICE_ENTITY_SUFFIXES: tuple[tuple[Platform, str, str], ...] = (
    (Platform.SELECT, "profile", "profile"),
    (Platform.SWITCH, "internet", "internet"),
    (Platform.BINARY_SENSOR, "connectivity", "connectivity"),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FritzBox Profile Manager from a config entry."""
    coordinator = FritzProfilesCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    _async_migrate_uid_unique_ids(hass, coordinator)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_API: coordinator.api,
        DATA_COORDINATOR: coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data[DATA_API].async_logout()
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_migrate_uid_unique_ids(
    hass: HomeAssistant,
    coordinator: FritzProfilesCoordinator,
) -> None:
    """Migrate entity registry entries away from volatile FritzBox UIDs."""
    entity_registry = er.async_get(hass)

    for device in coordinator.data.get("devices", []):
        old_uid = device["uid"]
        device_key = stable_device_key(device["name"])

        for platform, old_suffix, new_suffix in _DEVICE_ENTITY_SUFFIXES:
            old_unique_id = f"{DOMAIN}_{old_uid}_{old_suffix}"
            new_unique_id = f"{DOMAIN}_{device_key}_{new_suffix}"

            entity_id = entity_registry.async_get_entity_id(
                platform,
                DOMAIN,
                old_unique_id,
            )
            if entity_id is None:
                continue

            if entity_registry.async_get_entity_id(platform, DOMAIN, new_unique_id):
                _LOGGER.warning(
                    "Cannot migrate %s unique ID from %s to %s because the new "
                    "unique ID is already registered",
                    platform,
                    old_unique_id,
                    new_unique_id,
                )
                continue

            entity_registry.async_update_entity(
                entity_id,
                new_unique_id=new_unique_id,
            )
            _LOGGER.debug(
                "Migrated %s unique ID from %s to %s",
                entity_id,
                old_unique_id,
                new_unique_id,
            )
