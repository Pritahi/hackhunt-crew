# Meko integration

- conversation_create / conversation_add_message: owner-scoped role traces.
- memory_add / memory_search: shared candidate facts. conversation_id is tracing;
  run_id filters by the stored memory conversation tag.
- knowledgebase_upload_document: two-step criteria upload. Criteria also appear
  explicitly in both modes for parity; KB retrieval is not used in the benchmark.
- artifact_put: complete JSON reports stored by content hash.
- track_token_usage: role-level successful provider-reported LLM usage.

Meko backend inference and embedding tokens are outside this ledger. Client
prompt savings do not imply equal end-to-end cost savings. No automatic
self-learning benefit is claimed. Cold start uses a fresh datapack.
