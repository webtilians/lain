"""Reality opt-in diagnostic path: no live provider, no private dialogue logs."""
import json

from server.world_core import generated_entities as reality


class FakeResponse:
    def __init__(self, payload):
        self._raw = json.dumps({
            "choices": [{"message": {"content": payload}}],
        }).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, size):
        return self._raw[:size]


def test_proposal_parser_checks_all_original_npc_replies_when_opted_in(monkeypatch, capsys):
    monkeypatch.setenv("LAIN_REALITY_GENERATION", "1")
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.setenv("LAIN_LLM_MODEL", "local-fixture")
    monkeypatch.setenv("LAIN_REALITY_TRACE", "1")
    monkeypatch.setattr(
        reality, "urlopen",
        lambda *a, **kw: FakeResponse(
            "```json\n"
            '{"proposal":{"name":"Eco","premise":"Un reflejo en la Wired",'
            '"goal":"OBSERVE_WORLD"}}'
            "\n```"
        ),
    )
    # No keyword gate: even nonstandard metaphors reach the model parser.
    proposal = reality.suggest_entity(
        "AGENT_NORA", "Entre los cables se ha abierto otra mirada.",
        location="STATION",
    )
    assert proposal is not None and proposal.name == "Eco"
    assert "PARSER_REQUESTED" in capsys.readouterr().out
    assert "PROPOSAL_ACCEPTED" in capsys.readouterr().out


def test_generation_trace_reports_missing_model_and_no_proposal_without_text(monkeypatch, capsys):
    monkeypatch.setenv("LAIN_REALITY_TRACE", "1")
    monkeypatch.delenv("LAIN_REALITY_GENERATION", raising=False)
    assert reality.suggest_entity(
        "AGENT_NORA", "mensaje personal que no debe imprimirse",
        location="STATION",
    ) is None
    assert "GENERATION_DISABLED" in capsys.readouterr().out

    monkeypatch.setenv("LAIN_REALITY_GENERATION", "1")
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.delenv("LAIN_LLM_MODEL", raising=False)
    assert reality.suggest_entity(
        "AGENT_NORA", "mensaje personal que no debe imprimirse",
        location="STATION",
    ) is None
    assert "LLM_MODEL_NOT_CONFIGURED" in capsys.readouterr().out

    monkeypatch.setenv("LAIN_LLM_MODEL", "local-fixture")
    monkeypatch.setattr(
        reality, "urlopen",
        lambda *a, **kw: FakeResponse('{"proposal":null}'),
    )
    assert reality.suggest_entity(
        "AGENT_NORA", "mensaje personal que no debe imprimirse",
        location="STATION",
    ) is None
    result = capsys.readouterr().out
    assert "NO_NEW_ENTITY_IN_REPLY" in result
    assert "mensaje personal" not in result


def test_unexpected_parser_format_is_diagnostic_not_a_world_mutation(monkeypatch, capsys):
    monkeypatch.setenv("LAIN_REALITY_GENERATION", "1")
    monkeypatch.setenv("LAIN_LLM_ENABLED", "1")
    monkeypatch.setenv("LAIN_LLM_MODEL", "local-fixture")
    monkeypatch.setenv("LAIN_REALITY_TRACE", "1")
    monkeypatch.setattr(
        reality, "urlopen",
        lambda *a, **kw: FakeResponse("Esta respuesta no es JSON."),
    )
    assert reality.suggest_entity(
        "AGENT_NORA", "Una nueva presencia parece posible", location="STATION",
    ) is None
    assert "PARSER_ERROR_JSONDECODEERROR" in capsys.readouterr().out
