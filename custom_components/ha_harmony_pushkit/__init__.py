from __future__ import annotations

from pathlib import Path
from typing import Any

from .const import (
    CONF_KEY_FILE,
    CONF_PUSH_ENDPOINT,
    DEFAULT_KEY_FILE,
    DEFAULT_PUSH_ENDPOINT,
    DOMAIN,
    SERVICE_SEND_NOTIFICATION,
)
from .pushkit import load_service_account, send_push_message
from .services import normalize_send_notification_data, resolve_pushkit_token

PLATFORMS = ["notify"]


async def async_setup(hass: Any, config: dict[str, Any]) -> bool:
    await _async_register_services(hass, config.get(DOMAIN, {}))
    return True


async def async_setup_entry(hass: Any, entry: Any) -> bool:
    await _async_register_services(hass, entry.data)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: Any, entry: Any) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        _async_unregister_services(hass)
    return unloaded


async def _async_register_services(hass: Any, domain_config: dict[str, Any]) -> None:
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("service_registered"):
        return

    async def async_send_notification(call: Any) -> None:
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        service_data = normalize_send_notification_data(call.data)
        endpoint = service_data.push_endpoint or domain_config.get(CONF_PUSH_ENDPOINT, DEFAULT_PUSH_ENDPOINT)
        session = async_get_clientsession(hass)
        pushkit_token = resolve_pushkit_token(hass, service_data.pushkit_token, service_data.webhook_id)
        key_file = service_data.key_file or domain_config.get(CONF_KEY_FILE, DEFAULT_KEY_FILE)
        key_path = _hass_path(hass, key_file)
        auth = load_service_account(key_path)
        await send_push_message(
            session=session,
            auth=auth,
            pushkit_token=pushkit_token,
            title=service_data.title,
            message=service_data.message,
            data=service_data.data,
            endpoint_template=endpoint,
        )

    hass.services.async_register(DOMAIN, SERVICE_SEND_NOTIFICATION, async_send_notification)
    domain_data["service_registered"] = True


def _async_unregister_services(hass: Any) -> None:
    domain_data = hass.data.get(DOMAIN, {})
    if not domain_data.get("service_registered"):
        return
    hass.services.async_remove(DOMAIN, SERVICE_SEND_NOTIFICATION)
    domain_data.pop("service_registered", None)


def _hass_path(hass: Any, path: str) -> Path:
    value = Path(path)
    if value.is_absolute():
        return value
    return Path(hass.config.path(path))
