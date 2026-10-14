"""Device identity shared by the API and entity registry migration."""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from .api import normalize_mac



def stable_device_key(device: dict[str, Any]) -> str:
    """Prefer MAC identity; never use a hostname as a device identifier."""
    mac = normalize_mac(device.get("mac", ""))
    if mac:
        return mac.replace(":", "")
    return device.get("landevice_uid") or device["uid"]


def legacy_name_key(device_name: str) -> str:
    """Reproduce the old hostname key only for registry migration."""
    normalized = unicodedata.normalize("NFKD", device_name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    key = re.sub(r"[^a-z0-9]+", "_", ascii_name.lower()).strip("_")
    return key or "unknown_device"
