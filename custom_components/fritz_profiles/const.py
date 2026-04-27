from typing import Final
from homeassistant.const import Platform

DOMAIN: Final = "fritz_profiles"
NAME: Final = "FritzBox Profile Manager"

CONF_HOST: Final = "host"
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_HOST: Final = "fritz.box"
DEFAULT_SCAN_INTERVAL: Final = 30

PLATFORMS: Final = [Platform.SELECT, Platform.SWITCH]

DATA_API: Final = "api"
DATA_COORDINATOR: Final = "coordinator"

# Profile names that count as "blocked" for the switch entity
BLOCKED_PROFILE_NAMES: Final = [
    "gesperrt",
    "blocked",
    "kein internet",
    "no internet",
    "sperrzeit",
]

# Profile names that count as "unrestricted/standard" for switch turn_on
STANDARD_PROFILE_NAMES: Final = [
    "standard",
    "default",
    "unbegrenzt",
    "unlimited",
    "kein filter",
]
