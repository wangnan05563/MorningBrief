---
name: workspace-cleanup
description: Use when cleaning up project workspaces, removing garbage files, organizing scattered scripts, or establishing file classification standards. Triggers on requests like "clean up the workspace", "organize the project structure", "centralize scripts into scripts/ directory", "remove junk files", or "寤虹珛鏂囦欢鍒嗙被鏍囧噯". Config-driven, parameterized, no hardcoded paths.
---

# Workspace Cleanup

## Overview

宸ヤ綔绌洪棿娓呯悊鏄竴椤?*鍛ㄦ湡鎬х淮鎶や换鍔?*锛屼笉鏄竴娆℃€ф竻鐞嗐€傚悓涓€椤圭洰鍙兘闇€瑕?3-5 杞凯浠ｆ墠鑳界ǔ瀹氫笅鏉ャ€?
**鏍稿績鍘熷垯锛?*
- **閰嶇疆椹卞姩**锛氭墍鏈夎鍒欙紙璺緞銆佸悗缂€銆佺櫧鍚嶅崟锛夐€氳繃 YAML 閰嶇疆绠＄悊锛岄浂纭紪鐮?- **瀹夊叏浼樺厛**锛氬垹闄ゅ墠蹇呴』鍏堝浠?hash锛屾竻鐞嗗悗蹇呴』楠岃瘉搴旂敤瀹屾暣鎬?- **6 闃舵闂幆**锛歊econ 鈫?Classify 鈫?Impact 鈫?Execute 鈫?Verify 鈫?Archive

**Violating the letter of this process is violating the spirit of cleanup.**

## The Iron Law

```
NO DELETION WITHOUT CONFIG-DRIVEN CLASSIFICATION FIRST
NO ARCHIVE WITHOUT POST-CLEANUP VERIFICATION
```


## Context Loading Rules

Follow this loading hierarchy to minimize token consumption:

**Tier 1 (always load):** This file + cleanup-config.yaml (or example fallback)
**Tier 2 (load when needed):** [references/decisions.md](file:///d:/code/otherProjects/19_Karpathy-AI+Obsidian知识库/.trae/skills/workspace-cleanup/references/decisions.md) — when handling boundary cases, confidence scoring, or decision logic details
**Tier 3 (load when needed):** [references/retrospective.md](file:///d:/code/otherProjects/19_Karpathy-AI+Obsidian知识库/.trae/skills/workspace-cleanup/references/retrospective.md) — when dealing with historical recurrence patterns, service detection edge cases, or PowerShell platform specifics

**Trigger Tier 2 when:** garbage_patterns does not cover a file, service state is ambiguous, special filenames detected, or confidence threshold questions arise.
**Trigger Tier 3 when:** cleanup is recurring (round 2+), service keeps regenerating files, or cross-platform command issues occur.

Most routine cleanups complete with Tier 1 only (~7,400 total tokens vs ~14,670 before).

## When to Use

**Use for:**
- 闀挎湡缁存姢鐨勯」鐩牴鐩綍姹℃煋锛堥噸瀹氬悜浜х墿銆佽皟璇曡剼鏈€佹祴璇曡緭鍑恒€佺紦瀛樼洰褰曪級
- 鑴氭湰鏂囦欢鏁ｈ惤鍦ㄥ悇瀛愮洰褰曪紙搴旂粺涓€鍒?`scripts/`锛?- 鍛ㄦ湡鎬ч闃叉€х淮鎶わ紙姣忓懆/姣忔湀璺戜竴娆★級
- 鍒濇鎺ユ墜椤圭洰鏃剁殑缁撴瀯姊崇悊
- 閲嶆瀯鍚庢壒閲忛噸鏂板垎绫?
**Use this ESPECIALLY when:**
- 鏈嶅姟杩愯涓寔缁骇鐢熸柊鍨冨溇锛堝繀椤诲厛鍋滄湇鍔★級
- 鏍圭洰褰曟枃浠舵暟 > 30锛堝惈鍙枒锛?- 鍥㈤槦鎴愬憳澶氭鍙嶉"椤圭洰缁撴瀯娣蜂贡"
- 鍑嗗鍋氬ぇ鍨嬮噸鏋勬垨杩佺Щ鍓嶇殑鏁寸悊

**Don't skip when:**
- 鐪嬩技"鍙垹鍑犱釜鏂囦欢"锛堝垹闄ゅ喅绛栧簲鍙拷婧級
- 鐢ㄦ埛璇?灏卞揩閫熸竻涓€涓?锛堝揩閫?= 璇垹椋庨櫓楂橈級
- 宸茬粡鍋氳繃娓呯悊浜嗭紙鍛ㄦ湡鎬х淮鎶わ紝姣忚疆閮藉彲鑳藉彂鐜版柊闂锛?

## Configuration

**Required:** Read cleanup-config.yaml first. If absent, copy from [examples/cleanup-config.example.yaml](file:///d:/code/otherProjects/19_Karpathy-AI+Obsidian知识库/.trae/skills/workspace-cleanup/examples/cleanup-config.example.yaml).

Config has 10 sections: workspace, 
oot_allowlist, script_extensions, garbage_patterns, detection, service_indicators, stability_check, platform, erification, rchive + safety. Full schema with examples in the YAML file above.

**Loading priority:** 1) User cleanup-config.yaml -> 2) Example fallback -> 3) STOP and ask user.

