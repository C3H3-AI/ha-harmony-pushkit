from __future__ import annotations

from dataclasses import dataclass
import json
import secrets
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from .const import DEFAULT_PUSH_ENDPOINT

CONNECT_TOKEN_ENDPOINT = "https://connect-api.cloud.huawei.com/api/oauth2/v1/token"
DEFAULT_TICKET_ENDPOINT = "https://connect-api.cloud.huawei.com/api/wisefunction/functions/561wqit7/ha-harmony-pushkit-ticket-broker-$latest"
DEFAULT_DAILY_PUSH_LIMIT = 20


@dataclass(frozen=True)
class AgcClientCredentials:
    client_id: str
    client_secret: str
    product_id: str


@dataclass(frozen=True)
class BrokerTicket:
    access_token: str
    expires_at: int
    project_id: str


@dataclass(frozen=True)
class ConnectAccessToken:
    access_token: str
    expires_at: int


class PushKitClientError(Exception):
    """Raised when Huawei Push Kit rejects a request."""


class PushKitRateLimitError(PushKitClientError):
    """Raised when a local Push Kit rate limit is exceeded."""


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())


class DailyPushRateLimiter:
    def __init__(
        self,
        limit: int = DEFAULT_DAILY_PUSH_LIMIT,
        date_provider: Callable[[], str] | None = None,
    ) -> None:
        self._limit = limit
        self._date_provider = date_provider or _today
        self._counts: dict[tuple[str, str], int] = {}

    def check_and_increment(self, pushkit_token: str) -> None:
        key = (self._date_provider(), pushkit_token)
        count = self._counts.get(key, 0)
        if count >= self._limit:
            raise PushKitRateLimitError("daily push limit exceeded for this PushKit token")
        self._counts[key] = count + 1


DEFAULT_RATE_LIMITER = DailyPushRateLimiter()


class PushKitTicketCache:
    def __init__(
        self,
        refresh_margin_seconds: int = 60,
        now: Callable[[], int] | None = None,
    ) -> None:
        self._refresh_margin_seconds = refresh_margin_seconds
        self._now = now or (lambda: int(time.time()))
        self._connect_tokens: dict[tuple[str, str], ConnectAccessToken] = {}
        self._broker_tickets: dict[tuple[str, str], BrokerTicket] = {}

    async def get_broker_ticket(self, session: Any, credentials: AgcClientCredentials) -> BrokerTicket:
        cache_key = _credentials_cache_key(credentials)
        ticket = self._broker_tickets.get(cache_key)
        if self._is_valid(ticket):
            return ticket

        connect_token = await self._get_connect_token(session, credentials, cache_key)
        ticket = await request_broker_ticket(session, credentials, connect_token.access_token)
        self._broker_tickets[cache_key] = ticket
        return ticket

    async def _get_connect_token(
        self,
        session: Any,
        credentials: AgcClientCredentials,
        cache_key: tuple[str, str],
    ) -> ConnectAccessToken:
        token = self._connect_tokens.get(cache_key)
        if self._is_valid(token):
            return token

        access_token, expires_in = await request_connect_access_token(session, credentials)
        token = ConnectAccessToken(
            access_token=access_token,
            expires_at=self._now() + expires_in,
        )
        self._connect_tokens[cache_key] = token
        return token

    def _is_valid(self, ticket: ConnectAccessToken | BrokerTicket | None) -> bool:
        return ticket is not None and ticket.expires_at > self._now() + self._refresh_margin_seconds


DEFAULT_TICKET_CACHE = PushKitTicketCache()


def _credentials_cache_key(credentials: AgcClientCredentials) -> tuple[str, str]:
    return credentials.client_id, credentials.product_id


def build_push_message(
    pushkit_token: str,
    title: str,
    message: str,
    data: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "pushOptions": {
            "testMessage": True,
            "collapseKey": -1,
            "ttl": 86400,
        },
        "target": {
            "token": [pushkit_token],
        },
        "payload": {
            "notification": {
                "category": "DEVICE_REMINDER",
                "title": title,
                "body": message,
                "clickAction": {
                    "actionType": 0,
                },
            },
        },
    }


