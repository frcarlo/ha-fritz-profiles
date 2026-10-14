"""Offline regression tests; Home Assistant registry interfaces are stubbed."""
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


COMPONENT = Path(__file__).resolve().parents[1] / "custom_components/fritz_profiles"
PACKAGE = "fritz_identity_test"


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, COMPONENT / filename)
    spec.submodule_search_locations = None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Registry:
    def __init__(self, entries):
        self.entries = entries

    def async_get_entity_id(self, platform, domain, unique_id):
        return next((entity_id for entity_id, entry in self.entries.items()
                     if entry.platform == platform and entry.unique_id == unique_id), None)

    def async_get(self, entity_id):
        return self.entries[entity_id]

    def async_update_entity(self, entity_id, *, new_unique_id):
        self.entries[entity_id].unique_id = new_unique_id


class DeviceIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        package = ModuleType(PACKAGE)
        package.__path__ = [str(COMPONENT)]
        cls.modules = patch.dict(sys.modules, {PACKAGE: package})
        cls.modules.start()
        cls.addClassCleanup(cls.modules.stop)
        cls.api = load_module(f"{PACKAGE}.api", "api.py")
        cls.identity = load_module(f"{PACKAGE}.identity", "identity.py")
        const = ModuleType(f"{PACKAGE}.const")
        for key, value in {"DOMAIN": "fritz_profiles", "DATA_API": "api",
                           "DATA_COORDINATOR": "coordinator", "PLATFORMS": []}.items():
            setattr(const, key, value)
        coordinator = ModuleType(f"{PACKAGE}.coordinator")
        coordinator.FritzProfilesCoordinator = object
        class CoordinatorEntity:
            def __class_getitem__(cls, item):
                return cls

            def __init__(self, coordinator):
                self.coordinator = coordinator

        stubs = {
            f"{PACKAGE}.const": const,
            f"{PACKAGE}.coordinator": coordinator,
            "homeassistant": ModuleType("homeassistant"),
            "homeassistant.config_entries": SimpleNamespace(ConfigEntry=object),
            "homeassistant.const": SimpleNamespace(Platform=SimpleNamespace(
                SELECT="select", SWITCH="switch", BINARY_SENSOR="binary_sensor")),
            "homeassistant.core": SimpleNamespace(HomeAssistant=object),
            "homeassistant.helpers": SimpleNamespace(entity_registry=SimpleNamespace(
                async_get=lambda hass: hass.registry)),
            "homeassistant.helpers.device_registry": SimpleNamespace(
                DeviceInfo=dict, CONNECTION_NETWORK_MAC="mac", format_mac=lambda value: value),
            "homeassistant.helpers.update_coordinator": SimpleNamespace(CoordinatorEntity=CoordinatorEntity),
        }
        with patch.dict(sys.modules, stubs):
            cls.entity = load_module(f"{PACKAGE}.entity", "entity.py")
            cls.integration = load_module(f"{PACKAGE}.integration", "__init__.py")

    def device(self, uid="landevice1", name="iPhone", mac="AA:BB:CC:DD:EE:01"):
        return {"uid": uid, "name": name, "mac": mac}

    def test_duplicate_hostnames_have_distinct_keys(self):
        devices = [self.device(), self.device("landevice2", mac="AA:BB:CC:DD:EE:02")]
        self.assertEqual(len({self.identity.stable_device_key(d) for d in devices}), 2)

    def test_mac_format_and_uid_changes_preserve_identity(self):
        self.assertEqual(self.identity.stable_device_key(self.device()),
                         self.identity.stable_device_key(self.device("user99", "Renamed", "aabb.ccdd.ee01")))

    def test_missing_mac_uses_network_uid(self):
        device = self.device("user99", mac="00:00:00:00:00:00")
        device["landevice_uid"] = "landevice1"
        self.assertEqual(self.identity.stable_device_key(device), "landevice1")
        del device["landevice_uid"]
        self.assertEqual(self.identity.stable_device_key(device), "user99")

    def test_network_join_uses_uid_for_duplicate_names(self):
        devices = [self.device(), self.device("landevice2")]
        for d in devices:
            del d["mac"]
        payload = {"data": {"active": [{"UID": "landevice2", "name": "iPhone", "mac": "AA:BB:CC:DD:EE:02"}],
                            "passive": [{"UID": "landevice1", "name": "iPhone", "mac": "AA:BB:CC:DD:EE:01"}]}}
        self.api.FritzProfilesApi._add_network_identity(devices, json.dumps(payload))
        self.assertEqual([d["mac"] for d in devices], ["aa:bb:cc:dd:ee:01", "aa:bb:cc:dd:ee:02"])

    def test_user_uid_join_rejects_ambiguous_names(self):
        payload = {"data": {"active": [{"UID": "landevice1", "name": "iPhone", "mac": "AA:BB:CC:DD:EE:01"}], "passive": []}}
        devices = [{"uid": "user1", "name": "iPhone"}]
        self.api.FritzProfilesApi._add_network_identity(devices, json.dumps(payload))
        self.assertEqual(devices[0]["landevice_uid"], "landevice1")
        devices = [{"uid": "user1", "name": "iPhone"}, {"uid": "user2", "name": "iPhone"}]
        self.api.FritzProfilesApi._add_network_identity(devices, json.dumps(payload))
        self.assertTrue(all("mac" not in d for d in devices))

    def test_invalid_network_response_fails_update(self):
        for response in ("<html>Login</html>", '{"data": []}',
                         '{"data": {"active": null}}', '{"data": {"active": [1]}}'):
            with self.assertRaises(self.api.CannotConnectError):
                self.api.FritzProfilesApi._add_network_identity([], response)

    def test_lookup_tracks_mac_after_uid_change_and_rename(self):
        device = self.device()
        coordinator = SimpleNamespace(data={"devices": [device]})
        entity = self.entity.FritzProfileBaseEntity(coordinator, device["uid"], device["name"])
        other = self.device(mac="AA:BB:CC:DD:EE:02")
        updated = self.device("user99", "New name")
        coordinator.data["devices"] = [other, updated]
        self.assertIs(entity._get_device_data(), updated)
        coordinator.data["devices"] = [other]
        self.assertIsNone(entity._get_device_data())

    def migrate(self, devices, entries):
        registry = Registry({eid: SimpleNamespace(platform=platform, unique_id=uid, config_entry_id=owner)
                             for eid, platform, uid, owner in entries})
        self.integration._async_migrate_uid_unique_ids(
            SimpleNamespace(registry=registry),
            SimpleNamespace(data={"devices": devices}, config_entry=SimpleNamespace(entry_id="ours")))
        return registry

    def test_migration_preserves_entity_id_and_is_idempotent(self):
        entries = [("switch.existing", "switch", "fritz_profiles_iphone_internet", "ours")]
        registry = self.migrate([self.device()], entries)
        self.assertEqual(registry.entries["switch.existing"].unique_id, "fritz_profiles_aabbccddee01_internet")
        registry = self.migrate([self.device()], [("switch.existing", "switch", registry.entries["switch.existing"].unique_id, "ours")])
        self.assertEqual(len(registry.entries), 1)

    def test_migration_skips_shared_names_and_foreign_entries(self):
        devices = [self.device(), self.device("landevice2", mac="AA:BB:CC:DD:EE:02")]
        registry = self.migrate(devices, [
            ("switch.shared", "switch", "fritz_profiles_iphone_internet", "ours"),
            ("switch.old", "switch", "fritz_profiles_landevice2_internet", "ours"),
            ("switch.foreign", "switch", "fritz_profiles_landevice1_internet", "other")])
        self.assertEqual(registry.entries["switch.shared"].unique_id, "fritz_profiles_iphone_internet")
        self.assertEqual(registry.entries["switch.old"].unique_id, "fritz_profiles_aabbccddee02_internet")
        self.assertEqual(registry.entries["switch.foreign"].unique_id, "fritz_profiles_landevice1_internet")

    def test_migration_counts_normalized_name_collisions(self):
        devices = [self.device(name="My Phone"), self.device("landevice2", "My-Phone", "AA:BB:CC:DD:EE:02")]
        registry = self.migrate(devices, [("switch.shared", "switch", "fritz_profiles_my_phone_internet", "ours")])
        self.assertEqual(registry.entries["switch.shared"].unique_id, "fritz_profiles_my_phone_internet")


if __name__ == "__main__":
    unittest.main()
