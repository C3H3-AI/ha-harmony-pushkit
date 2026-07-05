import pytest

from custom_components.ha_harmony_pushkit.services import (
    ServiceValidationError,
    normalize_send_notification_data,
    resolve_pushkit_token,
)


def test_normalize_send_notification_data_accepts_required_fields():
    normalized = normalize_send_notification_data(
        {
            "pushkit_token": " token-123 ",
            "title": " Door ",
            "message": " Front door opened ",
            "data": {
                "entity_id": "binary_sensor.front_door",
                "count": 2,
            },
            "key_file": "custom-key.json",
            "push_endpoint": "https://example.test/v3/{project_id}/messages:send",
            "webhook_id": "webhook-1",
        }
    )

    assert normalized.pushkit_token == "token-123"
    assert normalized.title == "Door"
    assert normalized.message == "Front door opened"
    assert normalized.data == {"entity_id": "binary_sensor.front_door", "count": 2}
    assert normalized.key_file == "custom-key.json"
    assert normalized.push_endpoint == "https://example.test/v3/{project_id}/messages:send"
    assert normalized.webhook_id == "webhook-1"


def test_normalize_send_notification_data_defaults_title_and_optional_data():
    normalized = normalize_send_notification_data(
        {
            "message": "Front door opened",
        }
    )

    assert normalized.pushkit_token == ""
    assert normalized.title == "Home Assistant"
    assert normalized.data == {}
    assert normalized.key_file == ""
    assert normalized.push_endpoint == ""


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("message", ""),
    ],
)
def test_normalize_send_notification_data_rejects_empty_required_fields(field, value):
    data = {
        "pushkit_token": "token-123",
        "message": "Front door opened",
    }
    data[field] = value

    with pytest.raises(ServiceValidationError, match=field):
        normalize_send_notification_data(data)


def test_resolve_pushkit_token_prefers_explicit_token():
    hass = FakeHass(
        {
            "mobile_app": {
                "config_entries": {
                    "device-1": FakeEntry(
                        {
                            "app_data": {
                                "pushkit_enabled": True,
                                "pushkit_provider": "huawei_push_kit",
                                "pushkit_token": "registered-token",
                            }
                        }
                    )
                }
            }
        }
    )

    assert resolve_pushkit_token(hass, " explicit-token ", "") == "explicit-token"


def test_resolve_pushkit_token_reads_mobile_app_registration_app_data():
    hass = FakeHass(
        {
            "mobile_app": {
                "config_entries": {
                    "device-1": FakeEntry(
                        {
                            "app_data": {
                                "pushkit_enabled": True,
                                "pushkit_provider": "huawei_push_kit",
                                "pushkit_token": "registered-token",
                            }
                        }
                    )
                }
            }
        }
    )

    assert resolve_pushkit_token(hass, "", "") == "registered-token"


def test_resolve_pushkit_token_reads_specific_mobile_app_registration():
    hass = FakeHass(
        {
            "mobile_app": {
                "config_entries": {
                    "device-1": FakeEntry(
                        {
                            "webhook_id": "webhook-1",
                            "app_data": {
                                "pushkit_enabled": True,
                                "pushkit_provider": "huawei_push_kit",
                                "pushkit_token": "first-token",
                            },
                        }
                    ),
                    "device-2": FakeEntry(
                        {
                            "webhook_id": "webhook-2",
                            "app_data": {
                                "pushkit_enabled": True,
                                "pushkit_provider": "huawei_push_kit",
                                "pushkit_token": "second-token",
                            },
                        }
                    ),
                }
            }
        }
    )

    assert resolve_pushkit_token(hass, "", "webhook-2") == "second-token"


def test_resolve_pushkit_token_rejects_ambiguous_mobile_app_registrations():
    hass = FakeHass(
        {
            "mobile_app": {
                "config_entries": {
                    "device-1": FakeEntry(
                        {
                            "app_data": {
                                "pushkit_enabled": True,
                                "pushkit_provider": "huawei_push_kit",
                                "pushkit_token": "first-token",
                            }
                        }
                    ),
                    "device-2": FakeEntry(
                        {
                            "app_data": {
                                "pushkit_enabled": True,
                                "pushkit_provider": "huawei_push_kit",
                                "pushkit_token": "second-token",
                            }
                        }
                    ),
                }
            }
        }
    )

    with pytest.raises(ServiceValidationError, match="webhook_id"):
        resolve_pushkit_token(hass, "", "")


def test_resolve_pushkit_token_rejects_missing_registration_token():
    hass = FakeHass({"mobile_app": {"config_entries": {}}})

    with pytest.raises(ServiceValidationError, match="pushkit_token"):
        resolve_pushkit_token(hass, "", "")


class FakeEntry:
    def __init__(self, data):
        self.data = data


class FakeHass:
    def __init__(self, data):
        self.data = data
