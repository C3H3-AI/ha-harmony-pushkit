import enum
import importlib
import sys
import types

import pytest


def pushkit_entry(token="token-1"):
    return FakeEntry(
        {
            "webhook_id": "webhook-1",
            "device_id": "device-id-1",
            "device_name": "Living Room Phone",
            "manufacturer": "Huawei",
            "model": "Mate 60 Pro",
            "app_data": {
                "pushkit_enabled": True,
                "pushkit_provider": "huawei_push_kit",
                "pushkit_token": token,
            },
        }
    )



def pushkit_entry_without_device_id(token="token-1"):
    entry = pushkit_entry(token)
    data = dict(entry.data)
    data.pop("device_id", None)
    return FakeEntry(data)

def test_notify_setup_adds_one_entity_per_registered_pushkit_client(monkeypatch):
    notify_module = import_notify_module(monkeypatch)
    hass = FakeHass({"mobile_app": {"config_entries": {"device-1": pushkit_entry()}}})
    added = []

    async def run():
        await notify_module.async_setup_entry(hass, FakeEntry({}), added.extend)

    import asyncio
    asyncio.run(run())

    assert len(added) == 1
    assert added[0].unique_id == "ha_harmony_pushkit_webhook-1"
    assert added[0].name == "Living Room Phone"
    assert added[0].supported_features == notify_module.NotifyEntityFeature.TITLE
    assert added[0].device_info == {
        "identifiers": {("ha_harmony_pushkit", "webhook-1")},
        "manufacturer": "Huawei",
        "model": "Mate 60 Pro",
        "name": "Living Room Phone",
    }
    assert len(hass.tracked_intervals) == 1


@pytest.mark.asyncio
async def test_notify_setup_adds_later_registered_pushkit_client(monkeypatch):
    notify_module = import_notify_module(monkeypatch)
    hass = FakeHass({"mobile_app": {"config_entries": {}}})
    added = []

    await notify_module.async_setup_entry(hass, FakeEntry({}), added.extend)

    assert added == []
    assert len(hass.tracked_intervals) == 1

    hass.data["mobile_app"]["config_entries"]["device-1"] = pushkit_entry()
    refresh = hass.tracked_intervals[0][0]

    await refresh(None)
    await refresh(None)

    assert len(added) == 1
    assert added[0].unique_id == "ha_harmony_pushkit_webhook-1"


@pytest.mark.asyncio
async def test_notify_entity_sends_pushkit_message(monkeypatch):
    notify_module = import_notify_module(monkeypatch)
    calls = []

    def fake_load_service_account(path):
        calls.append(("load", str(path)))
        return "auth"

    async def fake_send_push_message(**kwargs):
        calls.append(("send", kwargs))

    monkeypatch.setattr(notify_module, "load_service_account", fake_load_service_account)
    monkeypatch.setattr(notify_module, "send_push_message", fake_send_push_message)

    client = notify_module.PushKitClient(
        unique_key="webhook-1",
        webhook_id="webhook-1",
        device_id="device-id-1",
        name="Living Room Phone",
        manufacturer="Huawei",
        model="Mate 60 Pro",
        pushkit_token="token-1",
    )
    hass = FakeHass({"mobile_app": {"config_entries": {"device-1": pushkit_entry()}}})
    entity = notify_module.HarmonyPushKitNotifyEntity(hass, client, {})

    await entity.async_send_message("Body", title="Title", data={"entity_id": "binary_sensor.front_door"})

    assert calls[0] == ("load", "config\\.storage\\ha_harmony_pushkit\\jwt.json")
    assert calls[1][0] == "send"
    assert calls[1][1]["session"] == "session"
    assert calls[1][1]["auth"] == "auth"
    assert calls[1][1]["pushkit_token"] == "token-1"
    assert calls[1][1]["title"] == "Title"
    assert calls[1][1]["message"] == "Body"
    assert calls[1][1]["data"] == {"entity_id": "binary_sensor.front_door"}


