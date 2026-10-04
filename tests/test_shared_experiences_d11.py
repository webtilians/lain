"""D11 integration tests with SQLite and World Core, no live model."""
import pytest
from server.world_core.database import get_connection, save_agent
from server.world_core.models import ActionIntent
from server.world_core.simulation import Simulation
from server.world_core.shared_experiences import (
    experience_context, experience_reply, record_shared_attention,
    record_experience,
)
from server.world_core.interactions import create_or_get_interaction
from server.world_core.player_conversation import start_player_conversation
from server.world_core.free_conversation import say_to_player_conversation
from server.world_core.agent_context import AgentContextBuilder


def world():
    sim = Simulation()
    for agent in (sim.player, sim.k.agent, sim.nora.agent):
        agent.location = 'STATION'
        agent.energy = 1.0
        save_agent(agent)
    return sim


def resolve(sim, *pairs):
    return sim.resolve_intents([(None, ActionIntent(actor, action, 'NODE_07')) for actor, action in pairs])


def records(owner='AGENT_K'):
    return experience_context(owner, None)['records']


def chat(sim):
    interaction, _ = create_or_get_interaction('PLAYER_1', 'AGENT_K', 'PLAYER_INITIATED_CONVERSATION', 'UNKNOWN', sim.minute)
    return interaction, start_player_conversation('AGENT_K', sim.minute)


@pytest.mark.parametrize('role,verb', [('OBSERVE','observé'),('INVESTIGATE','investigué')])
def test_shared_attention_requires_actual_actions_and_preserves_roles(role, verb):
    sim = world()
    resolve(sim, ('PLAYER_1','INVESTIGATE'), ('AGENT_K',role))
    shared = [r for r in records() if r['kind'] == 'SHARED_ATTENTION']
    assert len(shared) == 1
    assert shared[0]['participants'] == ['AGENT_K','PLAYER_1']
    assert shared[0]['source_event_id']
    assert records('AGENT_NORA') == []
    _, turn = chat(sim)
    answer = say_to_player_conversation('AGENT_K', '¿Estabas conmigo cuando investigamos esa señal?', turn['turn_id'], sim.minute)
    assert answer['response_source'] == 'GROUNDED_RECALL'
    assert verb in answer['line']


def test_proximity_and_different_batches_are_not_shared_experience():
    sim = world()
    resolve(sim, ('PLAYER_1','INVESTIGATE'))
    assert records() == []
    resolve(sim, ('AGENT_K','OBSERVE'))
    assert not any(r['kind'] == 'SHARED_ATTENTION' for r in records())


def test_denied_action_cannot_create_shared_episode():
    sim = world()
    sim.player.energy = 0
    save_agent(sim.player)
    resolve(sim, ('PLAYER_1','INVESTIGATE'), ('AGENT_K','OBSERVE'))
    assert records('PLAYER_1') == []
    assert not any(r['kind'] == 'SHARED_ATTENTION' for r in records())


def test_encounter_retry_previous_visit_and_reopen():
    sim = world()
    interaction, first = chat(sim)
    start_player_conversation('AGENT_K', 0)
    assert len(records()) == 1
    assert records('AGENT_NORA') == []
    context = AgentContextBuilder().build('AGENT_K', interaction.id,
        '¿Qué pasó la última vez que estuvimos en la estación?')
    assert 'No tengo registrado' in experience_reply(context)
    with get_connection() as conn:
        conn.execute("UPDATE interactions SET status='RESUMING' WHERE id=?", (interaction.id,))
    start_player_conversation('AGENT_K', 10)
    context = AgentContextBuilder().build('AGENT_K', interaction.id,
        '¿Qué pasó la última vez que estuvimos en la estación?')
    assert 'minuto 0' in experience_reply(context)
    assert len(records()) == 2
    assert records()[0]['origin_turn_id'] != first['turn_id']
    assert records() == experience_context('AGENT_K', None)['records']


def test_testimony_does_not_become_participation_or_observation():
    sim = world()
    _, turn = chat(sim)
    turn = say_to_player_conversation('AGENT_K', 'Investigamos juntos NODE_07.', turn['turn_id'], 0)
    turn = say_to_player_conversation('AGENT_K', '¿Estabas conmigo cuando investigamos NODE_07?', turn['turn_id'], 0)
    assert 'No tengo registrada' in turn['line']
    answer = say_to_player_conversation('AGENT_K', '¿NODE_07 lo viste tú o te lo conté yo?', turn['turn_id'], 0)
    assert 'Me hablaste' in answer['line']
    assert {r['kind'] for r in records()} == {'ENCOUNTER'}


