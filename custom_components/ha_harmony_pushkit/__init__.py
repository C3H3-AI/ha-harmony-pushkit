from __future__ import annotations

from typing import Any

from .const import (
    DEFAULT_KEY_FILE,
    DEFAULT_PUSH_ENDPOINT,
    DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from .clients import PushKitClient, iter_pushkit_clients
from .pushkit import load_agc_client, send_push_message
from .services import normalize_send_message_data

PLATFORMS = ["notify"]


async def async_setup(hass: Any, _config: dict[str, Any]) -> bool:
    await _async_register_services(hass)
    return True


async def async_setup_entry(hass: Any, entry: Any) -> bool:
    await _async_register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: Any, entry: Any) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        _async_unregister_services(hass)
    return unloaded


async def _async_register_services(hass: Any) -> None:
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("service_registered"):
        return

    async def async_send_message(call: Any) -> None:
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        service_data = normalize_send_message_data(call.data)
        session = async_get_clientsession(hass)
        clients = _resolve_pushkit_clients(hass, service_data.entity_ids)
        credentials = load_agc_client(hass.config.path(DEFAULT_KEY_FILE))
        for client in clients:
            await send_push_message(
                session=session,
                credentials=credentials,
                pushkit_token=client.pushkit_token,
                title=service_data.title,
                message=service_data.message,
                data=service_data.data,
                persistent=service_data.persistent,
                endpoint_template=DEFAULT_PUSH_ENDPOINT,
                server_instance_id=_hass_instance_id(hass),
            )
            _record_notification_success(hass, client.unique_key)

    hass.services.async_register(DOMAIN, SERVICE_SEND_MESSAGE, async_send_message)
    domain_data["service_registered"] = True


def _async_unregister_services(hass: Any) -> None:
    domain_data = hass.data.get(DOMAIN, {})
    if not domain_data.get("service_registered"):
        return
    hass.services.async_remove(DOMAIN, SERVICE_SEND_MESSAGE)
    domain_data.pop("service_registered", None)


def _hass_instance_id(hass: Any) -> str:
    config = getattr(hass, "config", None)
    return str(getattr(config, "instance_id", "") or "").strip()


def _resolve_pushkit_clients(hass: Any, entity_ids: list[str]) -> list[PushKitClient]:
    client_keys = _entity_client_keys(hass, entity_ids)
    clients = [
        client
        for client in iter_pushkit_clients(hass)
        if client.unique_key in client_keys or client.webhook_id in client_keys or client.device_id in client_keys
    ]
    if len(clients) != len(client_keys):
        raise ValueError("selected Harmony PushKit notify entity is no longer registered")
    return clients


def _record_notification_success(hass: Any, client_key: str) -> None:
    entity = hass.data.get(DOMAIN, {}).get("notify_entities", {}).get(client_key)
    if entity is not None:
        entity.async_record_success()


def _entity_client_keys(hass: Any, entity_ids: list[str]) -> set[str]:
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    keys: set[str] = set()
    prefix = f"{DOMAIN}_"
    for entity_id in entity_ids:
        entity = registry.async_get(entity_id)
        unique_id = getattr(entity, "unique_id", "") if entity else ""
        if not unique_id.startswith(prefix):
            raise ValueError(f"invalid Harmony PushKit notify entity: {entity_id}")
        keys.add(unique_id.removeprefix(prefix))
    return keys
