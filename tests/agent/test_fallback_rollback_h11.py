"""FABLE5 H11: try_activate_fallback must roll back a partially-applied
identity when activation fails partway, instead of leaving the agent with a
half-applied fallback (e.g. api_mode='anthropic_messages' but no client built)
for the next chain entry / chain exhaustion.
"""

from __future__ import annotations

from types import SimpleNamespace

import agent.chat_completion_helpers as ch


def _primary_agent(chain):
    return SimpleNamespace(
        provider="openai-codex",
        model="gpt-5.4-mini",
        base_url="https://api.openai.com/v1",
        api_mode="codex_responses",
        api_key="primary-key",
        _config_context_length=None,
        _anthropic_api_key=None,
        _anthropic_base_url=None,
        _anthropic_client=None,
        client="PRIMARY_CLIENT",
        _client_kwargs={"api_key": "primary-key"},
        _use_prompt_caching=False,
        _use_native_cache_layout=False,
        _fallback_activated=False,
        _credential_pool=None,
        _is_anthropic_oauth=False,
        _fallback_index=0,
        _fallback_chain=chain,
        _unavailable_fallback_keys=set(),
        _primary_runtime={"provider": "openai-codex"},
        _transport_cache={},
        _is_azure_openai_url=lambda u: False,
        _is_direct_openai_url=lambda u: False,
        _provider_model_requires_responses_api=lambda m, provider=None: False,
    )


def test_rollback_restores_identity_on_activation_failure(monkeypatch):
    agent = _primary_agent([{"provider": "anthropic", "model": "claude-x"}])
    agent._try_activate_fallback = lambda reason=None: ch.try_activate_fallback(agent, reason)

    fake_client = SimpleNamespace(base_url="https://api.anthropic.com", api_key="ak")

    import agent.auxiliary_client as aux
    monkeypatch.setattr(aux, "resolve_provider_client", lambda *a, **k: (fake_client, "claude-x"))
    monkeypatch.setattr(ch, "_fallback_entry_unavailable_without_network", lambda a, fb: None)

    import agent.anthropic_adapter as aa

    def _boom(*a, **k):
        raise RuntimeError("simulated mid-activation failure")

    monkeypatch.setattr(aa, "build_anthropic_client", _boom)
    monkeypatch.setattr(aa, "resolve_anthropic_token", lambda: "tok")
    monkeypatch.setattr(aa, "_is_oauth_token", lambda k: False)

    result = ch.try_activate_fallback(agent, None)

    # Chain had one entry; it failed and rolled back -> exhausted -> False.
    assert result is False
    # Identity fully restored to the primary (not the half-applied anthropic entry).
    assert agent.provider == "openai-codex"
    assert agent.model == "gpt-5.4-mini"
    assert agent.api_mode == "codex_responses"
    assert agent.base_url == "https://api.openai.com/v1"
    assert agent.api_key == "primary-key"
    assert agent.client == "PRIMARY_CLIENT"
    assert agent._anthropic_api_key is None
    assert agent._anthropic_base_url is None
    assert agent._fallback_activated is False


def test_rollback_does_not_compound_across_failing_entries(monkeypatch):
    """Two consecutive entries fail to activate. Rollback must restore the
    primary identity after each — corruption must not accumulate so that after
    the chain is exhausted the agent is byte-for-byte back on the primary."""
    agent = _primary_agent([
        {"provider": "anthropic", "model": "claude-a"},
        {"provider": "anthropic", "model": "claude-b"},
    ])
    agent._try_activate_fallback = lambda reason=None: ch.try_activate_fallback(agent, reason)

    import agent.auxiliary_client as aux

    def _resolve(provider, model, *a, **k):
        return SimpleNamespace(base_url="https://api.anthropic.com", api_key="ak"), model

    monkeypatch.setattr(aux, "resolve_provider_client", _resolve)
    monkeypatch.setattr(ch, "_fallback_entry_unavailable_without_network", lambda a, fb: None)

    import agent.anthropic_adapter as aa

    def _boom(*a, **k):
        raise RuntimeError("anthropic build fails")

    monkeypatch.setattr(aa, "build_anthropic_client", _boom)
    monkeypatch.setattr(aa, "resolve_anthropic_token", lambda: "tok")
    monkeypatch.setattr(aa, "_is_oauth_token", lambda k: False)

    result = ch.try_activate_fallback(agent, None)

    # Both entries attempted and rolled back -> exhausted -> False, primary intact.
    assert result is False
    assert agent._fallback_index == 2  # both chain entries were tried
    assert agent.provider == "openai-codex"
    assert agent.model == "gpt-5.4-mini"
    assert agent.api_mode == "codex_responses"
    assert agent.base_url == "https://api.openai.com/v1"
    assert agent.api_key == "primary-key"
    assert agent.client == "PRIMARY_CLIENT"
    assert agent._anthropic_api_key is None
    assert agent._fallback_activated is False
