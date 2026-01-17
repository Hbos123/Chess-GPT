import pytest

from session_store import InMemorySessionStore


def test_session_prefix_is_stable_and_append_only():
    store = InMemorySessionStore(ttl_seconds=60)
    s = store.get_or_create("s1", "SYSTEM")
    assert s.system_prompt == "SYSTEM"
    assert s.working_context == ""

    store.append_user("s1", "hi")
    store.append_assistant("s1", "hello")
    after_1 = store.get("s1").working_context
    assert "USER: hi" in after_1
    assert "ASSISTANT: hello" in after_1

    store.append_user("s1", "next")
    store.append_assistant("s1", "ok")
    after_2 = store.get("s1").working_context
    # Must only grow (append-only)
    assert after_2.startswith(after_1)


def test_session_system_prompt_mismatch_raises():
    store = InMemorySessionStore(ttl_seconds=60)
    store.get_or_create("s1", "SYSTEM_A")
    with pytest.raises(ValueError):
        store.get_or_create("s1", "SYSTEM_B")





