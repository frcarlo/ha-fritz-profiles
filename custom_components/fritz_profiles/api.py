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

        # Tickets come from kidPro page
        pro_resp = await self._fetch_page("kidPro")
        tickets = self._parse_tickets(pro_resp)

        # Profiles and device assignments come from kidLis page
        # (only profiles assignable to devices appear in the dropdowns)
        lis_resp = await self._fetch_page("kidLis")
        profiles = self._parse_profiles_from_options(lis_resp)
        devices = self._parse_devices(lis_resp)

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
        """Extract assignable {profile_id: profile_name} from the first device dropdown in kidLis.

        Only profiles that appear as <option> elements are actually assignable to devices.
        """
        profiles: dict[str, str] = {}
        # Find the first <select> with filtprof options
        m = re.search(r'<select[^>]*name="profile:landevice[^"]*"[^>]*>(.*?)</select>', html, re.DOTALL)
        if m:
            for opt in re.finditer(r'<option[^>]*value="(filtprof\d+)"[^>]*>([^<]+)</option>', m.group(1)):
                profiles[opt.group(1)] = opt.group(2).strip()
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

    @staticmethod
    def _parse_devices(html: str) -> list[dict[str, str]]:
        """Extract device list with current profile from kidLis HTML.

        Each <tr> contains data-uid="landeviceXXX", a name title, and a <select>
        with <option value="filtprofN" selected>.
        """
        devices: list[dict[str, str]] = []
        for row in html.split("<tr"):
            if "filtprof" not in row:
                continue
            # UID from select name: name="profile:landeviceXXX"
            uid_m = re.search(r'name="profile:(landevice\d+)"', row)
            name_m = re.search(r'class="name"[^>]*title="([^"]+)"', row)
            profile_m = re.search(r'value="(filtprof\d+)"[^>]*selected', row)
            if uid_m and name_m and profile_m:
                devices.append({
                    "uid": uid_m.group(1),
                    "name": name_m.group(1),
                    "current_profile": profile_m.group(1),
                })
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
        payload = {"sid": self._sid, "page": page}
        try:
            async with self._session.post(
                f"{self._base_url}/data.lua",
                data=payload,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 403:
                    self._sid = None
                    await self.async_login()
                    payload["sid"] = self._sid
                    async with self._session.post(
                        f"{self._base_url}/data.lua",
                        data=payload,
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
