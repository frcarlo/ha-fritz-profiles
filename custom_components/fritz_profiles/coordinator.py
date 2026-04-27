"""DataUpdateCoordinator for fritz_profiles."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AuthenticationError, CannotConnectError, FritzProfilesApi
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class FritzProfilesCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that polls the FritzBox for profile data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.api = FritzProfilesApi(
            host=entry.data[CONF_HOST],
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            session=async_get_clientsession(hass, verify_ssl=False),
        )
        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.api.async_get_profiles()
        except AuthenticationError as err:
            raise UpdateFailed(f"Authentication error: {err}") from err
        except CannotConnectError as err:
            raise UpdateFailed(f"Cannot connect to FritzBox: {err}") from err