See [references/decisions.md](file:///d:/code/otherProjects/19_Karpathy-AI+Obsidian知识库/.trae/skills/workspace-cleanup/references/decisions.md) for 7 core decision logic trees.
---
## The Six Phases

Complete each phase in order. Output a compact report after each.

### Phase 1: Recon

**Goal:** Collect ground truth. NO deletions.

1. **List root files** with sizes: Get-ChildItem -File (Win) / ls -la (Linux/macOS). Note: LS tool has 40000 char cutoff — use PowerShell/Bash for large dirs. Record: filename, size, extension, mtime.
2. **List subdirs** at depth 1-2 (exclude node_modules/, .venv/, .git/, __pycache__/). Scan workspace.frontend_dir if configured.
3. **Read .gitignore**, compare with actual files, record gaps.
4. **Decision 7 (pattern inference)** if detection.enabled: true: check detection.prefix_indicators, name_keywords, name_patterns. Compute confidence — below infer_confidence_threshold marks as suspicious.
5. **Output:** file inventory table + suspicious files list.

**Report:** Files: N | Subdir scripts: M | Frontend: F | Gaps: G | Inferred: I

### Phase 2: Classify

1. **Decision 1 (garbage?):** Match against garbage_patterns categories. If in root and NOT in root_allowlist -> mark scattered.
2. **Decision 2 (script?):** Check script_extensions + script_exclude_dirs for non-allowlisted root/scattered files.
3. **Hash** files marked Delete/Move: Get-FileHash / sha256sum. Log to logs/cleanup-{YYYYMMDD-HHmmss}.log.
4. **Output:** Classification table (Action: Delete/Move/Keep, Reason, Target).

**Report:** Delete: X | Move: Y | Keep: Z | Backup: logs/cleanup-...log

### Phase 3: Impact

1. **Decision 3 (service check - 4-way):**
   - PID file: check service_indicators.pid_files, verify process exists
   - Port: check service_indicators.ports via netstat/lsof/ss
   - Process name: check service_indicators.process_names
   - File occupancy: check service_indicators.file_occupancy_probes via platform.commands.file_occupancy_check
2. **If service running** AND safety.require_stopped_service: true: STOP and ask user to (a) stop service, (b) soft-delete, (c) skip moves only, or (d) cancel.
3. **Decision 6 (special filenames):** Scan delete targets for special chars. If safety.special_filename_handling: safe, mark for Get-ChildItem matching.

**Report:** Service: yes/no | Stale PIDs: list | Locked: list | Special: list | Action: proceed/wait/soft-delete

### Phase 4: Execute

**Order (lowest risk first):**
1. **Cache dirs** -> platform.commands.remove_dir for each cache_dirs entry
2. **Redirect artifacts + tmp** -> platform.commands.remove_file. Special filenames: use Get-ChildItem + Where-Object + -LiteralPath if safety.special_filename_handling: safe.
3. **Test outputs** -> platform.commands.remove_file
4. **Move scripts** to script_dir. Handle conflicts: prompt or auto-rename.
5. **Delete high-confidence root files** matching garbage_patterns or inference >= threshold. Large files (> safety.large_file_threshold_mb MB) need second confirmation.

**Batching:** Respect safety.max_files_per_batch. Verify each batch with Test-Path.
**PS notes:** Use script: vars (not hashtables), dollar-brace syntax, -LiteralPath. See PowerShell Best Practices above.
**Stability check** if stability_check.enabled: snapshot -> wait stability_check.wait_seconds -> rescan -> compare -> match recurrence_patterns -> act per recurrence_action. Stop if exceeds max_recurrence.

**Report:** Deleted: X (freed NN MB) | Moved: Y | Errors: Z | Batches: N | Stability: new=K action=[proceed/warn/stop]

### Phase 5: Verify

1. **Run verification command** from config using platform.venv_python + verification.python_imports. Exit 0 = pass.
2. **On failure:** DO NOT proceed to Phase 6. Report details. Suggest rollback from verification.on_failure.
3. **Integrity checklist:** Core import OK | Root count before->after | scripts/ count | frontend count | no accidental deletion (cross-check backup log hashes)
4. **Optional:** run tests if tests/ exists (pytest / npm test)

**Report:** Import: PASS/FAIL | Tests: PASS/FAIL/SKIP | Checklist: [5 items] | Rollback: (if FAIL)

### Phase 6: Archive

1. **Update .gitignore** if archive.auto_update_gitignore: true. Group new patterns by category.
2. **Update .pre-commit-config.yaml** if archive.auto_update_precommit: true.
3. **Update changelog** at archive.changelog_path: date, background, actions table, verification, files added.
4. **Final report:** total cleaned, space freed, root files (before->after), scripts count, verification status, recurrence prevention.

**Report:** Gitignore rules: N | Pre-commit: yes/no | Changelog: path | Freed: NN MB | Root: A->B

---
## Safety Checklist

STOP immediately if any of these apply:
- Proceeding to Phase 4 without finishing Phases 1-3 reports
- Deleting files without writing hash to backup log first
- Skipping Phase 5 because it should be fine
- Hardcoding paths instead of using config
- Adding to .gitignore without also updating pre-commit
- Service running but proceeding to Phase 4
- Bulk delete of >20 files without batching
- Interpreting clean it up as delete everything I did not write
- Using PowerShell variable syntax without proper wrapping
- Using hashtable strict mode incorrectly
- Ignoring stability check warnings
- Skipping file occupancy check when PID files missing

---

## When NOT to Use

Skip for: empty repos, monorepo single packages, 24/7 prod services (cannot stop), teams >20 people (use PR-based cleanup), large binaries in root (delete = redownload), macOS/Linux only (no Windows). For concurrent AI sessions, stop all background sessions first.

---

## Execution Rules

- **Config-driven:** Read config -> Apply patterns -> Report. Never delete without checking config first.
- **Backup before delete:** Hash file -> Log to cleanup.log -> Then remove.
- **Service check:** Verify PID file, port listening, process name before any deletion.
- **Verify:** Run import check -> exit 0 -> Report PASS. Never skip.
- **Prevent recurrence:** Update .gitignore + pre-commit + changelog (all three).

Quick pattern reference: see [cleanup-config.example.yaml](file:///d:/code/otherProjects/19_Karpathy-AI+Obsidian知识库/.trae/skills/workspace-cleanup/examples/cleanup-config.example.yaml) garbage_patterns section for all 11 common patterns.

---
## PowerShell Best Practices

> Full code examples in [references/decisions.md](file:///d:/code/otherProjects/19_Karpathy-AI+Obsidian知识库/.trae/skills/workspace-cleanup/references/decisions.md) Section 6.

- Variable trap: use `${var}` syntax when variable name is followed by colon
- Hashtable strict mode: use `[PSCustomObject]` or `$script:` variables instead of `@{}`
- Special filenames: use `Get-ChildItem` + `Where-Object` with `-LiteralPath` instead of direct path strings
- File lock detection: `[System.IO.File]::Open()` with try/catch
- Cross-platform: select commands from `platform.commands` based on `platform.current`

---

## Configuration Fallback

> Detailed tables in [references/decisions.md](file:///d:/code/otherProjects/19_Karpathy-AI+Obsidian知识库/.trae/skills/workspace-cleanup/references/decisions.md) Section 5 and [references/retrospective.md](file:///d:/code/otherProjects/19_Karpathy-AI+Obsidian知识库/.trae/skills/workspace-cleanup/references/retrospective.md) Section 7.

| Missing Config | Fallback Strategy |
|---|---|
| `garbage_patterns` partial | Enable `detection` inference |
| `service_indicators.file_occupancy_probes` | PID + port + process name only |
| `stability_check` | Skip stability check |
| `platform.commands` | Default Windows commands |
| `detection` | No pattern inference |

**Confidence threshold:** Above `infer_confidence_threshold` -> auto-delete. Below -> mark as suspicious, require confirmation.

---
## The Bottom Line

**No cleanup without config, no delete without backup, no archive without verification.**

Read config 鈫?Run 6 phases 鈫?Output report. This is non-negotiable.

If config is missing, STOP and ask the user to provide `cleanup-config.yaml` or copy from `examples/cleanup-config.example.yaml`.

**閰嶇疆椹卞姩 + 妯″紡鎺ㄦ柇 + 鍥涢噸鏈嶅姟妫€娴?+ 绋冲畾鎬ф鏌?+ 寮傚父鏂囦欢鍚嶅鐞?= 鍋ュ．鐨勬竻鐞嗘祦绋嬨€?*
