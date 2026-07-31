from __future__ import annotations

from typing import Any

from homeassistant import config_entries

from .const import DOMAIN


class HarmonyPushKitConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Harmony PushKit."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Harmony PushKit", data={})