def test_direct_observation_source_and_ambiguous_reference():
    sim = world()
    resolve(sim, ('AGENT_K','OBSERVE'))
    _, turn = chat(sim)
    answer = say_to_player_conversation('AGENT_K', '¿Eso lo viste tú o te lo conté yo?', turn['turn_id'], 0)
    assert 'observé NODE_07 personalmente' in answer['line']
    context = AgentContextBuilder().build('AGENT_NORA', retrieval_query='¿Eso lo viste tú o te lo conté yo?')
    assert '¿A qué señal' in experience_reply(context)


def test_moving_during_batch_disallows_witness_pairing():
    sim = world()
    sim.resolve_intents([
        (None,ActionIntent('PLAYER_1','INVESTIGATE','NODE_07')),
        (None,ActionIntent('AGENT_K','OBSERVE','NODE_07')),
        (None,ActionIntent('AGENT_K','MOVE','APARTMENT')),
    ])
    assert not any(r['kind'] == 'SHARED_ATTENTION' for r in records())


def test_shared_projection_is_idempotent_and_survives_movement():
    sim = world()
    resolve(sim, ('PLAYER_1','INVESTIGATE'), ('AGENT_K','OBSERVE'))
    before = records()
    with get_connection() as conn:
        rows = conn.execute("SELECT id,actor_id,action,target,minute FROM events WHERE action IN ('INVESTIGATE','OBSERVE')").fetchall()
    snapshots = [dict(id=r[0],actor=r[1],action=r[2],target=r[3],minute=r[4],location='STATION') for r in rows]
    record_shared_attention(snapshots)
    sim.k.agent.location = 'APARTMENT'
    save_agent(sim.k.agent)
    assert records() == before
    assert all(r['location']=='STATION' for r in records())


def test_episode_rolls_back_with_caller():
    world()
    with pytest.raises(RuntimeError):
        with get_connection() as conn:
            record_experience(conn, owner='AGENT_K', key='rollback', kind='ENCOUNTER', role='PARTICIPANT', minute=0, location='STATION', participants=('AGENT_K','PLAYER_1'))
            raise RuntimeError('rollback')
    assert records() == []


@pytest.mark.parametrize('question', [
    'que paso la ultima vez que nos vimos',
    'que paso la ultima vez que nos encontramos en la estacion',
    'que paso la ultima vez q nos encontramos en la estacion',
    'que paso la ultima vez q estuvimos en la estacion?',
    'que paso la ultima vez q estuvimos en la estacion',
    'que paso la ultima vez q nos vimos',
])
def test_repeated_real_player_phrasing_recalls_previous_visit(monkeypatch, question):
    from server.world_core import llm_dialogue
    sim = world()
    interaction, _ = chat(sim)
    with get_connection() as conn:
        conn.execute("UPDATE interactions SET status='RESUMING' WHERE id=?", (interaction.id,))
    turn = start_player_conversation('AGENT_K', 10)
    monkeypatch.setenv('LAIN_LLM_ENABLED', '1')
    def forbidden(*args, **kwargs):
        pytest.fail('Supported recall must not call the model')
    monkeypatch.setattr(llm_dialogue, '_provider_reply', forbidden)
    for _ in range(3):
        turn = say_to_player_conversation('AGENT_K', question, turn['turn_id'], 10)
        assert turn['response_source'] == 'GROUNDED_RECALL'
        assert 'minuto 0' in turn['line']
        assert 'la estación' in turn['line']
        assert 'Nos volvemos' not in turn['line']
        assert 'No deduzco' not in turn['line']
    assert len(records()) == 2


def test_model_cannot_replay_resumption_greeting_as_answer(monkeypatch):
    from server.world_core import llm_dialogue
    sim = world()
    _, turn = chat(sim)
    monkeypatch.setenv('LAIN_LLM_ENABLED', '1')
    monkeypatch.setattr(llm_dialogue, '_provider_reply', lambda *a, **kw: 'Nos volvemos a encontrar. ¿Qué quieres contarme?')
    answer = say_to_player_conversation('AGENT_K', 'Puedes explicarlo de otra manera', turn['turn_id'], 0)
    assert answer['response_source'] == 'DETERMINISTIC_FALLBACK'
    assert 'Nos volvemos' not in answer['line']
    assert 'No he conseguido responder' in answer['line']
