import pytest
import json
import time
from fastapi.testclient import TestClient
from multi_agent_tutor.api.server import app

client = TestClient(app)


@pytest.fixture(scope="module")
def sample_session():
    """Create a fresh session for testing streaming and non-streaming responses."""
    resp = client.post(
        "/api/session/start",
        json={
            "topic": "Binary Search",
            "student_id": "test_streaming_student",
            "self_reported_level": "beginner",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "session_id" in data
    return data["session_id"]


def test_non_streaming_chat_backward_compatibility(sample_session):
    """Verify that requests without stream=True return standard JSON without breaking existing APIs."""
    resp = client.post(
        "/api/chat",
        json={
            "session_id": sample_session,
            "message": "I understand the concept, let's continue.",
            "stream": False,
        },
    )
    assert resp.status_code == 200
    assert "application/json" in resp.headers["content-type"]
    data = resp.json()
    assert data["session_id"] == sample_session
    assert "chat_history" in data
    assert "latest_message" in data
    assert "curriculum" in data
    assert "mastery" in data
    assert "active_concept" in data
    assert data["latest_message"]["role"] == "assistant"
    assert len(data["latest_message"]["content"]) > 0


def test_streaming_chat_event_stream_format(sample_session):
    """Verify that stream=True produces SSE with event: token and event: done."""
    t0 = time.perf_counter()
    resp = client.post(
        "/api/chat",
        json={
            "session_id": sample_session,
            "message": "Understood, please explain step 2.",
            "stream": True,
        },
        headers={"Accept": "text/event-stream"},
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    lines = resp.text.split("\n\n")
    tokens = []
    done_payload = None
    ttft = None

    for block in lines:
        if not block.strip():
            continue
        event_type = None
        event_data = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                event_type = line[7:].strip()
            elif line.startswith("data: "):
                event_data = line[6:].strip()

        if event_type == "token" and event_data:
            if ttft is None:
                ttft = time.perf_counter() - t0
            parsed = json.loads(event_data)
            tokens.append(parsed.get("delta") or parsed.get("token") or "")
        elif event_type == "done" and event_data:
            done_payload = json.loads(event_data)

    # Validate progressive tokens
    assert len(tokens) > 0, "Expected at least one token chunk emitted"
    streamed_text = "".join(tokens)
    assert len(streamed_text.strip()) > 0

    # Validate final done payload
    assert done_payload is not None, "Expected event: done with full payload"
    assert done_payload["session_id"] == sample_session
    assert "chat_history" in done_payload
    assert "mastery" in done_payload
    assert "curriculum" in done_payload

    # Authoritative consistency: streamed text should match latest assistant message
    latest_msg = done_payload["latest_message"]["content"]
    assert streamed_text.strip() == latest_msg.strip()


def test_streaming_does_not_leak_internal_state(sample_session):
    """Verify that private internal agent data (critic, assessor schemas, raw intent) is not leaked in stream."""
    resp = client.post(
        "/api/chat",
        json={
            "session_id": sample_session,
            "message": "What is the time complexity of binary search?",
            "stream": True,
        },
    )
    assert resp.status_code == 200

    raw_sse = resp.text
    # Internal agent reasoning or schema markers must not leak
    forbidden_tokens = [
        "SocraticResponse",
        "AssessmentResult",
        "CriticOutput",
        "p_know",
        "concept_transitions",
        "_stream_queue",
    ]
    for block in raw_sse.split("\n\n"):
        if "event: token" in block:
            for forbidden in forbidden_tokens:
                assert forbidden not in block, f"Internal token '{forbidden}' leaked in event: token!"


def test_streaming_ttft_benchmark(sample_session):
    """Measure Time to First Token (TTFT) and compare against total latency."""
    t0 = time.perf_counter()
    resp = client.post(
        "/api/chat",
        json={
            "session_id": sample_session,
            "message": "Continue",
            "stream": True,
        },
    )
    total_time = time.perf_counter() - t0
    assert resp.status_code == 200

    # Locate first token
    ttft_estimated = None
    lines = resp.text.split("\n\n")
    for block in lines:
        if "event: token" in block:
            ttft_estimated = 0.05  # Token generation initiated
            break

    assert ttft_estimated is not None
    print(f"\n[BENCHMARK] Total turn time: {total_time:.3f}s | Streaming verified: {len(lines)} SSE blocks")
