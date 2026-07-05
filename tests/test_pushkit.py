import json
from pathlib import Path
import re

import jwt
import pytest

from custom_components.ha_harmony_pushkit.pushkit import (
    PushKitAuth,
    PushKitClientError,
    build_jwt,
    build_push_message,
    build_push_messages,
    load_service_account,
    send_push_message,
)


def test_build_push_message_uses_huawei_notification_payload():
    body = build_push_message(
        pushkit_token="token-123",
        title="Door",
        message="Front door opened",
        data={"entity_id": "binary_sensor.front_door", "critical": True},
    )

    assert body == {
        "pushOptions": {
            "testMessage": True,
            "collapseKey": -1,
            "ttl": 86400,
        },
        "target": {
            "token": ["token-123"],
        },
        "payload": {
            "notification": {
                "category": "DEVICE_REMINDER",
                "title": "Door",
                "body": "Front door opened",
                "clickAction": {
                    "actionType": 0,
                },
            },
        },
    }


def test_build_push_messages_uses_shared_message_identity_for_notification_and_background_payloads():
    bodies = build_push_messages(
        pushkit_token="token-123",
        title="Door",
        message="Front door opened",
        data={"entity_id": "binary_sensor.front_door"},
        message_id_factory=lambda: "message-1",
    )

    assert len(bodies) == 2
    notification_body = bodies[0]
    background_body = bodies[1]
    notification_data = json.loads(notification_body["payload"]["data"])
    background_extra = json.loads(background_body["payload"]["extraData"])

    assert notification_data["message_id"] == "message-1"
    assert notification_data["tag"] == "message-1"
    assert background_extra["message_id"] == "message-1"
    assert background_extra["tag"] == "message-1"
    assert background_extra["title"] == "Door"
    assert background_extra["message"] == "Front door opened"
    assert background_body["payload"]["proxyData"] == "ENABLE"


def test_build_push_messages_reuses_existing_message_id():
    bodies = build_push_messages(
        pushkit_token="token-123",
        title="Door",
        message="Front door opened",
        data={"message_id": "existing-id", "tag": "existing-tag"},
        message_id_factory=lambda: "generated-id",
    )

    notification_data = json.loads(bodies[0]["payload"]["data"])
    background_extra = json.loads(bodies[1]["payload"]["extraData"])

    assert notification_data["message_id"] == "existing-id"
    assert notification_data["tag"] == "existing-tag"
    assert background_extra["message_id"] == "existing-id"
    assert background_extra["tag"] == "existing-tag"


def test_load_service_account_reads_agc_fields(tmp_path: Path):
    key_file = tmp_path / "jwt.json"
    key_file.write_text(
        json.dumps(
            {
                "project_id": "project-1",
                "key_id": "key-1",
                "private_key": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----\n",
                "sub_account": "sub-1",
                "token_uri": "https://oauth-login.cloud.huawei.com/oauth2/v3/token",
            }
        ),
        encoding="utf-8",
    )

    auth = load_service_account(key_file)

    assert auth.project_id == "project-1"
    assert auth.key_id == "key-1"
    assert auth.sub_account == "sub-1"
    assert auth.token_uri == "https://oauth-login.cloud.huawei.com/oauth2/v3/token"
    assert "PRIVATE KEY" in auth.private_key


def test_build_jwt_uses_service_account_subject_and_key_id():
    test_secret = "test-secret-with-enough-length-for-hs256"
    auth = PushKitAuth(
        project_id="project-1",
        key_id="key-1",
        sub_account="sub-1",
        private_key=test_secret,
        token_uri="https://oauth-login.cloud.huawei.com/oauth2/v3/token",
    )

    token = build_jwt(
        auth,
        now=1000,
        signer=lambda payload, key, algorithm, headers: jwt.encode(
            payload,
            key,
            algorithm="HS256",
            headers=headers,
        ),
    )
    header = jwt.get_unverified_header(token)
    payload = jwt.decode(
        token,
        test_secret,
        algorithms=["HS256"],
        options={"verify_aud": False, "verify_exp": False},
    )

    assert header["kid"] == "key-1"
    assert payload["iss"] == "sub-1"
    assert payload["sub"] == "sub-1"
    assert payload["aud"] == "https://oauth-login.cloud.huawei.com/oauth2/v3/token"
    assert payload["iat"] == 1000
    assert payload["exp"] == 1300


class FakeResponse:
    def __init__(self, status: int, body: str):
        self.status = status
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return self._body


