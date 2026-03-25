# Ghostwriter V2 — Code Review

> Reviewed: 2026-03-26 | Scope: All files in `v2/`

---

## Critical (must fix before shipping)

### C1: `chunk_text` can infinite-loop

**File:** `v2/app/services/documents.py:28`

The word-boundary seeking loops in `chunk_text` have no guard. On text with no spaces (URLs, base64, CJK text), the `while` loops scan forward/backward indefinitely. The overlap logic can also produce duplicate or empty chunks when boundaries aren't found.

**Fix:** Add a max-scan guard to both boundary loops. Fall back to hard character-boundary splits when no space is found within a reasonable range.

---

### C2: `fetch_tweets` doesn't wait for Apify run completion

**File:** `v2/app/services/twitter.py:9-27`

The function POSTs to start an Apify actor run, then immediately GETs the dataset items. Apify runs are asynchronous — the dataset will be empty or incomplete.

**Fix:** Either use the synchronous run endpoint (`/run-sync-get-dataset-items`), or poll the run status until it reaches `SUCCEEDED` before fetching results.

---

### C3: Zero test files exist

**Directory:** `v2/tests/`

All 8 test files from the implementation plan are missing: `test_auth.py`, `test_brands.py`, `test_workflows.py`, `test_templates.py`, `test_source_content.py`, `test_engine.py`, `test_templatize.py`, `test_providers.py`. Effective test coverage is 0%.

**Fix:** Write all test files per the implementation plan (Tasks 3-11 each specify tests).

---

### C4: Deprecated pytest-asyncio fixture pattern

**File:** `v2/tests/conftest.py`

The session-scoped `event_loop` fixture is deprecated in pytest-asyncio 0.21+ and will break in the next major version. There is also no `asyncio_mode = "auto"` configuration anywhere.

**Fix:** Add a `v2/pyproject.toml` with `[tool.pytest.ini_options] asyncio_mode = "auto"` and remove the manual `event_loop` fixture.

---

## Important (should fix)

### I1: `update_workflow` steps serialization is fragile

**File:** `v2/app/routers/workflows.py:69-71`

The conditional `if "steps" in update_data and update_data["steps"] is not None` skips re-serialization when steps is an empty list `[]` (falsy but valid). The double-dump pattern is also confusing.

**Fix:** Simplify:
```python
update_data = body.model_dump(exclude_unset=True)
if "steps" in update_data:
    update_data["steps"] = [s.model_dump() for s in body.steps] if body.steps else []
```

---

### I2: Missing `ondelete` on GeneratedContent FKs

**File:** `v2/app/models/generated_content.py:16-17`

`workflow_id` and `brand_id` FKs have no `ondelete` behavior. Deleting a workflow or brand voice will cause FK constraint violations. Every other FK in the codebase uses `ondelete="CASCADE"`.

**Fix:**
- `brand_id`: Add `ondelete="SET NULL"` (already nullable)
- `workflow_id`: Add `ondelete="SET NULL"` and make nullable, or use `ondelete="RESTRICT"` to prevent deletion of workflows with generated history

---

### I3: No indexes on `account_id` columns

**Files:** All model files

Every query filters by `account_id` but no model has `index=True` on that column. SQLAlchemy does NOT auto-create FK indexes.

**Fix:** Add `index=True` to every `account_id` `mapped_column()`. Consider also indexing `source`, `channel_source`, and `category` if frequently filtered.

---

### I4: SHA-256 API key hashing — document or strengthen

**File:** `v2/app/auth/service.py:6`

SHA-256 is a fast hash. If the key_hash column is ever leaked, all keys could be brute-forced quickly (though the 256-bit entropy of the keys makes pre-image attacks infeasible). The SQL comparison is also not constant-time.

**Fix:** Either document the rationale (high-entropy keys make fast hashing acceptable) or switch to HMAC-based lookup (fetch by key prefix, compare full hash with `hmac.compare_digest` in Python).

---

### I5: `POST /accounts` is unauthenticated with no rate limiting

**File:** `v2/app/routers/accounts.py:12`

Anyone can create unlimited accounts. This is an abuse vector for resource exhaustion.

**Fix:** Add rate limiting (e.g., `slowapi` middleware) on account creation. Consider requiring an admin token or invite code.

