from spekoai.client import _realtime_session_body
from spekoai.models import RealtimeConnectParams
from spekoai.realtime import _translate_frame


def test_realtime_session_body_wraps_s2s_and_top_level_keys():
    body = _realtime_session_body(
        RealtimeConnectParams(
            agent_id="ag_1",
            provider="speko-lab",
            model="rt-1",
            voice="sophia",
            webhook_tags={"env": "prod"},
            metadata={"k": "v"},
            ttl_seconds=600,
        )
    )
    assert body == {
        "mode": "s2s",
        "s2s": {"provider": "speko-lab", "model": "rt-1", "voice": "sophia"},
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
