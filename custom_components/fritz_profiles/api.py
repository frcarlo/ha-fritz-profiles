"""FritzBox LUA API client for profile management."""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

SID_INVALID = "0000000000000000"


class AuthenticationError(Exception):
    pass


class CannotConnectError(Exception):
    pass


class FritzProfilesApi:
    """Client for the FritzBox internal LUA API."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
    ) -> None:
        self._host = host
        self._username = username
        self._password = password
        self._session = session
        self._sid: str | None = None
        self._base_url = f"http://{host}"

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def async_login(self) -> None:
        """Authenticate with the FritzBox and obtain a SID."""
        try:
            async with self._session.get(
                f"{self._base_url}/login_sid.lua?version=2",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
                text = await resp.text()
        except aiohttp.ClientError as err:
            raise CannotConnectError(str(err)) from err

        challenge = self._parse_xml_value(text, "Challenge")
        if not challenge:
            raise CannotConnectError("No challenge in login response")

        # FritzOS ≥ 7.24: PBKDF2 challenge starts with "2$"
        if challenge.startswith("2$"):
            response = self._pbkdf2_response(challenge, self._password)
        else:
            response = self._md5_response(challenge, self._password)

        try:
            async with self._session.post(
                f"{self._base_url}/login_sid.lua?version=2",
                data={"username": self._username, "response": response},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
                text = await resp.text()
        except aiohttp.ClientError as err:
            raise CannotConnectError(str(err)) from err

        sid = self._parse_xml_value(text, "SID")
        if not sid or sid == SID_INVALID:
            raise AuthenticationError("Invalid credentials")

        self._sid = sid
        _LOGGER.debug("FritzBox login successful, SID acquired")

    async def async_logout(self) -> None:
        """Invalidate the current SID."""
        if not self._sid:
            return
        try:
            await self._session.post(
                f"{self._base_url}/login_sid.lua",
                data={"logout": "1", "sid": self._sid},
                timeout=aiohttp.ClientTimeout(total=5),
            )
        except aiohttp.ClientError:
            pass
        self._sid = None

    # ------------------------------------------------------------------
    # Profile management
    # ------------------------------------------------------------------

    async def async_get_profiles(self) -> dict[str, Any]:
        """Return all profiles, device assignments, and ticket codes.

        Returns:
            {
              "profiles": {profile_id: profile_name, ...},
              "devices": [{"uid": str, "name": str, "current_profile": profile_id}, ...],
              "tickets": [{"code": str, "used": bool}, ...]
            }
        """
        await self._ensure_logged_in()

        profiles: dict[str, str] = {}
        devices: list[dict[str, str]] = []
        tickets: list[dict] = []

        for attempt in range(2):
            # Tickets come from kidPro page
            pro_resp = await self._fetch_page("kidPro")
            tickets = self._parse_tickets(pro_resp)

            # Profiles and device assignments come from kidLis page
            # (only profiles assignable to devices appear in the dropdowns)
            lis_resp = await self._fetch_page("kidLis")
            profiles = self._parse_profiles_from_options(lis_resp)
            devices = self._parse_devices(lis_resp, profiles)

            if profiles:
                break

            if attempt == 0:
                # Empty profiles usually means the FritzBox returned a login page
                # with a stale SID (200 OK instead of 403). Force re-login and retry.
                _LOGGER.warning(
                    "Got empty profiles on first attempt — forcing re-login (stale SID?)"
                )
                self._sid = None
                await self.async_login()

        _LOGGER.debug(
            "Loaded %d profiles, %d devices, %d tickets from FritzBox",
            len(profiles),
            len(devices),
            len(tickets),
        )
        return {"profiles": profiles, "devices": devices, "tickets": tickets}

    async def async_reset_tickets(self) -> None:
        """Generate a new set of ticket codes (invalidates all existing ones)."""
        await self._ensure_logged_in()
        assert self._sid
        try:
            async with self._session.post(
                f"{self._base_url}/internet/kids_profilelist.lua",
                data={"sid": self._sid, "refresh": ""},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
        except aiohttp.ClientError as err:
            raise CannotConnectError(str(err)) from err
        _LOGGER.debug("Ticket list reset")

    async def async_set_profile(self, device_uid: str, profile_id: str) -> None:
        """Assign a profile to a device via the kidLis form."""
        await self._ensure_logged_in()
        assert self._sid
        payload = {
            "sid": self._sid,
            "apply": "",
            "editProfiles": "true",
            f"profile:{device_uid}": profile_id,
        }
        try:
            async with self._session.post(
                f"{self._base_url}/internet/kids_userlist.lua",
                data=payload,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
        except aiohttp.ClientError as err:
            raise CannotConnectError(str(err)) from err

    # ------------------------------------------------------------------
    # HTML parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_profiles_from_options(html: str) -> dict[str, str]:
        """Extract assignable {profile_id: profile_name} from any device dropdown in kidLis.

        Only profiles that appear as <option> elements are actually assignable to devices.
        Scans all device <select> elements and merges the results so that a device in a
        non-standard profile (which may appear in a different table section) still
        contributes its profile options.
        """
        profiles: dict[str, str] = {}
        for select in re.finditer(
            r'<select[^>]*name="profile:\w+"[^>]*>(.*?)</select>',
            html,
            re.DOTALL,
        ):
            for opt in re.finditer(
                r'<option([^>]*)>([^<]+)</option>', select.group(1)
            ):
                val_m = re.search(r'value="(filtprof\d+)"', opt.group(1))
                if val_m:
                    profiles[val_m.group(1)] = opt.group(2).strip()
        return profiles

    @staticmethod
    def _parse_tickets(html: str) -> list[dict]:
        """Extract ticket codes from kidPro HTML.

        Ticket objects are embedded as JSON: {"id":"912692","assigned":"0","_node":"ticketN"}
        """
        return [
            {"code": m.group(1), "used": m.group(2) == "1"}
            for m in re.finditer(
                r'\{"id":"(\d{6})","assigned":"([01])","_node":"ticket\d+"',
                html,
            )
        ]

    @classmethod
    def _parse_devices(cls, html: str, profiles: dict[str, str]) -> list[dict[str, str]]:
        """Extract device list with current profile from kidLis HTML.

        Each device row has a <select name="profile:landeviceXXX" disabled>
        where the <option selected> shows the current profile.  The UID can
        also come from data-uid="landeviceXXX" on the block-toggle link.
        """
        devices: list[dict[str, str]] = []
        for row in html.split("<tr"):
            name_m = re.search(r'class="name"[^>]*title="([^"]+)"', row)
            if not name_m:
                continue

            # UID: prefer select name, fall back to data-uid on the block link
            # FritzBox uses both landeviceXXX and userXXX as device UIDs
            uid_m = re.search(r'name="profile:(\w+)"', row) or \
                    re.search(r'data-uid="(\w+)"', row)
            if not uid_m:
                continue

            selected_profile: str | None = None
            for opt in re.finditer(r'<option([^>]+)>', row):
                attrs = opt.group(1)
                if re.search(r'\bselected\b', attrs):
                    val_m = re.search(r'value="(filtprof\d+)"', attrs)
                    if val_m:
                        selected_profile = val_m.group(1)
                        break

            if selected_profile:
                devices.append({
                    "uid": uid_m.group(1),
                    "name": name_m.group(1),
                    "current_profile": selected_profile,
                })
            else:
                _LOGGER.warning(
                    "No selected profile found for device '%s' (%s) — skipping",
                    name_m.group(1),
                    uid_m.group(1),
                )

        return devices

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _ensure_logged_in(self) -> None:
        if not self._sid:
            await self.async_login()

    async def _fetch_page(self, page: str) -> str:
        """Fetch a data.lua page and return raw HTML."""
        assert self._sid
        try:
            async with self._session.post(
                f"{self._base_url}/data.lua",
                data={"sid": self._sid, "page": page},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 403:
                    _LOGGER.debug("Got 403 on page %s, re-logging in", page)
                    self._sid = None
                    await self.async_login()
                    async with self._session.post(
                        f"{self._base_url}/data.lua",
                        data={"sid": self._sid, "page": page},
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as retry:
                        retry.raise_for_status()
                        return await retry.text()
                resp.raise_for_status()
                return await resp.text()
        except aiohttp.ClientError as err:
            raise CannotConnectError(str(err)) from err

    @staticmethod
    def _parse_xml_value(text: str, tag: str) -> str | None:
        match = re.search(rf"<{tag}>(.*?)</{tag}>", text)
        return match.group(1) if match else None

    @staticmethod
    def _pbkdf2_response(challenge: str, password: str) -> str:
        """Compute the PBKDF2-SHA256 challenge response (FritzOS ≥ 7.24)."""
        # challenge format: "2$<iter1>$<salt1>$<iter2>$<salt2>"
        parts = challenge.split("$")
        iter1, salt1, iter2, salt2 = int(parts[1]), parts[2], int(parts[3]), parts[4]

        hash1 = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt1), iter1
        )
        hash2 = hashlib.pbkdf2_hmac("sha256", hash1, bytes.fromhex(salt2), iter2)
        return f"{salt2}${hash2.hex()}"

    @staticmethod
    def _md5_response(challenge: str, password: str) -> str:
        """Compute the MD5 challenge response (FritzOS < 7.24)."""
        response_str = f"{challenge}-{password}"
        # FritzBox requires UTF-16LE encoding for MD5
        return f"{challenge}-{hashlib.md5(response_str.encode('utf-16-le')).hexdigest()}"