---

### I6: OpenAI provider — `None` content crash

**File:** `v2/app/providers/openai.py:30`

`response.choices[0].message.content` can be `None` when the model produces a refusal. `GenerationResult.text` is typed as `str`, so this crashes.

**Fix:** Default to empty string or raise a descriptive error:
```python
text = response.choices[0].message.content or ""
```

---

### I7: Google provider — `response.text` raises on safety filter

**File:** `v2/app/providers/google.py:31`

The `response.text` property raises `ValueError` if the response was blocked by safety filters or if no candidates were returned.

**Fix:** Catch `ValueError` and raise a descriptive error about content being filtered.

---

### I8: No error handling in providers or engine

**Files:** All provider files, `v2/app/engine/executor.py`

LLM API failures (rate limits, auth errors, network timeouts) produce raw 500s. If step 3 of 5 fails, the caller gets no indication of which step failed.

**Fix:** Catch provider-specific exceptions per-step in the executor. Return structured errors with step number, step name, and error message.

---

### I9: API clients instantiated per-call, never closed

**Files:** `v2/app/providers/anthropic.py`, `openai.py`, `google.py`, `v2/app/services/embeddings.py`

Every `generate()` call creates a new SDK client with an HTTP connection pool that is never closed. Produces `ResourceWarning` and leaks connections.

**Fix:** Use `async with` context managers where SDKs support it (both `AsyncAnthropic` and `AsyncOpenAI` do). For per-request API keys this is the cleanest approach.

---

### I10: File upload has no size limit

**File:** `v2/app/routers/source_content.py:76`

`await file.read()` loads the entire upload into memory with no guard. An attacker can upload a multi-gigabyte file and OOM the server.

**Fix:** Add an explicit size check after read:
```python
file_bytes = await file.read()
if len(file_bytes) > 10 * 1024 * 1024:  # 10MB
    raise HTTPException(413, "File too large")
```

---

### I11: Sequential embedding calls in batch/upload/Twitter endpoints

**File:** `v2/app/routers/source_content.py`

Batch import, file upload, and Twitter import all generate embeddings one-at-a-time in a loop. Each is a separate HTTP round-trip to OpenAI.

**Fix:** Add a `generate_embeddings_batch(texts: list[str])` function in `services/embeddings.py` that calls OpenAI's batch embedding endpoint in a single request. Use it in all loops.

---

### I12: Missing input validation on schemas

**Files:** Multiple schema files

No bounds or constraints on:
- `WorkflowStep.temperature` (should be `Field(ge=0.0, le=2.0)`)
- `WorkflowStep.max_tokens` (should be `Field(ge=1, le=16384)`)
- `GenerateRequest.template_count` (should be `Field(ge=1, le=10)`)
- `SourceContentBatchRequest.items` (should be `Field(max_length=100)`)
- `TwitterImportRequest.max_tweets` (should be `Field(le=500)`)
- `TemplateSearchRequest.limit` / `SourceContentSearchRequest.limit` (should be `Field(ge=1, le=50)`)
- `AccountCreate.name` (should be `Field(min_length=1, max_length=255)`)

**Fix:** Add `pydantic.Field` constraints to all fields listed above.

---

### I13: Markdown extraction only strips `<p>` tags

**File:** `v2/app/services/documents.py:48-50`

`_extract_markdown` converts markdown to HTML then only strips `<p>` and `</p>`. All other HTML tags (`<h1>`, `<strong>`, `<code>`, `<ul>`, `<li>`, `<a>`, etc.) remain in the text sent to LLMs.

**Fix:** Use a proper HTML-to-text approach. Either use `BeautifulSoup(html, "html.parser").get_text()` or a regex to strip all tags.

---

### I14: Docker Compose — API starts before Postgres is ready

**File:** `v2/docker-compose.yml`

`depends_on: db` only waits for the container to start, not for PostgreSQL to accept connections. The API will crash on startup.

**Fix:** Add a health check to the `db` service and use `condition: service_healthy`:
```yaml
db:
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U ghostwriter"]
    interval: 5s
    timeout: 5s
    retries: 5

api:
  depends_on:
    db:
      condition: service_healthy
```

---

### I15: No `.dockerignore` — secrets baked into image

