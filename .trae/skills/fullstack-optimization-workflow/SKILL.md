---
name: "fullstack-optimization-workflow"
description: "Full-stack web app optimization workflow: symptom-to-root-cause tracing, field alignment, config hot-reload, dynamic threshold propagation, historical data recompute, and error handling. Invoke when user reports UI/data/config issues across frontend-backend stack, or needs systematic debugging of a full-stack project."
---

# Full-Stack Optimization Workflow

A systematic debugging and optimization workflow for full-stack web applications (backend API + SPA frontend + database), abstracted from real-world project optimization. Framework-agnostic — applicable to any backend/frontend/database combination.

## When to Invoke

- User reports UI display issues (missing data, wrong values, hardcoded thresholds)
- User reports search/API failures (0 results, timeout, session expiration)
- User reports config changes not taking effect (stale values, no hot-reload)
- User requests feature parity between old and new UI versions
- User needs systematic root-cause analysis across frontend-backend-database stack
- User reports error messages that are technical/unfriendly and need UX improvement
- User needs to verify config-driven logic propagates correctly across all layers

## Core Principles

1. **Config-Driven**: All thresholds, weights, and parameters must come from a config source — never inline literals in business logic
2. **Hot-Reload**: Config changes must take effect without restart — read config at call-time, not at construction-time
3. **End-to-End Propagation**: Config values must flow from config source → backend logic → API response → frontend display
4. **Historical Consistency**: When config changes, historical data should be recomputable with new rules
5. **Layer-Aligned Field Names**: Field names must be identical across all layers (frontend interface, API response, database schema, event payload)

## Workflow Phases

### Phase 1: Symptom-to-Root-Cause Tracing

**Goal**: Trace user-reported symptom through the full stack to identify root cause.

**Steps**:

1. **Capture Symptom**: Record the exact URL, page, and specific issue description from user
2. **Frontend Code Review**: Read the page component to identify expected field names and data structure
   - Check TypeScript/interface definitions for expected field names
   - Check column/render definitions for display logic
   - Identify any hardcoded values or default fallbacks
3. **Backend Code Review**: Read the API endpoint to identify actual field names returned
   - Check route handler response structure
   - Check enrichment/serialization functions
   - Check payload construction in worker/event emitter
4. **Database Schema Review**: Verify stored field names match what backend reads
   - Check ORM model definitions
   - Check JSON payload structure in event/log tables
5. **Mismatch Identification**: Compare frontend expectations vs backend actuals vs database stored

**Decision Tree**:
```
Symptom: "Field X shows wrong value"
  ├─ Frontend expects field name "X"?
  │   ├─ YES → Backend returns field name "X"?
  │   │   ├─ YES → Database stores field name "X"?
  │   │   │   ├─ YES → Check value transformation logic (type conversion, formatting)
  │   │   │   └─ NO → Fix database schema or enrichment function
  │   │   └─ NO → Fix backend payload field name to match frontend
  │   └─ NO → Fix frontend to use correct field name from API
```

### Phase 2: Field Alignment Protocol

**Goal**: Ensure data field names are consistent across all layers.

**Checklist**:
- [ ] Frontend interface defines field `<entity>_<field>` consistently (e.g., `item_title`, not mixed `title` and `item_title`)
- [ ] Backend API response returns the same field name as frontend expects
- [ ] Backend enrichment function maps raw field names → aligned field names
- [ ] Worker/Event emitter writes aligned field names to payload
- [ ] Database column or JSON payload key matches the aligned name
- [ ] No mixed naming conventions (snake_case vs camelCase) within the same layer

**Common Patterns**:
- Use a consistent `<entity>_<field>` prefix for entity-related fields across all layers
- Enrichment functions should only supplement missing fields, not override existing values
- Top-level identifier fields (e.g., `<entity>_id`) should be both in event top-level AND payload for direct access
- When enriching from another table, map source field → target field explicitly

### Phase 3: Config-Driven Logic & Hot-Reload

**Goal**: Eliminate hardcoded values, ensure config changes take effect immediately.

**Anti-Pattern: Construction-Time Config Fixation**:
```python
# BAD: Config read once at construction, never updates
class Evaluator:
    def __init__(self):
        self.thresholds = load_config()  # Frozen at init time
        self.weights = load_config().weights  # Stale forever

    def evaluate(self, item):
        if self.score >= self.thresholds.pass_score:  # Uses stale config
            ...
```

