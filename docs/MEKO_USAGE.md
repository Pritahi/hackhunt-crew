> WORK IN PROGRESS: this document predates the corrected benchmark.
> Fixture pages are illustrative, not official. Old savings/quality claims are not validated.

# How HackHunt Crew uses Meko

Mapped to the ContextCon judging rubric ("Use of Meko", 30%: all parts of the
context - conversations, memory, learning, knowledge, artifacts, decision
tracing - plus sharing context to improve it).

| Meko capability | Where the crew uses it |
|---|---|
| Conversations | One stored conversation per candidate evaluation (`conversation_create`), one message per agent turn with `reasoning` and `plan` (`conversation_add_message`). |
| Memory | Durable facts (Scout's extracted facts), verdicts (Verifier), kill reasons (RedTeam) promoted with `memory_add`; recalled with `memory_search` and `context_search` by later agents and later runs. |
| Knowledge base | `entry-criteria.md` uploaded once via `knowledgebase_upload_document`; retrievable by any agent via `knowledgebase_search`. |
| Artifacts | Per-candidate final report JSON stored via `artifact_store`. |
| Decision traces + token cost | Every LLM call's metered usage attached to its trace with `track_token_usage`; full cost story visible in the portal. |
| Learning | Run 2+ warm-starts from memory: memorized verdicts reused instead of re-derived; retrievals get tighter as the datapack learns. |
| Sharing / collaboration | All four agents (scout, verifier, redteam, builder as separate `agent_id`s) read and write one datapack - one agent's learning is every agent's advantage. |

## Why the datapack model fits

Each agent namespace keeps its own conversation history, while memory and
knowledge are shared and governed. Verifier's "student-only badge pattern"
memory is written once and recalled by RedTeam on every later candidate -
without either agent ever seeing the other's full transcript.
