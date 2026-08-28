import json
from types import SimpleNamespace

import httpx
import pytest
import respx

import spekoai.realtime as realtime_module
from spekoai.client import _realtime_session_body
from spekoai.models import RealtimeConnectParams, RealtimeSessionInfo
from spekoai.realtime import (
    _OpenAIInputAudioTrack,
    _provider_session_update,
    _provider_url,
    _translate_frame,
    _translate_provider_frames,
    open_realtime_session,
)


class FakeRTCDataChannel:
    def __init__(self) -> None:
        self.readyState = "connecting"
        self.sent: list[str] = []
        self.listeners: dict[str, object] = {}

    def on(self, event: str):
        def register(listener):
            self.listeners[event] = listener
            return listener

        return register

    def open(self) -> None:
        self.readyState = "open"
        listener = self.listeners.get("open")
        if callable(listener):
            listener()

    def send(self, payload: str) -> None:
        self.sent.append(payload)
        if json.loads(payload).get("type") == "session.update":
            listener = self.listeners.get("message")
            if callable(listener):
                listener(json.dumps({"type": "session.updated"}))

    def close(self) -> None:
        self.readyState = "closed"
        listener = self.listeners.get("close")
        if callable(listener):
            listener()


class FakeRTCPeerConnection:
    instances: list["FakeRTCPeerConnection"] = []

    def __init__(self) -> None:
        self.connectionState = "new"
        self.localDescription = None
        self.remote_description = None
        self.channel = FakeRTCDataChannel()
        self.listeners: dict[str, object] = {}
        self.input_track = None
        self.sideband_bound = False
        self.__class__.instances.append(self)

    def on(self, event: str):
        def register(listener):
            self.listeners[event] = listener
            return listener

        return register

    def addTrack(self, track) -> None:  # noqa: N802 - mirrors aiortc
        self.input_track = track

    def createDataChannel(self, label: str) -> FakeRTCDataChannel:  # noqa: N802
        assert label == "oai-events"
        return self.channel

    async def createOffer(self):  # noqa: N802
        return SimpleNamespace(type="offer", sdp="offer-sdp")

    async def setLocalDescription(self, description) -> None:  # noqa: N802
        self.localDescription = description

    async def setRemoteDescription(self, description) -> None:  # noqa: N802
        assert self.sideband_bound, "remote media enabled before billing sideband bound"
        self.remote_description = description
        self.connectionState = "connected"
        self.channel.open()

    async def close(self) -> None:
        self.connectionState = "closed"
        listener = self.listeners.get("connectionstatechange")
        if callable(listener):
            listener()


def _openai_session_info() -> RealtimeSessionInfo:
    return RealtimeSessionInfo.model_validate(
        {
            "mode": "s2s",
            "transport": "provider_direct",
            "sessionId": "11111111-1111-4111-8111-111111111111",
            "planId": "plan_openai",
            "attemptId": "att_openai",
            "provider": "openai",
            "model": "gpt-realtime",
            "adapter": "openai.realtime.v1",
            "providerTransport": "webrtc",
            "endpoint": "https://api.openai.com/v1/realtime/calls",
            "sidebandUrl": (
                "https://gateway.speko.dev/v1/sessions/"
                "11111111-1111-4111-8111-111111111111/sidebands/openai"
            ),
            "credential": {
                "kind": "bearer",
                "value": "ek-short-lived",
                "expiresAt": "2100-01-01T00:05:00Z",
            },
            "telemetry": {
                "endpoint": "https://gateway.speko.dev/v1/runtime-events",
                "token": "telemetry-token",
                "flushIntervalMs": 5000,
            },
            "reservation": {
                "id": "res_openai",
                "authorizedDurationSeconds": 300,
                "leaseExpiresAt": "2100-01-01T00:05:00Z",
                "billing": {
                    "mode": "direct_entitlement",
                    "state": "estimated",
                    "maximumAmountMicros": "30000",
                    "currency": "USD",
                },
            },
            "session": {"voice": "marin", "instructions": "Be concise."},
            "inputSampleRate": 24000,
            "outputSampleRate": 24000,
            "expiresAt": "2100-01-01T00:05:00Z",
        }
    )


def test_realtime_session_body_wraps_s2s_and_top_level_keys():
    body = _realtime_session_body(
        RealtimeConnectParams(
            agent_id="ag_1",
            provider="xai",
            model="grok-voice-fast-1.0",
            voice="sophia",
            webhook_tags={"env": "prod"},
            metadata={"k": "v"},
            ttl_seconds=600,
        )
    )
    assert body == {
        "mode": "s2s",
        "s2s": {
            "provider": "xai",
            "model": "grok-voice-fast-1.0",
            "voice": "sophia",
        },
        "agentId": "ag_1",
        "webhookTags": {"env": "prod"},
        "metadata": {"k": "v"},
        "ttlSeconds": 600,
    }


def test_realtime_session_body_accepts_dict():
    body = _realtime_session_body({"provider": "openai", "model": "gpt-realtime"})
    assert body == {"mode": "s2s", "s2s": {"provider": "openai", "model": "gpt-realtime"}}


def test_translate_frame_new_types():
    assert _translate_frame(
        {"t": "ready", "inputSampleRate": 16000, "outputSampleRate": 24000}
    ) == {"type": "ready", "input_sample_rate": 16000, "output_sample_rate": 24000}
    assert _translate_frame({"t": "interruption", "at": "assistant"}) == {
        "type": "interruption",
        "at": "assistant",
    }
    assert _translate_frame(
        {"t": "server_tool_call", "id": "st_1", "name": "search", "status": "completed"}
    ) == {
        "type": "server_tool_call",
        "id": "st_1",
        "name": "search",
        "status": "completed",
    }
    assert _translate_frame({"t": "transcript", "role": "user", "text": "hi", "final": True}) == {
        "type": "transcript",
        "role": "user",
        "text": "hi",
        "final": True,
    }