**Pattern: Call-Time Config Reading**:
```python
# GOOD: Config read fresh on every call, changes take effect immediately
class Evaluator:
    def __init__(self, overrides=None):
        self._overrides = overrides  # Optional test overrides

    def _get_config(self):
        """Read config fresh each time — supports hot-reload"""
        if self._overrides:
            return self._overrides
        return load_config()  # Always returns current state

    def evaluate(self, item):
        cfg = self._get_config()  # Fresh read every call
        if self.score >= cfg.pass_score:  # Uses live config
            ...
```

**Checklist**:
- [ ] No magic numbers in business logic (scores, thresholds, weights, timeouts)
- [ ] All parameters come from a config source (YAML, env, database)
- [ ] Config is read at call-time, not construction-time (or config object is a live singleton)
- [ ] Config changes propagate without service restart
- [ ] Config singleton is not overwritten by concurrent initialization

### Phase 4: Config Validation

**Goal**: Prevent invalid config values from causing silent logic errors.

**Pattern: Model-Level Validation**:
```python
# Using Pydantic model_validator (or equivalent in other frameworks)
class WeightConfig(BaseModel):
    weight_a: int = 30
    weight_b: int = 30
    weight_c: int = 25
    weight_d: int = 15

    @model_validator(mode="after")
    def _check_weight_sum(self) -> "WeightConfig":
        total = self.weight_a + self.weight_b + self.weight_c + self.weight_d
        if total != 100:
            raise ValueError(f"Weights must sum to 100, got {total}")
        return self

class ThresholdConfig(BaseModel):
    pass_score: int = 60
    auto_score: int = 80

    @model_validator(mode="after")
    def _check_order(self) -> "ThresholdConfig":
        if self.pass_score > self.auto_score:
            raise ValueError(
                f"pass_score ({self.pass_score}) cannot exceed "
                f"auto_score ({self.auto_score})"
            )
        return self
```

**Frontend Validation Mirror**:
```tsx
// Frontend should validate before sending to backend
const handleSave = () => {
  const sum = weights.a + weights.b + weights.c + weights.d
  if (sum !== 100) {
    setError(`Weights must sum to 100, current: ${sum}`)
    return
  }
  if (thresholds.pass_score > thresholds.auto_score) {
    setError('Pass score cannot exceed auto score')
    return
  }
  save()
}
```

**Checklist**:
- [ ] Weight/percentage configs validate that sum equals expected total (e.g., 100)
- [ ] Ordered thresholds validate that lower bound ≤ upper bound
- [ ] Frontend mirrors backend validation for immediate feedback
- [ ] Invalid config raises clear error at save time, not silent degradation at runtime

### Phase 5: Dynamic Threshold Propagation

**Goal**: When backend uses config-driven thresholds, frontend display must adapt dynamically.

**Pattern: API Returns Active Thresholds**:
```python
# Backend: return thresholds alongside data
@router.get("/distribution")
def get_distribution():
    cfg = load_config()
    return {
        "data": [...],
        "thresholds": {
            "pass_score": cfg.pass_score,
            "auto_score": cfg.auto_score,
        }
    }
```

**Pattern: Frontend Reads Thresholds from API**:
```tsx
// Frontend: use API-returned thresholds, not hardcoded
const { data } = useQuery('/distribution')
const passScore = data?.thresholds?.pass_score ?? DEFAULT_PASS
const autoScore = data?.thresholds?.auto_score ?? DEFAULT_AUTO

// Color/label logic adapts to current config
const getRiskLevel = (score: number) => {
  if (score >= autoScore) return { label: 'Auto', color: 'green' }
  if (score >= passScore) return { label: 'Pass', color: 'orange' }
  return { label: 'Fail', color: 'red' }
}
```

**Anti-Pattern: Hardcoded Thresholds in Frontend**:
```tsx
// BAD: Frontend hardcodes same thresholds as backend
if (score >= 80) return 'green'   // What if config changes to 85?
if (score >= 60) return 'orange'  // What if config changes to 55?
```

**Checklist**:
- [ ] Backend API responses include active threshold values
- [ ] Frontend reads thresholds from API response, not inline literals
- [ ] Labels, colors, and category boundaries adapt to config changes
- [ ] Statistics cards and charts use dynamic thresholds for classification

### Phase 6: Historical Data Recompute

**Goal**: When config changes, historical data should be recomputable with new rules.

**Pattern: Recompute API**:
```python
@router.post("/recompute")
def recompute(task_id: str | None = None):
    """Re-evaluate historical records with current config"""
    evaluator = get_evaluator()  # Fresh instance with current config
    records = fetch_historical_records(task_id)

    for record in records:
        # Rebuild domain objects from stored data
        entity = rebuild_entity(record)
        related = rebuild_related(record)

        # Re-evaluate with current config
        result = evaluator.evaluate(entity, related)

        # Update stored record with new scores
        update_record(record.id, {
            "score": result.score,
            "risk_level": result.risk_level,
            "dimension_scores": result.dimension_scores,
            "recomputed_at": now(),
        })

    return {"recomputed": count, "errors": error_count}
```

