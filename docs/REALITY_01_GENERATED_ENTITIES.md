# Reality 0.1 — NPC-created persistent digital presences

Experimental branch: `experiment/reality-0.1-generated-entities`, based on
`experiment/visual-0.3-apartment`. This does **not** merge into the default branch
and does **not** implement the multiplayer Wired or player god powers.

## What this milestone actually does

When an existing agent generates an original free-text **LLM_DIALOGUE** line
describing a new digital presence, an optional second local-model call may
propose a compact specification: a name, a short origin premise and one of
`OBSERVE_WORLD`, `SEEK_CREATOR`, `EXPLORE`. The original NPC response is still
displayed normally. A player's claim about an entity is never a direct world
mutation. A model suggestion is never arbitrary SQL or an action command.

World Core creates the entity in one SQLite transaction with the NPC's dialogue
turn, a unique provenance link, an independent agent row, origin memory for the
new actor, creator memory and an `ENTITY_CREATED` event. Failed/duplicate
requests do not duplicate an entity. A cap of eight generated entities protects
this experimental single-player world from unlimited spontaneous growth.

At the next simulation tick (or after restarting the server), the new actor is
rehydrated into `Simulation.ai_actors` and `Simulation.all_agents`. It perceives
its local world and acquires memories through the existing perception phase.
Its seeded goal drives a minimal deterministic action policy: local observation,
following its creator, or exploring adjacent locations; it rests when tired.
This is **limited autonomy**, not an unrestricted LLM-directed planning agent.

The normal player snapshot includes digital entities in `visible_actors` when
co-located. After the player's initial Wired connection, the apartment terminal
also shows **DIGITAL PRESENCES** by name. This list intentionally excludes the
entity's creator, remote location, personal memories and private objectives.
The experimental terminal list is the first in-game manifestation; Godot does
not yet spawn bespoke 3D NPC meshes or provide a dynamic dialogue interaction
control for these entities.

## Opt in and run

1. Back up your local `world.db` **outside the public repository** and stop
   Uvicorn and Godot before switching branches.
2. Switch to `experiment/reality-0.1-generated-entities` and run the standard
   Python server / Godot Visual 0.3 client.
3. Keep your existing local OpenAI-compatible provider configuration (e.g.
   Ollama). In PowerShell, before running Uvicorn:

```powershell
$env:LAIN_LLM_ENABLED="1"
$env:LAIN_REALITY_GENERATION="1"
$env:LAIN_LLM_MODEL="YOUR_LOCAL_MODEL"
python -m uvicorn server.api:app --reload
```

Generation is **disabled** unless both environment variables are `1`.
When the NPC's own reply describes a potential new presence, the auxiliary
model may still respond with `{"proposal": null}`. No new entity is promised
on any particular dialogue turn. The extra model call may increase latency.
The existing remote-provider opt-in remains in effect if configured.

Talk to K or Nora using free text, and explore the naturally generated dialogue.
After a created presence is saved, connect to the Wired in the apartment terminal
to see its broadcast name. Advance the world with a player action, then inspect
`visible_actors` and `ENTITY_CREATED` events in your local world. Restart the
server and verify that the same entity remains present with its memories.
Do not interpret the terminal presence listing as a fully playable 3D character.

## Deterministic checks

```powershell
$env:LAIN_LLM_ENABLED="0"
$env:LAIN_REALITY_GENERATION="0"
python -m pytest -q
```

`tests/test_generated_entities_reality_01.py` mocks NPC/model replies. It checks
provenance, rollback, identity validation, idempotent retries, origin memory,
independent actions, persistent restart and Wired information boundaries.
CI runs the Python test suite on this experimental branch and on pull requests.
A real-model spontaneous-generation check and a Godot render/terminal check
remain manual; neither is proven by the mocked Python tests.

## Boundaries for the next phase

Still missing: independently generated NPC planning with goals based on its
acquired beliefs, richer free-text creation without the first-pass keyword
trigger, 3D representation and UI conversation for new actors, player
knowledge/influence levels, multiple isolated worlds, shared Wired server and
authorization/conflict rules for cross-world interventions.