@pytest.mark.asyncio
async def test_notify_entity_refreshes_pushkit_token_before_sending(monkeypatch):
    notify_module = import_notify_module(monkeypatch)
    calls = []

    monkeypatch.setattr(notify_module, "load_service_account", lambda path: "auth")

    async def fake_send_push_message(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(notify_module, "send_push_message", fake_send_push_message)

    client = notify_module.PushKitClient(
        unique_key="webhook-1",
        webhook_id="webhook-1",
        device_id="device-id-1",
        name="Living Room Phone",
        manufacturer="Huawei",
        model="Mate 60 Pro",
        pushkit_token="old-token",
    )
    hass = FakeHass({"mobile_app": {"config_entries": {"device-1": pushkit_entry("new-token")}}})
    entity = notify_module.HarmonyPushKitNotifyEntity(hass, client, {})

    await entity.async_send_message("Body", title="Title")

    assert calls[0]["pushkit_token"] == "new-token"


@pytest.mark.asyncio
async def test_notify_entity_fails_when_registered_client_is_no_longer_valid(monkeypatch):
    notify_module = import_notify_module(monkeypatch)
    calls = []

    monkeypatch.setattr(notify_module, "load_service_account", lambda path: "auth")

    async def fake_send_push_message(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(notify_module, "send_push_message", fake_send_push_message)

    client = notify_module.PushKitClient(
        unique_key="webhook-1",
        webhook_id="webhook-1",
        device_id="device-id-1",
        name="Living Room Phone",
        manufacturer="Huawei",
        model="Mate 60 Pro",
        pushkit_token="old-token",
    )
    hass = FakeHass({"mobile_app": {"config_entries": {}}})
    entity = notify_module.HarmonyPushKitNotifyEntity(hass, client, {})

    with pytest.raises(notify_module.HomeAssistantError, match="no longer registered"):
        await entity.async_send_message("Body", title="Title")

    assert calls == []


def import_notify_module(monkeypatch):
    homeassistant = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    notify = types.ModuleType("homeassistant.components.notify")
    exceptions = types.ModuleType("homeassistant.exceptions")
    helpers = types.ModuleType("homeassistant.helpers")
    aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
    event = types.ModuleType("homeassistant.helpers.event")

    class HomeAssistantError(Exception):
        pass

    class NotifyEntityFeature(enum.IntFlag):
        TITLE = 1

    class NotifyEntity:
        @property
        def supported_features(self):
            return getattr(self, "_attr_supported_features", NotifyEntityFeature(0))

    def async_get_clientsession(hass):
        return hass.session

    def async_track_time_interval(hass, action, interval):
        hass.tracked_intervals.append((action, interval))
        return lambda: hass.removed_intervals.append(action)

    notify.NotifyEntity = NotifyEntity
    notify.NotifyEntityFeature = NotifyEntityFeature
    exceptions.HomeAssistantError = HomeAssistantError
    aiohttp_client.async_get_clientsession = async_get_clientsession
    event.async_track_time_interval = async_track_time_interval
    monkeypatch.setitem(sys.modules, "homeassistant", homeassistant)
    monkeypatch.setitem(sys.modules, "homeassistant.components", components)
    monkeypatch.setitem(sys.modules, "homeassistant.components.notify", notify)
    monkeypatch.setitem(sys.modules, "homeassistant.exceptions", exceptions)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers", helpers)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.aiohttp_client", aiohttp_client)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.event", event)
    sys.modules.pop("custom_components.ha_harmony_pushkit.notify", None)
    return importlib.import_module("custom_components.ha_harmony_pushkit.notify")


class FakeEntry:
    def __init__(self, data):
        self.data = data
        self.unload_callbacks = []

    def async_on_unload(self, callback):
        self.unload_callbacks.append(callback)


class FakeConfig:
    def path(self, path):
        return f"config\\{path}"


class FakeHass:
    def __init__(self, data):
        self.data = data
        self.config = FakeConfig()
        self.session = "session"
        self.tracked_intervals = []
        self.removed_intervals = []