**Checklist**:
- [ ] Recompute API exists for config-dependent scoring/evaluation
- [ ] Recompute rebuilds domain objects from stored data (not from live API)
- [ ] Recompute updates stored records with new results
- [ ] Frontend has a "Recompute" / "Re-evaluate" button to trigger
- [ ] Recompute handles missing related data gracefully (skip, don't crash)

### Phase 7: Error Detection & User Communication

**Goal**: Detect errors at backend, return structured flags, display user-friendly messages.

**Backend Error Detection Patterns**:

1. **Session/Cookie Expiration Detection**:
```python
# Detect: API responded but returned 0 results (possible login wall)
session_expired = (
    not results
    and getattr(collector, "_api_responded", False)
)
return {"session_expired": session_expired, "items": []}
```

2. **Database Table Existence Check**:
```python
# Check table existence before querying (prevent runtime errors)
# Use framework-appropriate method:
# - SQLAlchemy: inspect(engine).has_table("table_name")
# - Raw SQL: SELECT 1 FROM information_schema.tables WHERE ...
# - SQLite: SELECT 1 FROM sqlite_master WHERE type='table' AND name=?
if not table_exists("target_table"):
    return {}  # Silent skip, not error
```

3. **Technical Error Filtering**:
   - Database schema errors (`no such table`, `column not found`) → silent skip (technical, not user-facing)
   - Database lock errors (`database is locked`, `unable to open`) → user-friendly message about resource being busy
   - Network errors (timeout, connection refused) → user-friendly message about service availability

**Frontend Error Display Patterns**:

1. **Prominent Alert Banner for Critical Errors**:
```tsx
{sessionExpired && (
  <Alert
    type="error"
    showIcon
    banner
    message={t('errors.sessionExpired.title')}
    description={t('errors.sessionExpired.description')}
    action={
      <Button type="primary" onClick={() => navigate(loginRouteWithRedirect())}>
        {t('actions.relogin')}
      </Button>
    }
  />
)}
```

2. **HTTP Status to User Message Mapping** (use i18n, not hardcoded strings):
   - 401/403 → Set `sessionExpired=true`, show re-login banner
   - 404 → "Resource not found" (localized)
   - 422 → "Invalid request parameters" (localized)
   - Timeout → "Request timed out, please retry" (localized)

3. **Redirect-after-Login Flow**:
   - Navigate to login page with redirect param: `<login_route>?redirect=<current_path>`
   - Login page reads redirect param after success
   - Auto-navigate back to original page

### Phase 8: Concurrency & Resource Protection

**Goal**: Prevent concurrent access from causing data corruption or deadlocks.

**Patterns**:

1. **Mutex for Shared Browser/Resource**:
```python
from threading import Lock

resource_lock = Lock(timeout=10)  # 10-second timeout

def use_shared_resource():
    if not resource_lock.acquire(blocking=False):
        return {"error": "resource_busy", "message": "System is busy, please retry"}
    try:
        # Use shared resource (browser, file, etc.)
        ...
    finally:
        resource_lock.release()
```

2. **Singleton Protection**:
```python
# BAD: Multiple init calls overwrite singleton
container = Container()  # Called multiple times, overwrites previous

# GOOD: Use lru_cache or explicit singleton guard
@lru_cache(maxsize=1)
def get_container() -> Container:
    return Container()
```

3. **Page Route Cleanup**:
```python
# BAD: Passing handler can hang if page state changed
page.unroute("**/*", handler)

# GOOD: Remove all matching routes (no handler arg)
page.unroute("**/*")
```

**Checklist**:
- [ ] Shared resources (browser, database, file) protected by mutex/lock
- [ ] Lock has timeout to prevent permanent deadlock
- [ ] Busy resource returns 503 with user-friendly message
- [ ] Singletons use caching guard (lru_cache, module-level init)
- [ ] Route/event handler cleanup doesn't pass stale handler references

### Phase 9: Multi-Source Data Degradation Strategy

**Goal**: When reading data from multiple sources with varying reliability, ensure the most reliable source is tried first, with graceful degradation when sources are unavailable.

**Pattern: Priority-Ordered Source Chain**:
```python
# Data sources ordered by reliability (most reliable first)
# Each source may fail due to: encryption, file lock, process not running, stale data

async def read_data(keys: list[str]) -> dict:
    sources = [
        ("plaintext_store", read_from_json_store),    # Most reliable: plaintext, no encryption
        ("primary_db", read_from_system_db),          # May be encrypted (v20) or locked
        ("secondary_db", read_from_project_db),       # May be stale or empty
        ("runtime_api", read_from_live_process),      # May be unavailable (separated process)
    ]

    last_error = None
    for source_name, reader in sources:
        try:
            result = await reader(keys)
            if result:
                logger.info("Data found via %s: %d keys", source_name, len(result))
                return {"ok": True, "data": result, "source": source_name}
        except SourceEncryptedError:
            logger.warning("%s uses encryption, skipping", source_name)
            # Don't expose encryption details to user
        except SourceLockedError:
            last_error = "Resource is busy, please close the application"
        except SourceUnavailableError:
            logger.info("%s not available (process not running)", source_name)
            # Silent skip — not user-facing
        except Exception as e:
            last_error = str(e)

    # All sources exhausted — build user-friendly hint
    return {"ok": False, "data": {}, "error": build_error_hint(last_error)}
```

**Key Principles**:

1. **Plaintext Before Encrypted**: If a plaintext copy exists (e.g., JSON export), read it before attempting encrypted sources
2. **Silent Skip Technical Errors**: Database schema errors (`no such table`, `column not found`) should be logged but not shown to users
3. **User-Facing Error Hints**: When all sources fail, provide actionable hints (e.g., "Please use the login feature" or "Please close the browser and retry")
4. **Source Attribution**: Always return which source succeeded (for debugging and user transparency)
5. **Encryption Detection**: Detect encryption format markers (e.g., `v20` prefix) and skip gracefully without crashing

**Anti-Pattern: Single Source Dependency**:
```python
# BAD: Only reads from one source, fails when that source is unavailable
def get_cookie(name):
    db = read_sqlite("browser_cookies.db")
    return db.get(name)  # Fails if v20 encrypted or file locked

# GOOD: Tries plaintext JSON first, falls back to SQLite, then runtime API
def get_cookie(name):
    for source in [json_store, sqlite_db, runtime_api]:
        try:
            val = source.get(name)
            if val:
                return val
        except Exception:
            continue
    return None
```

**Checklist**:
- [ ] Multiple data sources tried in priority order (most reliable first)
- [ ] Plaintext/plain sources tried before encrypted/locked sources
- [ ] Technical errors (schema, encryption) silently skipped, not shown to users
- [ ] User-facing errors include actionable hints when all sources fail
- [ ] Successful source is attributed in response for debugging
- [ ] Encryption format detected and handled gracefully (skip, don't crash)
- [ ] Process-separated mode still works (fallback to shared file/JSON when runtime API unavailable)

### Phase 10: Logic Defect Repair

**Goal**: Fix calculation logic, overly permissive checks, and missing null protection.

**Patterns to Check**:

1. **Overly Permissive Validation**:
```python
# BAD: any() means 1 out of N valid fields passes
if any([has_field_a, has_field_b, has_field_c]):
    return False  # Not default

# GOOD: require minimum N valid fields (configurable threshold)
valid_count = sum([has_field_a, has_field_b, has_field_c])
min_required = config.min_valid_fields  # e.g., 2 out of 3
if valid_count >= min_required:
    return False  # Sufficient data
```

2. **Missing Null Checks**:
   - Check for `None`/`null` before calling `.toFixed()`, `.toLocaleString()`, etc.
   - Use `?? 0` or `|| 0` for numeric null coalescing
   - Use optional chaining `?.` for nested property access
   - Use `or 0` / `or ""` in Python for None coalescing

3. **Logger Format Mismatch**:
   - Identify which logging library is used and its format style (e.g., `{}` placeholder vs `%s`/`%d` printf-style)
   - Never mix formats — mixing causes format strings to appear literally in logs
   - Example: if library uses `{}` placeholders: `logger.info("Score is {}", score)` NOT `logger.info("Score is %s", score)`

4. **Weight Normalization**:
```python
# When weights don't sum to 100, normalize rather than fail
weight_sum = sum(weights.values())
if weight_sum == 0:
    # All-zero weights: fall back to equal weighting
    result = sum(scores.values()) // len(scores) if scores else 0
else:
    # Normalize: divide by actual sum
    result = sum(scores[k] * weights[k] for k in scores) // weight_sum
```

### Phase 11: Feature Parity Migration

**Goal**: Migrate features from old version to new version systematically.

**Steps**:
1. **Feature Inventory**: List all features in old version page
2. **Gap Analysis**: Compare with new version, identify missing features
3. **Priority Classification**: High (core functionality) / Medium (UX improvement) / Low (nice-to-have)
4. **Backend API Check**: Verify backend APIs already support missing features
5. **Frontend Implementation**: Add missing UI components and wire to existing APIs
6. **Visual Consistency**: Ensure new version matches or exceeds old version's UX

### Phase 12: Build-Test-Verify Cycle

**Goal**: Ensure changes are compiled, tested, and deployed correctly.

**Checklist**:
- [ ] Run backend tests (framework-appropriate command)
- [ ] Build frontend (framework-appropriate command)
- [ ] Check build exit code is 0
- [ ] Check build output directory has new files
- [ ] Restart backend service (if running)
- [ ] User hard-refreshes browser (bypass cache)
- [ ] Verify fix at reported URL
- [ ] Verify config changes propagate end-to-end (config → backend → API → frontend)
- [ ] Verify recompute produces correct results with new config

**Common Build Issues**:
- Terminal rendering crashes → use alternative terminal or shell
- Type errors → check UI library version compatibility (API changes between major versions)
- Missing imports → add newly used components to import statements
- Stale cache → hard refresh browser (Ctrl+F5 / Cmd+Shift+R)

## Config-Driven Parameters Reference

All thresholds, timeouts, and intervals should be managed via configuration. The table below shows the **categories** of parameters that should be config-driven — actual values and locations depend on the project:

| Parameter Category | Why Config-Driven | Validation Rule |
|---|---|---|
| Score/risk thresholds | Business logic changes without code deploy | Lower bound ≤ upper bound |
| Weight/percentage values | Tuning without code changes | Sum must equal expected total (e.g., 100) |
| API timeouts | Environment-dependent (local vs prod) | Positive integer |
| Polling intervals | Load-dependent tuning | Positive integer, ≥ min interval |
| Page sizes | UX tuning | Positive integer, ≤ max limit |
| Chart/bin counts | Visualization tuning | Within reasonable range (e.g., 4-20) |
| Token refresh intervals | Session policy dependent | Positive integer, < token TTL |
| Validation thresholds | Data quality tuning | Positive integer, ≤ total field count |
| Resource lock timeouts | Concurrency tuning | Positive integer, > expected operation time |

## Anti-Patterns to Avoid

1. **Hardcoded Magic Numbers**: Never inline thresholds, weights, or timeouts in business logic
2. **Construction-Time Config Fixation**: Don't read config once at init; read at call-time for hot-reload
3. **Mixed Field Naming**: Don't use different field names across layers (e.g., `title` in DB but `item_title` in API)
4. **Silent Failures**: Don't return empty results without indicating why (distinguish "no data" from "error")
5. **Technical Error Leakage**: Don't show database schema errors to end users
6. **Unbuilt Frontend**: Don't assume frontend changes auto-compile; always run build command
7. **Logger Format Mixing**: Don't mix `{}` and `%s`/`%d` formatting in the same logging system
8. **Overly Permissive Validation**: Don't use `any()` when you need `≥N/M` validation
9. **Missing Null Protection**: Don't call methods on potentially null/None values
10. **Stale Thresholds in Frontend**: Don't hardcode in frontend what backend already makes configurable
11. **No Recompute Path**: Don't make config changes that can't be applied to historical data
12. **Unprotected Shared Resources**: Don't allow concurrent access to browser/database without mutex
13. **Singleton Overwrite**: Don't re-initialize singletons without a caching guard
14. **Single Source Dependency**: Don't rely on only one data source when multiple exist; plaintext sources should be tried before encrypted/locked ones
15. **Encryption Crash**: Don't crash when encountering encrypted data; detect and skip gracefully, fall back to alternative sources

## Applicable Scenarios

- Full-stack web apps with backend API + SPA frontend (any framework combination)
- Projects with config-driven business logic (scoring, thresholds, weights, rules)
- Anti-bot/scraping systems with browser automation + session management
- Data pipeline debugging (collection → processing → storage → display)
- UI feature migration from old to new version
- Error handling and user experience improvement
- Config change propagation verification (end-to-end consistency)
- Historical data recompute after rule changes
- Multi-source data reading with encryption/lock fallback (cookie, session, credential management)

## Not Applicable Scenarios

- Pure frontend or pure backend projects (no cross-layer tracing needed)
- Projects without configuration management (all values are static)
- Static websites without dynamic data flow
- Projects without historical data (no recompute needed)
- Projects without shared resources (no concurrency protection needed)
- Projects using different paradigms (e.g., event-sourcing without config-driven logic)
