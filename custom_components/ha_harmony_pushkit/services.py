from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .const import (
    ATTR_DATA,
    ATTR_ENTITY_ID,
    ATTR_MESSAGE,
    ATTR_PERSISTENT,
    ATTR_TITLE,
)


class ServiceValidationError(ValueError):
    """Raised when a service call does not contain usable notification data."""


@dataclass(frozen=True)
class SendNotificationData:
    entity_ids: list[str]
    title: str
    message: str
    data: dict[str, Any]
    persistent: bool


def normalize_send_notification_data(data: Mapping[str, Any]) -> SendNotificationData:
    entity_ids = _optional_string_list(data, ATTR_ENTITY_ID)
    if not entity_ids:
        raise ServiceValidationError(f"{ATTR_ENTITY_ID} is required")
    message = _required_string(data, ATTR_MESSAGE)
    title = _optional_string(data, ATTR_TITLE) or "Home Assistant"
    payload_data = data.get(ATTR_DATA)
    if payload_data is None:
        payload_data = {}
    if not isinstance(payload_data, dict):
        raise ServiceValidationError(f"{ATTR_DATA} must be a mapping")

    return SendNotificationData(
        entity_ids=entity_ids,
        title=title,
        message=message,
        data=dict(payload_data),
        persistent=_optional_bool(data, ATTR_PERSISTENT),
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


def _optional_string_list(data: Mapping[str, Any], field: str) -> list[str]:
    value = data.get(field)
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    stripped = str(value).strip()
    return [stripped] if stripped else []


def _optional_bool(data: Mapping[str, Any], field: str) -> bool:
    value = data.get(field, False)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)