**File:** Missing `v2/.dockerignore`

`COPY . .` in the Dockerfile copies `.env` (with API keys), `__pycache__`, `.git`, `tests/`, and docs into the image.

**Fix:** Create `v2/.dockerignore`:
```
.env
.git
__pycache__
tests/
docs/
*.pyc
*.md
```

---

### I16: Test database not created by Docker Compose

**File:** `v2/tests/conftest.py`, `v2/docker-compose.yml`

`conftest.py` derives `ghostwriter_test` from the database URL, but docker-compose only creates `ghostwriter`. Tests will fail to connect.

**Fix:** Add an init script to docker-compose that creates the test database:
```yaml
db:
  volumes:
    - ./init-test-db.sql:/docker-entrypoint-initdb.d/init-test-db.sql
```
With `init-test-db.sql`:
```sql
CREATE DATABASE ghostwriter_test;
```

---

### I17: Unused and misplaced dependencies in `requirements.txt`

**File:** `v2/requirements.txt`

- `passlib[bcrypt]` and `python-jose[cryptography]` are listed but unused in v2 (SHA-256 hashing, no JWT)
- `pytest` and `pytest-asyncio` are test deps bundled in the production image
- `httpx` is listed twice

**Fix:** Remove unused deps. Split into `requirements.txt` (prod) and `requirements-dev.txt` (adds pytest, pytest-asyncio).

---

## Suggestions (nice to have)

| # | Area | Issue |
|---|------|-------|
| S1 | Models | `database.py` return type should be `AsyncGenerator[AsyncSession, None]` not `AsyncSession` |
| S2 | Models | Vector columns (`embedding`) lack `Mapped` type annotation for consistency |
| S3 | Engine | `{variable}` substitution syntax conflicts with literal braces in prompts (JSON examples). V1 used `$variable`. Consider switching. |
| S4 | Providers | `BaseProvider` should be `abc.ABC` with `@abstractmethod` for static analysis |
| S5 | Providers | Registry prefix matching — `"o1"`, `"o3"`, `"o4"` without hyphens could match unintended models |
| S6 | Routers | No pagination on any list endpoint — will return unbounded result sets over time |
| S7 | Routers | `templatize.py` defines schemas inline instead of in `app/schemas/` (inconsistent with all other routers) |
| S8 | Routers | Hardcoded default model `claude-haiku-4-5-20251001` in templatize should be a config constant |
| S9 | Routers | No `PUT /templates/{id}` endpoint — users must delete and recreate to edit |
| S10 | Services | `_extract_pdf` doesn't close the `fitz.Document` — use `with` statement |
| S11 | Infra | No Alembic migration version files generated yet — `alembic revision --autogenerate` needed |
| S12 | Infra | Dockerfile should run as non-root user and include `EXPOSE 8000` |
| S13 | Schemas | `StepUsage` schema in `generation.py` is defined but never used — `token_usage` is raw `dict` instead |
| S14 | Schemas | `ProviderKeys` transmits API keys in request body — will appear in logs/APM. Consider server-side storage. |

---

## What's done well

- **Account-scoping is correct everywhere** — every query filters by `account_id`, IDOR protection is solid
- **Design doc alignment** — data model, endpoints, and API contracts match the spec faithfully
- **Clean separation of concerns** — models, schemas, routers, services, providers, engine are well-organized
- **Proper FK cascades** on account-scoped models (except the two noted in I2)
- **Timezone-aware timestamps** with UTC defaults using lambdas
- **Auth flow** is clean and functional — Bearer token extraction, account lookup, proper 401/404
- **Template and source content** support both system-level (null account_id) and user-scoped resources

---

## Recommended priority order

1. Fix `chunk_text` infinite loop (C1) and Twitter polling (C2) — runtime crashes
2. Add `.dockerignore` (I15) and fix docker-compose health check (I14) — blocks deployment
3. Add input validation on schemas (I12) — low effort, high impact
4. Add error handling in providers and engine (I6, I7, I8) — currently silent 500s
5. Fix FK `ondelete` (I2) and add `account_id` indexes (I3) — needs Alembic migration
6. Write the test suite (C3) — fixtures exist but zero tests do
7. File upload size limit (I10) and batch embeddings (I11) — operational safety
