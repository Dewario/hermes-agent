"""FABLE5 L7: a failed session-DB persist must reach the user, not just a
log line. One notice per session (persist runs on many exit paths)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_agent():
    from run_agent import AIAgent
    agent = AIAgent(
        api_key="test-key",
        base_url="https://example.com/v1",
        model="test/model",
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
    )
    return agent


class TestPersistFailureNotice:
    def test_failed_persist_notifies_user_once(self):
        agent = _make_agent()
        db = MagicMock()
        db.append_message.side_effect = OSError("disk full")
        agent._session_db = db
        agent._session_db_created = True
        agent.session_id = "sess-l7"

        messages = [{"role": "user", "content": "hello"}]
        with patch.object(agent, "_emit_warning") as warn, \
                patch.object(agent, "_safe_print") as sp:
            agent._flush_messages_to_session_db(messages, [])
            agent._flush_messages_to_session_db(messages, [])  # second failure

        assert warn.call_count == 1, (
            "user must be warned exactly once per session — zero means the "
            "failure is silent, repeated means spam on every exit-path flush"
        )
        notice = warn.call_args[0][0]
        assert "save failed" in notice.lower()
        assert sp.call_count == 1

    def test_successful_persist_does_not_notify(self):
        agent = _make_agent()
        db = MagicMock()
        agent._session_db = db
        agent._session_db_created = True
        agent.session_id = "sess-ok"

        with patch.object(agent, "_emit_warning") as warn:
            agent._flush_messages_to_session_db(
                [{"role": "user", "content": "hello"}], [])

        assert warn.call_count == 0
        assert db.append_message.called
