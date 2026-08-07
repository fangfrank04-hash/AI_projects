# Fixed Rear 45-Degree Test Set Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve seven field photos as an independent fixed-rear-camera regression set and generate a separate report without changing recognition behavior or the 305-image baseline.

**Architecture:** Store immutable copies of the seven received JPGs under `assets/test_images/fixed_rear_45deg/images/` and define their labels in a manifest with the existing schema. Reuse `scripts/verify_actions_v2.py` with explicit `--answers` and `--output-dir`; make report generation display the actual answer path passed by the caller.

**Tech Stack:** Python, CSV, Pillow, existing MediaPipe verifier, pytest.

---

### Task 1: Add manifest and copied field photos

**Files:**
- Create: `assets/test_images/fixed_rear_45deg/images/rear45_001_normal.jpg`
- Create: `assets/test_images/fixed_rear_45deg/images/rear45_002_turn_head.jpg`
- Create: `assets/test_images/fixed_rear_45deg/images/rear45_003_turn_head_body.jpg`
- Create: `assets/test_images/fixed_rear_45deg/images/rear45_004_stand_up.jpg`
- Create: `assets/test_images/fixed_rear_45deg/images/rear45_005_stretch_arm.jpg`
- Create: `assets/test_images/fixed_rear_45deg/images/rear45_006_stretch_arm.jpg`
- Create: `assets/test_images/fixed_rear_45deg/images/rear45_007_normal.jpg`
- Create: `assets/test_images/fixed_rear_45deg/test_answers.csv`

- [ ] **Step 1: Copy the seven original JPGs without recompression**

Copy the seven files from the Windows temporary directory into the exact paths above. Verify each destination has the same byte length and SHA-256 hash as its source.

- [ ] **Step 2: Write the independent answer manifest**

Use fields `image_path,source_set,scenario,expected_category,split,include_in_main,note`. Set `source_set=fixed_rear_45deg`, `split=field_check`, and `include_in_main=0` for every row. Use the seven business labels agreed with the user.

- [ ] **Step 3: Validate the manifest**

Run a Python check calling `load_answer_manifest()` and assert exactly seven rows, zero included in the main set, and all files exist.

- [ ] **Step 4: Commit the data set**

Run `git add assets/test_images/fixed_rear_45deg` then `git commit -m "data: add fixed rear camera test set"`.

### Task 2: Fix custom-report answer path display

**Files:**
- Modify: `scripts/verify_actions_v2.py:112-155`
- Test: `tests/test_verify_actions_v2.py`

- [ ] **Step 1: Add a failing report test**

Call `write_reports(rows, summary, output_dir, answers_path=Path("custom/answers.csv"))` and assert the Markdown contains `custom/answers.csv`. The current function signature does not accept `answers_path`, so this test must fail first.

- [ ] **Step 2: Implement the smallest API-compatible change**

Add an optional `answers_path=ANSWERS_PATH` parameter to `write_reports()`, use `Path(answers_path).relative_to(ROOT_DIR)` when possible, and fall back to `Path(answers_path)` for external temporary paths. Pass `answers_path` from `run_verification()`. Do not change scoring or row collection.

- [ ] **Step 3: Run focused tests**

Run `\.venv\Scripts\python.exe -m pytest tests/test_verify_actions_v2.py -q`. Expected: all tests pass.

- [ ] **Step 4: Commit the report fix**

Run `git add scripts/verify_actions_v2.py tests/test_verify_actions_v2.py` then `git commit -m "fix: show custom answer path in reports"`.

### Task 3: Generate and verify the independent report

**Files:**
- Create: `reports/fixed_rear_45deg/detection_report.md`
- Create: `reports/fixed_rear_45deg/detection_results.csv`

- [ ] **Step 1: Run the independent verifier**

Run `\.venv\Scripts\python.exe scripts/verify_actions_v2.py --answers assets/test_images/fixed_rear_45deg/test_answers.csv --output-dir reports/fixed_rear_45deg`. Expected: exactly seven images processed and the main `reports/detection_report.md` remains unchanged.

- [ ] **Step 2: Check category outcomes**

Confirm the report records the current baseline, including the known rear-camera misclassifications. Do not edit labels to improve the score.

- [ ] **Step 3: Run manifest and full unit tests**

Run `\.venv\Scripts\python.exe -m pytest tests/test_answer_manifest.py tests/test_verify_actions_v2.py -q` and then `\.venv\Scripts\python.exe -m pytest -q`.

- [ ] **Step 4: Commit the report**

Run `git add reports/fixed_rear_45deg` then `git commit -m "test: record fixed rear camera baseline"`.

### Task 4: Final integrity check

**Files:**
- Verify: `assets/test_images/test_answers.csv`
- Verify: `reports/detection_report.md`
- Verify: `assets/test_images/fixed_rear_45deg/test_answers.csv`

- [ ] **Step 1: Confirm the main set is unchanged**

Run `Import-Csv assets/test_images/test_answers.csv | Measure-Object` and confirm it still has 305 rows.

- [ ] **Step 2: Confirm the new set is isolated**

Run `Import-Csv assets/test_images/fixed_rear_45deg/test_answers.csv | Where-Object include_in_main -ne 0` and expect no output.

- [ ] **Step 3: Confirm a clean tree and list recent commits**

Run `git status --short` and `git log -5 --oneline`; expected clean tree and three commits for the data, report fix, and report.