def build_push_messages(
    pushkit_token: str,
    title: str,
    message: str,
    data: Mapping[str, Any] | None = None,
    message_id_factory: Callable[[], str] | None = None,
    persistent: bool = False,
    server_instance_id: str = "",
) -> list[dict[str, Any]]:
    payload_data = dict(data or {})
    normalized_server_instance_id = server_instance_id.strip()
    if normalized_server_instance_id:
        payload_data.setdefault("server_instance_id", normalized_server_instance_id)
    message_id = _message_identity(payload_data, message_id_factory)
    tag = str(payload_data.get("tag") or message_id).strip()
    shared_data = {
        **payload_data,
        "title": title,
        "message": message,
        "message_id": message_id,
        "tag": tag,
    }
    messages = [
        {
            "pushOptions": {
                "testMessage": True,
                "collapseKey": -1,
                "ttl": 86400,
            },
            "target": {
                "token": [pushkit_token],
            },
            "payload": {
                "notification": {
                    "category": "DEVICE_REMINDER",
                    "title": title,
                    "body": message,
                    "clickAction": {
                        "actionType": 0,
                    },
                },
                "data": json.dumps(shared_data, ensure_ascii=False),
            },
        }
    ]
    if persistent:
        messages.append(
            {
                "pushOptions": {
                    "testMessage": True,
                    "collapseKey": -1,
                    "ttl": 86400,
                },
                "target": {
                    "token": [pushkit_token],
                },
                "payload": {
                    "extraData": json.dumps(shared_data, ensure_ascii=False),
                    "proxyData": "ENABLE",
                },
            }
        )
    return messages


def _message_identity(data: Mapping[str, Any], message_id_factory: Callable[[], str] | None = None) -> str:
    existing = str(data.get("message_id") or data.get("tag") or "").strip()
    if existing:
        return existing
    if message_id_factory:
        return message_id_factory()
    return f"ha-harmony-pushkit-{int(time.time() * 1000)}-{secrets.token_urlsafe(8)}"


def load_agc_client(path: str | Path) -> AgcClientCredentials:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return AgcClientCredentials(
        client_id=str(raw["client_id"]).strip(),
        client_secret=str(raw["client_secret"]).strip(),
        product_id=str(raw.get("product_id") or raw["project_id"]).strip(),
    )


async def request_connect_access_token(
    session: Any,
    credentials: AgcClientCredentials,
    token_endpoint: str = CONNECT_TOKEN_ENDPOINT,
) -> tuple[str, int]:
    body = {
        "grant_type": "client_credentials",
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
    }
    response = await _post_json(session, token_endpoint, {"Content-Type": "application/json"}, body)
    return str(response["access_token"]).strip(), int(response["expires_in"])


async def request_broker_ticket(
    session: Any,
    credentials: AgcClientCredentials,
    connect_access_token: str,
    ticket_endpoint: str = DEFAULT_TICKET_ENDPOINT,
) -> BrokerTicket:
    headers = {
        "Authorization": f"Bearer {connect_access_token}",
        "Content-Type": "application/json",
        "productId": credentials.product_id,
        "client_id": credentials.client_id,
    }
    response = await _post_json(session, ticket_endpoint, headers, None)
    return BrokerTicket(
        access_token=str(response["access_token"]).strip(),
        expires_at=int(response["expires_at"]),
        project_id=str(response["project_id"]).strip(),
    )


async def send_push_message(
    *,
    session: Any,
    credentials: AgcClientCredentials,
    pushkit_token: str,
    title: str,
    message: str,
    data: Mapping[str, Any] | None = None,
    endpoint_template: str = DEFAULT_PUSH_ENDPOINT,
    rate_limiter: DailyPushRateLimiter | None = None,
    persistent: bool = False,
    ticket_cache: PushKitTicketCache | None = None,
    server_instance_id: str = "",
) -> None:
    (rate_limiter or DEFAULT_RATE_LIMITER).check_and_increment(pushkit_token)
    ticket = await (ticket_cache or DEFAULT_TICKET_CACHE).get_broker_ticket(session, credentials)
    url = endpoint_template.format(project_id=ticket.project_id)
    bodies = build_push_messages(
        pushkit_token,
        title,
        message,
        data,
        persistent=persistent,
        server_instance_id=server_instance_id,
    )
    await _post_push_message(session, url, ticket.access_token, "0", bodies[0])
    if persistent:
        await _post_push_message(session, url, ticket.access_token, "6", bodies[1])


async def _post_json(
    session: Any,
    url: str,
    headers: dict[str, str],
    body: dict[str, Any] | None,
) -> dict[str, Any]:
    request = session.post(url, headers=headers) if body is None else session.post(url, headers=headers, json=body)
    async with request as response:
        text = await response.text()
        if response.status < 200 or response.status >= 300:
            raise PushKitClientError(f"HTTP {response.status}: {text}")
        return json.loads(text)


async def _post_push_message(session: Any, url: str, auth_token: str, push_type: str, body: dict[str, Any]) -> None:
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "push-type": push_type,
    }
    async with session.post(url, headers=headers, json=body) as response:
        text = await response.text()
        if response.status < 200 or response.status >= 300:
            raise PushKitClientError(f"HTTP {response.status}: {text}")
