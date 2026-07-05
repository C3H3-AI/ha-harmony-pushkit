from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .clients import iter_pushkit_clients
from .const import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_PUSHKIT_TOKEN,
    ATTR_TITLE,
    ATTR_WEBHOOK_ID,
    CONF_KEY_FILE,
    CONF_PUSH_ENDPOINT,
)


class ServiceValidationError(ValueError):
    """Raised when a service call does not contain usable notification data."""


@dataclass(frozen=True)
class SendNotificationData:
    pushkit_token: str
    title: str
    message: str
    data: dict[str, Any]
    key_file: str
    push_endpoint: str
    webhook_id: str


def normalize_send_notification_data(data: Mapping[str, Any]) -> SendNotificationData:
    pushkit_token = _optional_string(data, ATTR_PUSHKIT_TOKEN)
    message = _required_string(data, ATTR_MESSAGE)
    title = _optional_string(data, ATTR_TITLE) or "Home Assistant"
    payload_data = data.get(ATTR_DATA)
    if payload_data is None:
        payload_data = {}
    if not isinstance(payload_data, dict):
        raise ServiceValidationError(f"{ATTR_DATA} must be a mapping")

    return SendNotificationData(
        pushkit_token=pushkit_token,
        title=title,
        message=message,
        data=dict(payload_data),
        key_file=_optional_string(data, CONF_KEY_FILE),
        push_endpoint=_optional_string(data, CONF_PUSH_ENDPOINT),
        webhook_id=_optional_string(data, ATTR_WEBHOOK_ID),
    )


def resolve_pushkit_token(hass: Any, explicit_token: str, webhook_id: str) -> str:
    token = explicit_token.strip()
    if token:
        return token

    target_webhook_id = webhook_id.strip()
    matches = [
        client.pushkit_token
        for client in iter_pushkit_clients(hass)
        if not target_webhook_id or client.webhook_id == target_webhook_id
    ]

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ServiceValidationError(
            f"{ATTR_WEBHOOK_ID} is required when multiple HarmonyOS mobile_app registrations have Push Kit tokens"
        )

    raise ServiceValidationError(
        f"{ATTR_PUSHKIT_TOKEN} is required when no HarmonyOS mobile_app registration has Push Kit token"
    )



def _required_string(data: Mapping[str, Any], field: str) -> str:
    value = _optional_string(data, field)
    if not value:
        raise ServiceValidationError(f"{field} is required")
    return value


def _optional_string(data: Mapping[str, Any], field: str) -> str:
    value = data.get(field, "")
    if value is None:
        return ""
    return str(value).strip()
