# Learnings

## [LRN-20260721-001] correction

**Logged**: 2026-07-21T00:00:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: backend

### Summary
RAGFlow model configuration `max_tokens` is a total context-window value, not solely an input token limit.

### Details
Official RAGFlow defines `TenantLLM.max_tokens` with help text `Max context token num`. Dialog processing fits input messages within this budget and caps requested generation tokens to the remaining budget. Earlier analysis described the field only as an input budget, which was incomplete.

### Suggested Action
When explaining RAGFlow-derived model settings, distinguish total context window, current input tokens, and requested output tokens.

### Metadata
- Source: conversation
- Related Files: api/db/db_models.py, api/db/services/dialog_service.py
- Tags: ragflow, tokens, context-window

### Resolution
- **Resolved**: 2026-07-21T00:00:00+08:00
- **Notes**: Verified against the locally cloned official RAGFlow repository.

---

## [LRN-20260722-001] correction

**Logged**: 2026-07-22T00:00:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: backend

### Summary
Diagnose internal or production failures from the supplied runtime logs; treat a local repository as reference only unless version equivalence is confirmed.

### Details
The user clarified that the internal deployment code may differ from the local RAGFlow checkout. Conclusions about the failure must therefore come from the screenshot's exception chain, endpoint, timestamps, and error types rather than inferred local implementation details.

### Suggested Action
Clearly separate log-proven facts from hypotheses and local-source references when deployed code provenance is uncertain.

### Metadata
- Source: user_feedback
- Related Files: none
- Tags: diagnostics, production, logs, scope

### Resolution
- **Resolved**: 2026-07-22T00:00:00+08:00
- **Notes**: Analysis scope corrected in the same conversation.

---
