from custom_components.ha_harmony_pushkit.clients import iter_pushkit_clients


def test_iter_pushkit_clients_reads_registered_harmonyos_mobile_app_data():
    hass = FakeHass(
        {
            "mobile_app": {
                "config_entries": {
                    "device-1": FakeEntry(
                        {
                            "webhook_id": "webhook-1",
                            "device_id": "device-id-1",
                            "device_name": "Living Room Phone",
                            "manufacturer": "Huawei",
                            "model": "Mate 60 Pro",
                            "app_data": {
                                "pushkit_enabled": True,
                                "pushkit_provider": "huawei_push_kit",
                                "pushkit_token": "token-1",
                            },
                        }
                    )
                }
            }
        }
    )

    clients = iter_pushkit_clients(hass)

    assert len(clients) == 1
    assert clients[0].unique_key == "webhook-1"
    assert clients[0].webhook_id == "webhook-1"
    assert clients[0].name == "Living Room Phone"
    assert clients[0].manufacturer == "Huawei"
    assert clients[0].model == "Mate 60 Pro"
    assert clients[0].pushkit_token == "token-1"


def test_iter_pushkit_clients_falls_back_to_model_and_webhook_id():
    hass = FakeHass(
        {
            "mobile_app": {
                "config_entries": {
                    "device-1": FakeEntry(
                        {
                            "webhook_id": "webhook-1",
                            "model": "Mate X5",
                            "app_data": {
                                "pushkit_enabled": True,
                                "pushkit_provider": "huawei_push_kit",
                                "pushkit_token": "token-1",
                            },
                        }
                    )
                }
            }
        }
    )

    clients = iter_pushkit_clients(hass)

    assert clients[0].unique_key == "webhook-1"
    assert clients[0].name == "Mate X5"


def test_iter_pushkit_clients_skips_incomplete_or_non_pushkit_registrations():
    hass = FakeHass(
        {
            "mobile_app": {
                "config_entries": {
                    "missing-token": FakeEntry(
                        {
                            "webhook_id": "webhook-1",
                            "device_name": "No Token",
                            "app_data": {
                                "pushkit_enabled": True,
                                "pushkit_provider": "huawei_push_kit",
                            },
                        }
                    ),
                    "wrong-provider": FakeEntry(
                        {
                            "webhook_id": "webhook-2",
                            "device_name": "Wrong Provider",
                            "app_data": {
                                "pushkit_enabled": True,
                                "pushkit_provider": "other",
                                "pushkit_token": "token-2",
                            },
                        }
                    ),
                    "disabled": FakeEntry(
                        {
                            "webhook_id": "webhook-3",
                            "device_name": "Disabled",
                            "app_data": {
                                "pushkit_enabled": False,
                                "pushkit_provider": "huawei_push_kit",
                                "pushkit_token": "token-3",
                            },
                        }
                    ),
                }
            }
        }
    )

    assert iter_pushkit_clients(hass) == []


def test_iter_pushkit_clients_prefers_webhook_id_for_stable_unique_key():
    hass = FakeHass(
        {
            "mobile_app": {
                "config_entries": {
                    "device-1": FakeEntry(
                        {
                            "webhook_id": "webhook-1",
                            "device_id": "device-id-1",
                            "device_name": "Living Room Phone",
                            "app_data": {
                                "pushkit_enabled": True,
                                "pushkit_provider": "huawei_push_kit",
                                "pushkit_token": "token-1",
                            },
                        }
                    )
                }
            }
        }
    )

    clients = iter_pushkit_clients(hass)

    assert clients[0].unique_key == "webhook-1"
    assert clients[0].device_id == "device-id-1"

class FakeEntry:
    def __init__(self, data):
        self.data = data


class FakeHass:
    def __init__(self, data):
        self.data = data
