"""Quick local test for the FritzBox Profile API — no HA needed."""
import asyncio
import importlib.util
import os
import sys

import aiohttp

# Load api.py directly — avoids pulling in homeassistant package via __init__.py
_spec = importlib.util.spec_from_file_location(
    "api", os.path.join(os.path.dirname(__file__), "custom_components/fritz_profiles/api.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
FritzProfilesApi = _mod.FritzProfilesApi
AuthenticationError = _mod.AuthenticationError
CannotConnectError = _mod.CannotConnectError

HOST = os.getenv("FRITZ_HOST", "fritz.box")
USER = os.getenv("FRITZ_USER", "")
PASS = os.getenv("FRITZ_PASS", "")


async def main() -> None:
    if not USER or not PASS:
        print("Usage: FRITZ_HOST=192.168.178.1 FRITZ_USER=admin FRITZ_PASS=secret python test_api.py")
        sys.exit(1)

    async with aiohttp.ClientSession() as session:
        api = FritzProfilesApi(HOST, USER, PASS, session)

        print(f"\nConnecting to {HOST} as '{USER}' ...")
        try:
            await api.async_login()
        except AuthenticationError:
            print("ERROR: Login fehlgeschlagen — Benutzername/Passwort prüfen")
            sys.exit(1)
        except CannotConnectError as e:
            print(f"ERROR: Keine Verbindung — {e}")
            sys.exit(1)

        print("Login OK\n")

        data = await api.async_get_profiles()

        profiles = data["profiles"]
        devices = data["devices"]

        print(f"=== Profile ({len(profiles)}) ===")
        for pid, pname in profiles.items():
            print(f"  [{pid}] {pname}")

        print(f"\n=== Geräte ({len(devices)}) ===")
        for dev in devices:
            profile_name = profiles.get(dev["current_profile"], dev["current_profile"])
            print(f"  {dev['name']:<30} Profil: {profile_name}")

        # Optional: Profil eines Geräts setzen
        # uid = devices[0]["uid"]
        # new_pid = list(profiles.keys())[0]
        # print(f"\nSetze Gerät {uid} auf Profil {profiles[new_pid]} ...")
        # await api.async_set_profile(uid, new_pid)
        # print("Gesetzt!")

        await api.async_logout()
        print("\nLogout OK")


asyncio.run(main())
