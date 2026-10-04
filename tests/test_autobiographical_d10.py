"""D10 deterministic checks: private history, acquisition context and saves."""
import pytest

from server.world_core import llm_dialogue
from server.world_core.agent_context import AgentContextBuilder
from server.world_core.autobiographical_memory import knowledge_timeline
from server.world_core.database import get_connection, save_agent
from server.world_core.episodic_memory import (
    initialize_memory_provenance, retrieve_memories, save_episodic_memory,
)
from server.world_core.free_conversation import say_to_player_conversation
from server.world_core.interactions import create_or_get_interaction
from server.world_core.player_conversation import (
    initialize_conversation_turns, start_player_conversation,
)
from server.world_core.simulation import Simulation


def contact(actor='AGENT_K'):
    sim = Simulation()
    for agent in (sim.player, sim.k.agent, sim.nora.agent):
        agent.location = 'STATION'
        save_agent(agent)
    initialize_conversation_turns()
    interaction, _ = create_or_get_interaction(
        'PLAYER_1', actor, 'PLAYER_INITIATED_CONVERSATION', 'UNKNOWN', sim.minute,
    )
    return sim, interaction, start_player_conversation(actor, sim.minute)


def tell_pair():
    sim, interaction, result = contact()
    for text in ('Mi perro se llama Tango.', 'Mi perro ahora se llama Lupo.'):
        result = say_to_player_conversation('AGENT_K', text, result['turn_id'], 10)
    return sim, interaction, result


@pytest.mark.parametrize('question,contains,absent', [
    ('¿Cómo se llama mi perro?', 'Lupo', 'Tango'),
    ('¿Cómo se llama mi perro ahora?', 'Lupo', 'Tango'),
    ('¿Cómo se llamaba mi perro de antes?', 'Tango', None),
    ('¿Qué te dije primero sobre mi perro?', 'Tango', 'Lupo'),
    ('¿Qué ha cambiado sobre mi perro?', 'Tango', None),
])
def test_temporal_dialogue_without_provider(monkeypatch, question, contains, absent):
    _, _, result = tell_pair()
    monkeypatch.setenv('LAIN_LLM_ENABLED', '1')
    def forbidden(*args, **kwargs):
        pytest.fail('Temporal recall must not need a model')
    monkeypatch.setattr(llm_dialogue, '_provider_reply', forbidden)
    reply = say_to_player_conversation('AGENT_K', question, result['turn_id'], 11)
    assert reply['response_source'] == 'GROUNDED_RECALL'
    assert contains in reply['line']
    if absent:
        assert absent not in reply['line']
    if 'antes' in question:
        assert reply['line'].index('Tango') < reply['line'].index('Lupo')


def test_private_timeline_and_unknown_previous():
    _, _, result = contact()
    result = say_to_player_conversation('AGENT_K', 'Mi perro se llama Tango.', result['turn_id'], 1)
    reply = say_to_player_conversation('AGENT_K', '¿Cómo se llamaba mi perro antes?', result['turn_id'], 2)
    assert 'no conozco una anterior' in reply['line']
    context = AgentContextBuilder().build('AGENT_NORA', retrieval_query='¿Cómo se llama mi perro?')
    assert context['knowledge_timeline']['versions'] == []
    assert 'Tango' not in str(context)
    reply = llm_dialogue.generate_dialogue_reply(context, 'FREE_TEXT', '¿Cómo se llama mi perro?')
    assert 'No recuerdo' in reply.text


def test_episode_snapshot_survives_move_and_reopen():
    sim, _, _ = tell_pair()
    sim.k.agent.location = 'APARTMENT'
    save_agent(sim.k.agent)
    first = retrieve_memories('AGENT_K', 'perro')
    initialize_memory_provenance()
    second = retrieve_memories('AGENT_K', 'perro')
    assert first == second
    assert len(first) == 2
    assert all(row['location'] == 'STATION' for row in first)
    assert all(row['received_minute'] == 10 for row in first)
    assert all(row['owner_id'] == 'AGENT_K' for row in first)
    assert all(row['origin_turn_id'] and row['interaction_id'] for row in first)
    timeline = knowledge_timeline('AGENT_K', '¿Qué ha cambiado sobre mi perro?')
    assert [v['knowledge_status'] for v in timeline['versions']] == ['EARLIER_TESTIMONY', 'CURRENT_TESTIMONY']
    assert timeline['versions'][0]['origin_turn_id'] < timeline['versions'][1]['origin_turn_id']


def test_legacy_memory_not_assigned_invented_time_or_place():
    contact()
    with get_connection() as conn:
        conn.execute("INSERT INTO agent_memory(agent_id,memory) VALUES ('AGENT_K','Old encounter')")
    result = retrieve_memories('AGENT_K')[0]
    assert result['source_kind'] == 'LEGACY_UNCLASSIFIED'
    assert result['location'] is None
    assert result['received_minute'] is None
    assert result['chronology_known'] is False


