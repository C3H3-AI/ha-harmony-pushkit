import pytest

from custom_components.ha_harmony_pushkit import DOMAIN, SERVICE_SEND_NOTIFICATION, async_setup_entry, async_unload_entry


@pytest.mark.asyncio
async def test_unload_entry_unregisters_service_and_clears_flag():
    hass = FakeHass()

    await async_setup_entry(hass, FakeEntry({}))

    assert hass.services.registered == [(DOMAIN, SERVICE_SEND_NOTIFICATION)]
    assert hass.data[DOMAIN]["service_registered"] is True

    assert await async_unload_entry(hass, FakeEntry({})) is True

    assert hass.config_entries.unloaded_platforms == [["notify"]]
    assert hass.services.removed == [(DOMAIN, SERVICE_SEND_NOTIFICATION)]
    assert "service_registered" not in hass.data[DOMAIN]


class FakeEntry:
    def __init__(self, data):
        self.data = data


class FakeServices:
    def __init__(self):
        self.registered = []
        self.removed = []

    def async_register(self, domain, service, handler):
        self.registered.append((domain, service))

    def async_remove(self, domain, service):
        self.removed.append((domain, service))


class FakeConfigEntries:
    def __init__(self):
        self.unloaded_platforms = []

    async def async_forward_entry_setups(self, entry, platforms):
        return None

    async def async_unload_platforms(self, entry, platforms):
        self.unloaded_platforms.append(list(platforms))
        return True


class FakeHass:
    def __init__(self):
        self.data = {}
        self.services = FakeServices()
        self.config_entries = FakeConfigEntries()