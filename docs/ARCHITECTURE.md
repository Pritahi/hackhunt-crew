# Architecture

Scout extracts supplied source facts. Verifier checks seven entry criteria.
RedTeam flags hard violations. Builder proposes a plan for survivors.
Both modes use identical role prompts, fixtures and a fixed model.

Baseline includes all earlier concise fact/verdict learnings. Meko retrieves
up to five memories in a candidate-specific conversation scope shared by all
roles. Source facts override stale memory. Every pass re-evaluates each verdict.

Checkpoints retain reports, usage, baseline learnings and Meko conversation IDs.
Restarting a chunk preserves history. A fresh experiment needs new checkpoints
and a fresh datapack. Three passes are sequential, not independent trials.
The fixture set is illustrative, not a source for real-event recommendations.
