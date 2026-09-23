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


## Diagnostico de generaciones ausentes (Reality 0.2.1)

This prototype did not initially allow the dialogue model to imagine new entities:
its factuality prompt discouraged fictional propositions, while the Reality
parser inspected only messages containing a fixed list of words and silently
ignored provider errors. The experimental branch now allows speculative
digital-presence narration without turning a fictional line into verified past
experience. When explicitly enabled, the second model inspects every original
NPC LLM dialogue turn; no lexical keyword is required. Calls are therefore
slower/costlier and **still do not guarantee a creation**. World Core still
validates the proposal, enforces a global limit of eight, records provenance,
and never treats a player's testimony as permission to create.

Close the old Python server, check out the updated Reality 0.2 branch, and
start the server **from the same PowerShell process** in which the variables
were set. `play.ps1` only starts the Godot client; it does not configure
or launch the Python/LLM server.

```powershell
git fetch origin
git switch experiment/reality-0.2-autonomy-visual04
git pull --ff-only
$env:LAIN_LLM_ENABLED = "1"
$env:LAIN_REALITY_GENERATION = "1"
$env:LAIN_REALITY_TRACE = "1"
$env:LAIN_REALITY_TIMEOUT = "25"
# Keep your existing local provider settings, especially LAIN_LLM_MODEL.
if (-not $env:LAIN_LLM_MODEL) { throw "Configure LAIN_LLM_MODEL for your local provider" }
python -m uvicorn server.api:app --reload
```

When talking to K/Nora in **free text**, the Godot debug console prints
`DIALOGUE // SOURCE = LLM_DIALOGUE` only when the conversational model
actually responded. A `CURRENT_TESTIMONY`, `GROUNDED_RECALL`,
`RULE_GROUNDED` or `DETERMINISTIC_FALLBACK` response does **not** trigger
the generative proposal parser.

With trace enabled, the Python-server console prints **reason codes only**:
`GENERATION_DISABLED`, `DIALOGUE_MODEL_DISABLED`, `DIALOGUE_SOURCE_...`,
`LLM_MODEL_NOT_CONFIGURED`, `PARSER_REQUESTED`,
`NO_NEW_ENTITY_IN_REPLY`, `PROPOSAL_ACCEPTED`,
`REJECTED_ENTITY_CAP_REACHED`, `REJECTED_ENTITY_NAME_ALREADY_EXISTS`,
`PARSER_ERROR_...`, or `ENTITY_CREATED_ENTITY_...`.
Neither the NPC/player dialogue text nor secrets are included in these logs.
If no trace appears after sending a free-text message, verify that the server
process was **restarted** with these variables and that Godot is connected to
that process. If `PARSER_ERROR_...` appears, verify your provider endpoint,
model configuration and timeout; many local models return non-JSON responses
or need more than six seconds for the second inference.

To distinguish an entity created out of view from no entity at all, from
repo root in another PowerShell process, inspect the SQLite world **read-only**:

```powershell
@'
import sqlite3
from pathlib import Path
db = Path("world.db")
print("DB:", db.resolve(), "exists:", db.is_file())
if db.is_file():
    with sqlite3.connect(f"file:{db.resolve().as_posix()}?mode=ro", uri=True) as conn:
        table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='generated_entities'"
        ).fetchone()
        if table:
            print("GENERATED ENTITIES:", conn.execute(
                "SELECT g.id, a.name, a.location FROM generated_entities g "
                "JOIN agents a ON a.id=g.id ORDER BY g.created_minute"
            ).fetchall())
        else:
            print("NO GENERATED ENTITY TABLE IN THIS DATABASE")
'@ | python -
```

A `GENERATED ENTITIES: []` result means nothing has been created in that
database. A nonempty list with location `OLD_DISTRICT` or `APARTMENT`
means the entity exists but **these locations do not yet have the Reality
0.2 physical-character spawner**. To see its identity without moving an
NPC, connect to the Wired from the apartment terminal and look under
`DIGITAL PRESENCES`. Only `APARTMENT_DISTRICT` and `STATION` presently
render physical manifestations from `visible_actors`; do not edit your
persistent database to force an entity into view.