def test_legacy_turns_and_long_history_remain_private_and_bounded():
    _, interaction, _ = contact()
    with get_connection() as conn:
        for number in range(16):
            conn.execute('''INSERT INTO player_conversation_turns
                (interaction_id,speaker_id,text,source,minute) VALUES (?,?,?,?,?)''',
                (interaction.id, 'PLAYER_1', f'Mi perro se llama Nombre{number}.', 'PLAYER_FREE_TEXT', number))
        conn.execute('''INSERT INTO player_conversation_turns
            (interaction_id,speaker_id,text,source,minute) VALUES (?,?,?,?,?)''',
            (interaction.id, 'AGENT_K', 'Mi perro se llama Inventado.', 'LLM_DIALOGUE', 20))
    result = knowledge_timeline('AGENT_K', '¿Qué ha cambiado sobre mi perro?')
    assert result['total_versions'] == 16 and result['truncated']
    assert len(result['versions']) == 12
    assert result['versions'][0]['reported_value'] == 'Nombre0'
    assert result['versions'][-1]['reported_value'] == 'Nombre15'
    assert knowledge_timeline('AGENT_NORA', '¿Qué ha cambiado sobre mi perro?')['versions'] == []


def test_retrieval_context_prefers_same_place_for_equal_relevance():
    contact()
    initialize_memory_provenance()
    with get_connection() as conn:
        old = save_episodic_memory(conn, 'AGENT_K', 'Encuentro tren', source_kind='SELF_REPORTED', source_actor_id='AGENT_K', minute=1)
        conn.execute("UPDATE agents SET location='APARTMENT' WHERE id='AGENT_K'")
        save_episodic_memory(conn, 'AGENT_K', 'Otro tren', source_kind='SELF_REPORTED', source_actor_id='AGENT_K', minute=2)
        for n in range(4):
            save_episodic_memory(conn, 'AGENT_K', 'Descanso', source_kind='SELF_REPORTED', source_actor_id='AGENT_K', minute=n+3)
    result = retrieve_memories('AGENT_K', 'tren', limit=5, location='STATION')
    assert old in [item['id'] for item in result]
    assert result == retrieve_memories('AGENT_K', 'tren', limit=5, location='STATION')


def test_world_observation_records_individual_provenance():
    sim, _, _ = contact()
    sim.remember(sim.k.agent, 'Observed test signal', source_kind='DIRECT_PERCEPTION')
    record = retrieve_memories('AGENT_K')[0]
    assert record['source_kind'] == 'DIRECT_PERCEPTION'
    assert record['source_actor_id'] == 'AGENT_K'
    assert record['received_minute'] == sim.minute
    assert retrieve_memories('AGENT_NORA') == []


def test_failed_turn_does_not_append_episodes():
    _, _, result = tell_pair()
    before = retrieve_memories('AGENT_K')
    with pytest.raises(ValueError, match='STALE_TURN'):
        say_to_player_conversation('AGENT_K', 'Mi perro se llama Intruso.', result['turn_id']-1, 12)
    assert retrieve_memories('AGENT_K') == before
    assert knowledge_timeline('AGENT_K', '¿Cómo se llama mi perro?')['versions'][-1]['reported_value'] == 'Lupo'


def test_provider_receives_episode_provenance_without_other_agents(monkeypatch):
    import io
    import json
    _, _, _ = tell_pair()
    with get_connection() as conn:
        save_episodic_memory(conn, 'AGENT_NORA', 'Nora private secret', source_kind='SELF_REPORTED', source_actor_id='AGENT_NORA', minute=10)
    context = AgentContextBuilder().build('AGENT_K', retrieval_query='Hablemos del perro')
    captured = {}
    def fake_urlopen(request, timeout):
        captured.update(json.loads(request.data))
        return io.BytesIO(json.dumps({'choices': [{'message': {'content': 'Te escucho.'}}]}).encode())
    monkeypatch.setenv('LAIN_LLM_MODEL', 'test-model')
    monkeypatch.setattr(llm_dialogue, 'urlopen', fake_urlopen)
    assert llm_dialogue._provider_reply(context, 'Hablemos del perro') == 'Te escucho.'
    projected = json.loads(captured['messages'][1]['content'])['agent_context']
    assert 'Nora private secret' not in str(projected)
    record = projected['memory_records'][0]
    assert record['owner_id'] == 'AGENT_K'
    assert record['location'] == 'STATION'
    assert record['received_minute'] == 10
    assert record['origin_turn_id'] is not None
    assert record['source_kind'] == 'PLAYER_TESTIMONY'


def test_episodic_metadata_rolls_back_with_canonical_memory():
    contact()
    initialize_memory_provenance()
    with pytest.raises(RuntimeError):
        with get_connection() as conn:
            save_episodic_memory(conn, 'AGENT_K', 'Must roll back', source_kind='SELF_REPORTED', source_actor_id='AGENT_K', minute=2)
            raise RuntimeError('abort transaction')
    with get_connection() as conn:
        for table in ('agent_memory', 'agent_memory_provenance', 'agent_memory_episodes'):
            assert conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] == 0
