from __future__ import annotations

from dataclasses import dataclass
import json
import secrets
import time
from pathlib import Path
from typing import Any, Callable, Mapping

import jwt

from .const import DEFAULT_PUSH_ENDPOINT

JWT_TTL_SECONDS = 300

@dataclass(frozen=True)
class PushKitAuth:
    project_id: str
    key_id: str
    sub_account: str
    private_key: str
    token_uri: str

class PushKitClientError(Exception):
    """Raised when Huawei Push Kit rejects a request."""

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
) -> list[dict[str, Any]]:
    payload_data = dict(data or {})
    message_id = _message_identity(payload_data, message_id_factory)
    tag = str(payload_data.get("tag") or message_id).strip()
    shared_data = {
        **payload_data,
        "title": title,
        "message": message,
        "message_id": message_id,
        "tag": tag,
    }
    return [
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
        },
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
        },
    ]

def _message_identity(data: Mapping[str, Any], message_id_factory: Callable[[], str] | None = None) -> str:
    existing = str(data.get("message_id") or data.get("tag") or "").strip()
    if existing:
        return existing
    if message_id_factory:
        return message_id_factory()
    return f"ha-harmony-pushkit-{int(time.time() * 1000)}-{secrets.token_urlsafe(8)}"

def load_service_account(path: str | Path) -> PushKitAuth:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return PushKitAuth(
        project_id=str(raw["project_id"]).strip(),
        key_id=str(raw["key_id"]).strip(),
        sub_account=str(raw["sub_account"]).strip(),
        private_key=str(raw["private_key"]),
        token_uri=str(raw["token_uri"]).strip(),
    )

def build_jwt(
    auth: PushKitAuth,
    now: int | None = None,
    signer: Callable[[dict[str, Any], str, str, dict[str, str]], str] | None = None,
) -> str:
    issued_at = int(time.time() if now is None else now)
    payload = {
        "iss": auth.sub_account,
        "sub": auth.sub_account,
        "aud": auth.token_uri,
        "iat": issued_at,
        "exp": issued_at + JWT_TTL_SECONDS,
    }
    headers = {"kid": auth.key_id}
    encode = signer or jwt.encode
    return encode(payload, auth.private_key, "RS256", headers)

async def send_push_message(
    *,
    session: Any,
    auth: PushKitAuth,
    pushkit_token: str,
    title: str,
    message: str,
    data: Mapping[str, Any] | None = None,
    endpoint_template: str = DEFAULT_PUSH_ENDPOINT,
    jwt_signer: Callable[[dict[str, Any], str, str, dict[str, str]], str] | None = None,
) -> None:
    auth_token = build_jwt(auth, signer=jwt_signer)
    url = endpoint_template.format(project_id=auth.project_id)
    bodies = build_push_messages(pushkit_token, title, message, data)
    await _post_push_message(session, url, auth_token, "0", bodies[0])
    await _post_push_message(session, url, auth_token, "6", bodies[1])

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
