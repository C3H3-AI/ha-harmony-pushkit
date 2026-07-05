from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .const import ATTR_PUSHKIT_TOKEN, ATTR_WEBHOOK_ID

MOBILE_APP_DOMAIN = "mobile_app"
MOBILE_APP_CONFIG_ENTRIES = "config_entries"
PUSHKIT_PROVIDER = "huawei_push_kit"


@dataclass(frozen=True)
class PushKitClient:
    unique_key: str
    webhook_id: str
    device_id: str
    name: str
    manufacturer: str
    model: str
    pushkit_token: str


def iter_pushkit_clients(hass: Any) -> list[PushKitClient]:
    clients: list[PushKitClient] = []
    mobile_app_data = getattr(hass, "data", {}).get(MOBILE_APP_DOMAIN, {})
    config_entries = mobile_app_data.get(MOBILE_APP_CONFIG_ENTRIES, {})
    entries = config_entries.items() if isinstance(config_entries, dict) else enumerate(config_entries)
    for entry_key, entry in entries:
        entry_data = _entry_data(entry)
        app_data = _app_data(entry_data)
        if not app_data:
            continue
        if app_data.get("pushkit_enabled") is not True:
            continue
        if _string(app_data, "pushkit_provider") != PUSHKIT_PROVIDER:
            continue
        pushkit_token = _string(app_data, ATTR_PUSHKIT_TOKEN)
        if not pushkit_token:
            continue
        webhook_id = _string(entry_data, ATTR_WEBHOOK_ID)
        device_id = _string(entry_data, "device_id")
        unique_key = webhook_id or device_id or str(entry_key).strip()
        if not unique_key:
            continue
        model = _string(entry_data, "model")
        clients.append(
            PushKitClient(
                unique_key=unique_key,
                webhook_id=webhook_id,
                device_id=device_id,
                name=_string(entry_data, "device_name") or model or "HarmonyOS Device",
                manufacturer=_string(entry_data, "manufacturer"),
                model=model,
                pushkit_token=pushkit_token,
            )
        )
    return clients


def _entry_data(entry: Any) -> Mapping[str, Any]:
    entry_data = getattr(entry, "data", None)
    if isinstance(entry_data, Mapping):
        return entry_data
    if isinstance(entry, Mapping):
        return entry
    return {}


def _app_data(entry_data: Mapping[str, Any]) -> Mapping[str, Any] | None:
    app_data = entry_data.get("app_data")
    return app_data if isinstance(app_data, Mapping) else None


def _string(data: Mapping[str, Any], key: str) -> str:
    value = data.get(key, "")
    if value is None:
        return ""
    return str(value).strip()