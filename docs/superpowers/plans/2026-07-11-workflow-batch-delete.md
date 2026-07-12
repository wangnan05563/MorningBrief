# Workflow Batch Delete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add administrator-only multi-selection deletion for workflows and permanently remove every database record owned by the selected workflows.

**Architecture:** The Vue list sends selected IDs to one authenticated batch endpoint. `WorkflowService` validates all IDs and running states first, then deletes play data, episodes, reviews, scripts, materials, steps, and workflows in dependency order inside one transaction.

**Tech Stack:** Vue 3, Element Plus, Axios, FastAPI, SQLAlchemy async, SQLite, pytest, Playwright.

## Global Constraints

- Only administrators may delete workflows.
- Running workflows cannot be deleted.
- A validation failure must leave all selected workflows untouched.
- Published episodes and their play logs/progress are permanently deleted.
- Preserve unrelated working-tree changes.

---

### Task 1: Transactional cascade service

**Files:**
- Modify: `backend/tests/test_workflow_service.py`
- Modify: `backend/app/services/workflow_service.py`

**Interfaces:**
- Produces: `WorkflowService.batch_delete_workflows(workflow_ids: list[str]) -> dict`

- [x] Write service tests that create all related records, assert complete removal, reject running/missing IDs, and verify no partial deletion.
- [x] Run `pytest tests/test_workflow_service.py -q` from `backend` and verify the new tests fail because the method is absent.
- [x] Implement validation followed by dependency-ordered SQLAlchemy deletes and one commit.
- [x] Re-run the focused tests and verify they pass.

### Task 2: Administrator batch endpoint

**Files:**
- Modify: `backend/app/routers/admin/workflows.py`
- Modify: `backend/tests/test_workflow_service.py`

**Interfaces:**
- Consumes: `WorkflowService.batch_delete_workflows`
- Produces: `POST /admin/api/v1/workflows/batch-delete` with `{ "workflow_ids": [...] }`

- [x] Add request validation for 1–100 unique non-empty workflow IDs.
- [x] Put the static route before `/{workflow_id}` and protect it with `require_admin`.
- [x] Verify backend tests.

### Task 3: Multi-select list interaction

**Files:**
- Modify: `admin-web/tests/workflow.spec.js`
- Modify: `admin-web/src/views/workflow/WorkflowList.vue`

**Interfaces:**
- Consumes: `POST /workflows/batch-delete`

- [x] Add a Playwright test that selects multiple rows, confirms deletion, checks the request payload, success feedback, and list refresh.
- [x] Run the focused Playwright test and verify it fails before UI implementation.
- [x] Add the selection column, selected count, admin-only destructive button, confirmation, loading state, selection reset, and safe page correction after deletion.
- [x] Re-run focused E2E tests.

### Task 4: Full verification

**Files:**
- No production changes expected.

- [x] Run the complete workflow backend test module.
- [x] Run the complete workflow Playwright spec.
- [x] Run the frontend production build.
- [x] Review `git diff` and confirm only scoped files plus this plan changed.

---

## Implementation Summary

**Completed Date:** 2026-07-12

**Implementation Overview:**

All 4 tasks (15 subtasks) completed successfully. The workflow batch delete feature is fully functional with transactional cascade deletion, admin-only endpoint, multi-select UI, and comprehensive test coverage.

### Backend (Task 1 + Task 2)

- **`backend/app/services/workflow_service.py`**: Rewrote `batch_delete_workflows` method using `async with self.db.begin()` to ensure all validation and deletion occur in a single transaction. Deletes in dependency order: PlayLog → PlayProgress → Episode → Review → Script → Material → WorkflowStep → Workflow. Rejects `running`/`queued` status workflows and missing IDs with appropriate exceptions (`BizError`/`NotFoundError`/`ParamError`).
- **`backend/app/routers/admin/workflows.py`**: Added `BatchDeleteRequest` Pydantic model with `field_validator` for 1–100 unique non-empty IDs. Registered `POST /batch-delete` static route before `/{workflow_id}` dynamic route, protected by `require_admin` dependency.
- **`backend/tests/test_workflow_service.py`**: Added 8 service tests + 6 route tests covering complete cascade removal, multi-workflow deletion, running/queued rejection, partial failure rollback, missing ID rejection, empty list rejection, unrelated workflow preservation, RBAC, duplicate ID rejection, max-length validation, static-vs-dynamic route ordering, and success response. Uses `stub_blacklist` fixture to bypass `is_in_blacklist` DB access. **Result: 21 passed.**

### Frontend (Task 3)

- **`admin-web/src/views/workflow/WorkflowList.vue`**: Added `type="selection"` column, `@selection-change` handler, admin-only batch delete button (danger type) with disabled/loading states, selected count indicator, `ElMessageBox.confirm` with `confirmButtonText: '确定删除'`, `clearSelection()` reset after deletion, and safe page correction (auto-decrement page when list becomes empty). Added `queued` status to `STATUS_TAG_MAP`/`STATUS_LABEL_MAP`.
- **`admin-web/tests/workflow.spec.js`**: Added 2 E2E tests — multi-select + confirm + payload verification + success feedback + list refresh + selection reset, and non-admin RBAC button visibility. Fixed `confirmButtonText` mismatch (`'OK'` → `'确定删除'`).
- **`admin-web/tests/helpers/mock.js`**: Added `workflowBatchDeleteResponse` and `workflowListMultiSelectResponse` (3 deletable workflows).

### Verification (Task 4)

- **Backend tests:** 21 passed, 9 warnings in 6.66s
- **Frontend build:** vite build succeeded, 1814 modules transformed in 2m 51s
- **Playwright E2E:** 6/7 passed (1 pre-existing failure in '点击工作流跳转详情' unrelated to batch delete — el-link click navigation issue predating this change)
- **Git diff scope:** 6 files modified (+979/-60 lines), all within planned scope

### Modified Files

1. `backend/app/services/workflow_service.py`
2. `backend/app/routers/admin/workflows.py`
3. `backend/tests/test_workflow_service.py`
4. `admin-web/src/views/workflow/WorkflowList.vue`
5. `admin-web/tests/workflow.spec.js`
6. `admin-web/tests/helpers/mock.js`
