from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .clients import PushKitClient, iter_pushkit_clients
from .const import CONF_KEY_FILE, CONF_PUSH_ENDPOINT, DEFAULT_KEY_FILE, DEFAULT_PUSH_ENDPOINT, DOMAIN
from .pushkit import load_service_account, send_push_message

SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(hass: Any, entry: Any, async_add_entities: Any) -> None:
    known_client_keys: set[str] = set()

    async def async_add_new_entities(now: Any = None) -> None:
        entities: list[HarmonyPushKitNotifyEntity] = []
        for client in iter_pushkit_clients(hass):
            client_keys = _client_keys(client)
            if known_client_keys.intersection(client_keys):
                known_client_keys.update(client_keys)
                continue
            known_client_keys.update(client_keys)
            entities.append(HarmonyPushKitNotifyEntity(hass, client, entry.data))
        if entities:
            async_add_entities(entities)

    await async_add_new_entities()
    remove_interval = async_track_time_interval(hass, async_add_new_entities, SCAN_INTERVAL)
    if hasattr(entry, "async_on_unload"):
        entry.async_on_unload(remove_interval)


class HarmonyPushKitNotifyEntity(NotifyEntity):
    def __init__(self, hass: Any, client: PushKitClient, domain_config: dict[str, Any]) -> None:
        self.hass = hass
        self._client = client
        self._domain_config = domain_config
        self._attr_unique_id = f"{DOMAIN}_{client.unique_key}"
        self._attr_name = client.name
        self._attr_supported_features = NotifyEntityFeature.TITLE

    @property
    def unique_id(self) -> str:
        return self._attr_unique_id

    @property
    def name(self) -> str:
        return self._attr_name

    @property
    def device_info(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "identifiers": {(DOMAIN, self._client.unique_key)},
            "name": self._client.name,
        }
        if self._client.manufacturer:
            info["manufacturer"] = self._client.manufacturer
        if self._client.model:
            info["model"] = self._client.model
        return info

    async def async_send_message(
        self,
        message: str = "",
        title: str | None = None,
        target: list[str] | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        key_file = str(self._domain_config.get(CONF_KEY_FILE, DEFAULT_KEY_FILE)).strip() or DEFAULT_KEY_FILE
        endpoint = str(self._domain_config.get(CONF_PUSH_ENDPOINT, DEFAULT_PUSH_ENDPOINT)).strip() or DEFAULT_PUSH_ENDPOINT
        auth = load_service_account(_hass_path(self.hass, key_file))
        client = self._current_client()
        await send_push_message(
            session=async_get_clientsession(self.hass),
            auth=auth,
            pushkit_token=client.pushkit_token,
            title=title or "Home Assistant",
            message=message,
            data=data or {},
            endpoint_template=endpoint,
        )

    def _current_client(self) -> PushKitClient:
        for client in iter_pushkit_clients(self.hass):
            if client.unique_key == self._client.unique_key:
                return client
            if self._client.webhook_id and client.webhook_id == self._client.webhook_id:
                return client
            if self._client.device_id and client.device_id == self._client.device_id:
                return client
        raise HomeAssistantError(f"Harmony PushKit client {self._client.name} is no longer registered")


def _client_keys(client: PushKitClient) -> set[str]:
    return {key for key in (client.unique_key, client.device_id, client.webhook_id) if key}


def _hass_path(hass: Any, path: str) -> Path:
    value = Path(path)
    if value.is_absolute():
        return value
    return Path(hass.config.path(path))