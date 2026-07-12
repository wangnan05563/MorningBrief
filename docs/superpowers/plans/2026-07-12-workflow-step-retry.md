# Workflow Step Retry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retry a selected workflow step without rerunning its successful predecessors.

**Architecture:** The scheduler creates a new workflow, copies the successful predecessor step results from the original workflow, and persists them as successful steps on the new workflow. When execution begins, the scheduler rebuilds context from those persisted results and runs only missing steps from the selected step onward.

**Tech Stack:** FastAPI, SQLAlchemy async, Python 3.14, pytest.

## Global Constraints

- A retry must create a new workflow and must not mutate the original workflow.
- A retry must preserve the original episode date, channel, and priority.
- A retry may reuse only successful predecessor results; missing or failed prerequisites return a business error.
- The TTS retry path must not call the crawler or rewriter.

---

### Task 1: Persist and validate retry prerequisites

**Files:**
- Modify: `backend/app/services/workflow_scheduler.py`
- Modify: `backend/app/routers/admin/workflows.py`
- Test: `backend/tests/test_workflow_step_retry.py`

**Interfaces:**
- Produces `WorkflowScheduler.retry_workflow(original_workflow_id: str, step: str, triggered_by: str) -> str`.

- [ ] **Step 1: Write failing scheduler tests**

```python
async def test_retry_tts_copies_rewrite_result_and_preserves_workflow_metadata():
    new_id = await scheduler.retry_workflow("wf-old", "tts", "admin")
    new_steps = await steps_for(new_id)
    assert [step.step_name for step in new_steps] == ["crawl", "rewrite"]
    assert new_steps[1].result == {"script_id": 42}

async def test_retry_tts_rejects_missing_rewrite_output():
    with pytest.raises(ParamError, match="rewrite"):
        await scheduler.retry_workflow("wf-old", "tts", "admin")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_workflow_step_retry.py -q`

Expected: FAIL because the scheduler has no `retry_workflow` method.

- [ ] **Step 3: Implement retry creation**

```python
STEP_ORDER = (WorkflowStepName.crawl, WorkflowStepName.rewrite,
              WorkflowStepName.tts, WorkflowStepName.stitch,
              WorkflowStepName.review)

async def retry_workflow(self, original_workflow_id, step, triggered_by):
    start_index = STEP_ORDER.index(WorkflowStepName(step))
    predecessor_results = await self._load_retry_predecessors(
        original_workflow_id, STEP_ORDER[:start_index]
    )
    return await self.trigger_workflow(
        episode_date=original.episode_date, source="manual",
        channel_id=original.channel_id, priority=original.priority,
        reused_step_results=predecessor_results,
    )
```

- [ ] **Step 4: Run scheduler tests to verify they pass**

Run: `python -m pytest tests/test_workflow_step_retry.py -q`

Expected: PASS.

### Task 2: Resume execution after persisted predecessors

**Files:**
- Modify: `backend/app/services/workflow_scheduler.py`
- Test: `backend/tests/test_workflow_step_retry.py`

**Interfaces:**
- Consumes persisted successful predecessor `WorkflowStep.result` records.
- Produces a context containing reused `script_id` / `audio_segments` / `final_audio_url` and executes only missing canonical steps.

- [ ] **Step 1: Write failing execution test**

```python
async def test_resumed_tts_workflow_skips_crawl_and_rewrite(monkeypatch):
    await scheduler._run_workflow("wf-retry", date.today())
    crawler_mod.run.assert_not_awaited()
    llm_mod.rewrite.assert_not_awaited()
    tts_mod.synthesize.assert_awaited_once_with("wf-retry", 42)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_workflow_step_retry.py -q`

Expected: FAIL because `_run_workflow` always calls the crawler first.

- [ ] **Step 3: Implement context restoration and conditional execution**

```python
completed, context = await self._load_completed_step_context(workflow_id)
if WorkflowStepName.crawl not in completed:
    await self._run_step(...crawl...)
if WorkflowStepName.rewrite not in completed:
    await self._run_step(...rewrite...)
```

- [ ] **Step 4: Run focused and complete tests**

Run: `python -m pytest tests/test_workflow_step_retry.py tests/test_workflow_service.py tests/test_queue_service.py -q`

Expected: PASS.
