# Reality 0.2 — autonomia perceptiva + manifestacion Visual 0.4

Branch: `experiment/reality-0.2-autonomy-visual04`, cut directly
from graphical baseline `experiment/visual-0.4-lain-environments`
at commit `3afd782`. The existing character models, apartment, street,
station and Reality 0.1 creation/memory all remain intact.

## Delivered

- A generated agent's **own** recent DIRECT_PERCEPTION of a signal with
  perceived strength >= 0.70 and confidence >= 0.80 can temporarily override
  its seed objective with `INVESTIGATE_ANOMALY`. The engine validates the
  actual investigation; the agent records the experience in its existing
  episodic-memory system. A completed investigation cannot be farmed again
  from the same node. The direct belief may survive a restart and is useful
  for up to forty simulated minutes. Third-party beliefs, rumors, outdated
  perceptions and the global world-node table cannot trigger this goal.
  This is **bounded goal adaptation**, not free-form AI planning or generic
  natural-language-to-goal conversion.
- Generated actors have stable IDs (from World Core), are rendered in the
  street and station when `visible_actors` includes them, and disappear
  when the server removes them. They use a simple translucent cyan
  manifestation, NOT a replacement of the existing K/Nora Visual 0.4 assets.
  The generic `ActorInteractable` enables normal player dialogue for these
  actors whenever they are co-located and World Core accepts CONTACT.
- An exploring/following generated entity that currently **directly sees**
  the player waits rather than moving out of range before a contact action.
  K/Nora behaviour and actor spawns remain unchanged.
- The offline Visual 0.4 capture test now checks the dynamic spawn,
  interaction identity and despawn in both street and station scenes.
  Additional Python tests cover perception-based goal changes, stale/foreign
  information, independent investigation, memory persistence and dialogue.

## Play the new branch

Back up `world.db` outside the repository and close Godot and Uvicorn before
changing branches. From the repo root on Windows:

```powershell
git fetch origin
git switch --track origin/experiment/reality-0.2-autonomy-visual04
.\play.ps1
```

If it already exists locally:
`git switch experiment/reality-0.2-autonomy-visual04`.
Start the Python server separately using your current local-model setup.
Reality creation is still opt-in; when enabled, keep:
`$env:LAIN_LLM_ENABLED="1"` and
`$env:LAIN_REALITY_GENERATION="1"` before starting Uvicorn.

A new entity may appear in the same location as its NPC creator. If it is
present in `visible_actors`, the Godot street/station spawner renders it;
approach and press E to talk. Walking/talking can advance World Core ticks.
The entity can notice a sufficiently strong nearby anomalous node, choose
to investigate and retain its discovery after restarting. It is not
guaranteed that every session naturally produces an entity or anomaly:
creation depends on the optional model proposal and the current world state.

## Tests

```powershell
$env:LAIN_LLM_ENABLED="0"
$env:LAIN_REALITY_GENERATION="0"
python -m pytest -q
godot --headless --path client --editor --import --quit
godot --headless --path client --fixed-fps 60 --script res://tools/capture_visual04.gd -- district
godot --headless --path client --fixed-fps 60 --script res://tools/capture_visual04.gd -- station
```

Python regressions run automatically in GitHub Actions on this branch and PR.
Godot capture tests are runnable offline and do not modify the user's save.
A real Ollama dialogue run and interactive Godot navigation need a local
manual end-to-end check.

## Still outside this milestone

Player knowledge/influence levels, multiple worlds, cross-world Wired,
arbitrary LLM-driven world edits, new world geography, rich entity avatars,
generic long-horizon planning, NPC-to-NPC conversations and multiplayer
permissions/conflict resolution remain to be designed and tested separately.