class FakeSession:
    def __init__(self, *responses: FakeResponse):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, *, headers=None, json=None, data=None):
        self.calls.append({"url": url, "headers": headers or {}, "json": json, "data": data})
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_send_push_message_posts_jwt_to_v3_push_endpoint():
    session = FakeSession(
        FakeResponse(200, '{"code":"80000000"}'),
        FakeResponse(200, '{"code":"80000000"}'),
    )
    auth = PushKitAuth(
        project_id="project-1",
        key_id="key-1",
        sub_account="sub-1",
        private_key="secret",
        token_uri="https://oauth-login.cloud.huawei.com/oauth2/v3/token",
    )

    await send_push_message(
        session=session,
        auth=auth,
        pushkit_token="token-123",
        title="Door",
        message="Front door opened",
        data={},
        endpoint_template="https://example.test/v3/{project_id}/messages:send",
        jwt_signer=lambda payload, key, algorithm, headers: "signed-jwt",
    )

    assert len(session.calls) == 2
    assert session.calls[0] == {
        "url": "https://example.test/v3/project-1/messages:send",
        "headers": {
            "Authorization": "Bearer signed-jwt",
            "Content-Type": "application/json",
            "push-type": "0",
        },
        "json": build_push_messages(
            "token-123",
            "Door",
            "Front door opened",
            {},
            message_id_factory=lambda: json.loads(session.calls[0]["json"]["payload"]["data"])["message_id"],
        )[0],
        "data": None,
    }
    assert session.calls[1] == {
        "url": "https://example.test/v3/project-1/messages:send",
        "headers": {
            "Authorization": "Bearer signed-jwt",
            "Content-Type": "application/json",
            "push-type": "6",
        },
        "json": build_push_messages(
            "token-123",
            "Door",
            "Front door opened",
            {},
            message_id_factory=lambda: json.loads(session.calls[0]["json"]["payload"]["data"])["message_id"],
        )[1],
        "data": None,
    }
    assert re.match(
        r"ha-harmony-pushkit-\d+-[a-zA-Z0-9_-]+",
        json.loads(session.calls[0]["json"]["payload"]["data"])["message_id"],
    )


@pytest.mark.asyncio
async def test_send_push_message_reuses_data_message_id_for_both_push_types():
    session = FakeSession(
        FakeResponse(200, '{"code":"80000000"}'),
        FakeResponse(200, '{"code":"80000000"}'),
    )
    auth = PushKitAuth(
        project_id="project-1",
        key_id="key-1",
        sub_account="sub-1",
        private_key="secret",
        token_uri="https://oauth-login.cloud.huawei.com/oauth2/v3/token",
    )

    await send_push_message(
        session=session,
        auth=auth,
        pushkit_token="token-123",
        title="Door",
        message="Front door opened",
        data={"message_id": "message-1"},
        endpoint_template="https://example.test/v3/{project_id}/messages:send",
        jwt_signer=lambda payload, key, algorithm, headers: "signed-jwt",
    )

    assert [call["headers"]["push-type"] for call in session.calls] == ["0", "6"]
    assert json.loads(session.calls[0]["json"]["payload"]["data"])["message_id"] == "message-1"
    assert json.loads(session.calls[1]["json"]["payload"]["extraData"])["message_id"] == "message-1"


@pytest.mark.asyncio
async def test_send_push_message_posts_background_payload_after_notification_payload():
    session = FakeSession(
        FakeResponse(200, '{"code":"80000000"}'),
        FakeResponse(200, '{"code":"80000000"}'),
    )
    auth = PushKitAuth(
        project_id="project-1",
        key_id="key-1",
        sub_account="sub-1",
        private_key="secret",
        token_uri="https://oauth-login.cloud.huawei.com/oauth2/v3/token",
    )

    await send_push_message(
        session=session,
        auth=auth,
        pushkit_token="token-123",
        title="Door",
        message="Front door opened",
        data={"message_id": "message-1"},
        endpoint_template="https://example.test/v3/{project_id}/messages:send",
        jwt_signer=lambda payload, key, algorithm, headers: "signed-jwt",
    )

    assert session.calls == [
        {
            "url": "https://example.test/v3/project-1/messages:send",
            "headers": {
                "Authorization": "Bearer signed-jwt",
                "Content-Type": "application/json",
                "push-type": "0",
            },
            "json": build_push_messages("token-123", "Door", "Front door opened", {"message_id": "message-1"})[0],
            "data": None,
        },
        {
            "url": "https://example.test/v3/project-1/messages:send",
            "headers": {
                "Authorization": "Bearer signed-jwt",
                "Content-Type": "application/json",
                "push-type": "6",
            },
            "json": build_push_messages("token-123", "Door", "Front door opened", {"message_id": "message-1"})[1],
            "data": None,
        }
    ]


@pytest.mark.asyncio
async def test_send_push_message_raises_on_huawei_error():
    session = FakeSession(
        FakeResponse(400, '{"code":"bad"}'),
    )
    auth = PushKitAuth(
        project_id="project-1",
        key_id="key-1",
        sub_account="sub-1",
        private_key="secret",
        token_uri="https://oauth-login.cloud.huawei.com/oauth2/v3/token",
    )

    with pytest.raises(PushKitClientError, match="HTTP 400"):
        await send_push_message(
            session=session,
            auth=auth,
            pushkit_token="token-123",
            title="Door",
            message="Front door opened",
            data={},
            endpoint_template="https://example.test/v3/{project_id}/messages:send",
            jwt_signer=lambda payload, key, algorithm, headers: "signed-jwt",
        )

