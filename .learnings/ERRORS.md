# Errors

## [ERR-20260720-001] powershell-skill-read

**Logged**: 2026-07-20T00:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary
Initial skill-file reads failed because the shell startup exceeded a short timeout and one catalog path did not exist in the workspace.

### Error
```text
Get-Content timed out after 10 seconds.
Get-Item: Cannot find path '.agents\skills\requirements-analysis\SKILL.md' because it does not exist.
```

### Context
- Attempted to read skill instructions from PowerShell in the RAGFlow workspace.
- PowerShell startup took about 12 seconds in this environment.
- The requirements-analysis catalog entry referenced a missing workspace path.

### Suggested Fix
Use a timeout of at least 60 seconds for this PowerShell environment and fall back when a cataloged skill path is unavailable.

### Metadata
- Reproducible: yes
- Related Files: none

### Resolution
- **Resolved**: 2026-07-20T00:00:00+08:00
- **Notes**: Retried with a 60-second timeout and used the documented fallback for the missing skill.

---

## [ERR-20260721-001] parallel-rg-no-match

**Logged**: 2026-07-21T00:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
A parallel source-inspection batch failed because one `rg` expression returned no matches.

### Error
```text
Exit code: 1
```

### Context
- One non-matching `rg` command caused the combined inspection batch to fail.

### Suggested Fix
Run optional searches separately or handle their non-zero no-match exit status.

### Metadata
- Reproducible: yes
- Related Files: none

### Resolution
- **Resolved**: 2026-07-21T00:00:00+08:00
- **Notes**: Continued with direct file reads and successful exact searches.

---

## [ERR-20260720-003] docx-renderer-missing

**Logged**: 2026-07-20T00:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
DOCX text extraction succeeded, but the required visual renderer could not start because its LibreOffice executable was unavailable.

### Error
```text
FileNotFoundError: [WinError 2] 系统找不到指定的文件。
```

### Context
- Attempted to render `C:\Users\11768\Desktop\钉钉材料\qkl.docx` with the bundled `render_docx.py`.
- The bundled Python runtime was available; the renderer's external conversion executable was not.

### Suggested Fix
Use text extraction for read-only content review when the document image is already supplied; install/provide LibreOffice for visual QA when layout review is required.

### Metadata
- Reproducible: yes
- Related Files: C:\Users\11768\Desktop\钉钉材料\qkl.docx

### Resolution
- **Resolved**: 2026-07-20T00:00:00+08:00
- **Notes**: Cross-checked extracted paragraphs against the supplied screenshot.

---

## [ERR-20260720-002] powershell-rg-quoting

**Logged**: 2026-07-20T00:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary
A PowerShell `rg` command containing escaped double quotes was split into separate arguments.

### Error
```text
rg: =: 系统找不到指定的文件。
rg: min api\\db\\services\\dialog_service.py: 系统找不到指定的路径。
```

### Context
- The command was used to inspect the local reference implementation.

### Suggested Fix
Use single-quoted PowerShell search patterns when the pattern contains literal double quotes.

### Metadata
- Reproducible: yes
- Related Files: none

### Resolution
- **Resolved**: 2026-07-20T00:00:00+08:00
- **Notes**: Re-ran the search with single-quoted patterns.

---

## [ERR-20260722-001] powershell-login-file-output-timeout

**Logged**: 2026-07-22T00:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
PowerShell file reads timed out under login-shell initialization and failed while flushing output.

### Error
```text
Exit code: 124
command timed out
Exception ignored on flushing sys.stdout: OSError: [Errno 22] Invalid argument
```

### Context
- Attempted to read the internal token guide and the self-improvement skill with `Get-Content -Raw`.
- The files were readable; the failure came from the login-shell/output path.

### Suggested Fix
For local read-only PowerShell inspection, use `login: false` and prefer targeted `rg` output or `[System.IO.File]::ReadAllText()`.

### Metadata
- Reproducible: yes
- Related Files: docs/guides/internal_model_token_guide.md

### Resolution
- **Resolved**: 2026-07-22T00:00:00+08:00
- **Notes**: Re-ran with `login: false`; both direct file reading and targeted searches succeeded.

---

## [ERR-20260722-002] local-python-missing-project-dependency

**Logged**: 2026-07-22T00:00:00+08:00
**Priority**: low
**Status**: pending
**Area**: tests

### Summary
The system Python could compile the edited files but could not import the RAGFlow LLM module for a focused runtime check.

### Error
```text
ModuleNotFoundError: No module named 'strenum'
```

### Context
- Attempted to instantiate `XinferenceChat` without calling its network client and verify `_clean_conf()` output.
- `python -m py_compile` succeeded for both edited Python files.
- The current shell was not using the repository's fully provisioned environment.

### Suggested Fix
Run the focused runtime check in the project's `uv` environment after dependencies are installed.

### Metadata
- Reproducible: yes
- Related Files: rag/llm/chat_model.py

---

## [ERR-20260722-003] broad-agno-search-timeout

**Logged**: 2026-07-22T00:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: backend

### Summary
A parallel whole-repository search for Agno symbols exceeded the shell timeout.

### Error
```text
Exit code: 124
command timed out
```

### Context
- Searched the large local reference repository for `get_agno_model` and `OpenAILike`.
- The internal screenshot already located the relevant function in `tools.py`.

### Suggested Fix
Use the known internal file and IDE call hierarchy, or restrict filesystem searches to likely source roots.

### Metadata
- Reproducible: unknown
- Related Files: none

### Resolution
- **Resolved**: 2026-07-22T00:00:00+08:00
- **Notes**: Continued from the supplied internal source screenshot and requested targeted call-site evidence.

---