def test_provider_direct_response_validates_and_builds_xai_connection():
    info = RealtimeSessionInfo.model_validate(
        {
            "mode": "s2s",
            "transport": "provider_direct",
            "sessionId": "11111111-1111-4111-8111-111111111111",
            "planId": "plan_1",
            "attemptId": "att_1",
            "provider": "xai",
            "model": "grok-voice-fast-1.0",
            "adapter": "xai.realtime.v1",
            "providerTransport": "websocket",
            "endpoint": "wss://api.x.ai/v1/realtime",
            "credential": {
                "kind": "bearer",
                "value": "ek-short-lived",
                "expiresAt": "2100-01-01T00:05:00Z",
            },
            "telemetry": {
                "endpoint": "https://gateway.speko.dev/v1/runtime-events",
                "token": "telemetry-token",
                "flushIntervalMs": 5000,
            },
            "reservation": {
                "id": "res_1",
                "authorizedDurationSeconds": 300,
                "leaseExpiresAt": "2100-01-01T00:05:00Z",
                "billing": {
                    "mode": "direct_entitlement",
                    "state": "estimated",
                    "maximumAmountMicros": "30000",
                    "currency": "USD",
                },
            },
            "session": {
                "voice": "Ara",
                "instructions": "Be concise.",
                "tools": [
                    {
                        "name": "lookup",
                        "description": "Look up an order.",
                        "parameters": {"type": "object"},
                    }
                ],
            },
            "inputSampleRate": 24000,
            "outputSampleRate": 24000,
            "expiresAt": "2100-01-01T00:05:00Z",
        }
    )

    assert _provider_url(info) == "wss://api.x.ai/v1/realtime?model=grok-voice-fast-1.0"
    update = _provider_session_update(info)
    assert update["session"]["voice"] == "Ara"
    assert update["session"]["turn_detection"] == {"type": "server_vad"}
    assert update["session"]["tools"] == [
        {
            "type": "function",
            "name": "lookup",
            "description": "Look up an order.",
            "parameters": {"type": "object"},
        }
    ]

    frames = _translate_provider_frames(
        info,
        {
            "type": "response.function_call_arguments.done",
            "call_id": "call_1",
            "name": "lookup",
            "arguments": '{"order_id":"123"}',
        },
    )
    assert frames == [
        {
            "type": "tool_call",
            "call_id": "call_1",
            "name": "lookup",
            "arguments": '{"order_id":"123"}',
        }
    ]


def test_realtime_idempotency_key_is_not_sent_as_provider_config():
    body = _realtime_session_body(
        RealtimeConnectParams(
            provider="google",
            model="gemini-3.1-flash-live-preview",
            idempotency_key="retry-me",
        )
    )
    assert "idempotencyKey" not in body
    assert "idempotencyKey" not in body["s2s"]


@respx.mock
async def test_openai_uses_webrtc_and_binds_sideband_before_media(monkeypatch):
    FakeRTCPeerConnection.instances = []
    monkeypatch.setattr(realtime_module, "RTCPeerConnection", FakeRTCPeerConnection)
    provider_route = respx.post("https://api.openai.com/v1/realtime/calls").mock(
        return_value=httpx.Response(
            201,
            text="answer-sdp",
            headers={"Location": "/v1/realtime/calls/call_12345678"},
        )
    )

    def bind_sideband(request: httpx.Request) -> httpx.Response:
        peer = FakeRTCPeerConnection.instances[0]
        peer.sideband_bound = True
        return httpx.Response(201, json={"status": "bound"})

    sideband_route = respx.post(
        "https://gateway.speko.dev/v1/sessions/"
        "11111111-1111-4111-8111-111111111111/sidebands/openai"
    ).mock(side_effect=bind_sideband)
    telemetry_route = respx.post("https://gateway.speko.dev/v1/runtime-events").mock(
        return_value=httpx.Response(202, json={"accepted": 2, "deduplicated": 0})
    )

    session = await open_realtime_session(_openai_session_info())
    peer = FakeRTCPeerConnection.instances[0]
    assert provider_route.called
    provider_request = provider_route.calls.last.request
    assert provider_request.headers["Authorization"] == "Bearer ek-short-lived"
    assert provider_request.headers["Content-Type"].startswith("multipart/form-data;")
    assert b"offer-sdp" in provider_request.content
    assert b'"model":"gpt-realtime"' in provider_request.content
    assert sideband_route.called
    sideband_request = sideband_route.calls.last.request
    assert sideband_request.headers["Authorization"] == "Bearer telemetry-token"
    assert json.loads(sideband_request.content) == {
        "attempt_id": "att_openai",
        "provider_session_id": "call_12345678",
    }
    assert peer.remote_description.sdp == "answer-sdp"
    assert json.loads(peer.channel.sent[0])["type"] == "session.update"

    await session.send_audio(bytes(480))
    assert isinstance(peer.input_track, _OpenAIInputAudioTrack)
    await session.commit()
    assert peer.input_track._queue.qsize() == 1
    await session.close()
    assert telemetry_route.called


def test_openai_provider_url_refuses_websocket_downgrade():
    with pytest.raises(ValueError, match="requires its negotiated WebRTC"):
        _provider_url(_openai_session_info())
