# Gaze-Away Rule Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Correct seated-turn business classification and conservatively improve gaze-away detection while preserving all 37 normal-exam samples.

**Architecture:** Keep `ActionType.TURN_BODY` as the machine-readable pose subtype, but map it to the gaze-away business category and label. Evaluate head-angle candidates through the existing strict manifest; only retain a candidate that improves gaze-away without reducing normal, leave-seat, multi-person, phone-call, or stretch-arm results. Keep the mirrored split-deployment application synchronized.

**Tech Stack:** Python, MediaPipe, OpenCV, PIL, pytest, Ruff, existing 305-image verification script.

---

### Task 1: Add regression tests for seated-turn classification

**Files:**
- Modify: `tests/test_verify_actions_v2.py`
- Modify: `tests/test_image_proctor_behaviors.py`

- [ ] **Step 1: Write the failing classification assertions**

Add a test fixture result with `action_type="turn_body"` and assert that `run_single()` reports `actual_category == "视线偏移"`. Add a behavior test for `turn_body_left_90_01_174519.jpg` asserting the raw result remains `ActionType.TURN_BODY`; the test must distinguish subtype preservation from business-category mapping.

- [ ] **Step 2: Run the focused tests and verify the expected failure**

Run:
`\.venv\Scripts\python.exe -m pytest tests/test_verify_actions_v2.py tests/test_image_proctor_behaviors.py -q`

Expected: the new category assertion fails because `turn_body` currently maps to `离开座位`; the existing tests continue to pass.

- [ ] **Step 3: Commit the regression tests**

Run:
`git add tests/test_verify_actions_v2.py tests/test_image_proctor_behaviors.py`
`git commit -m "test: protect seated turn gaze classification"`

### Task 2: Implement the minimal seated-turn classification fix

**Files:**
- Modify: `scripts/verify_actions_v2.py:31-40`
- Modify: `app/ml/image_proctor.py:708`
- Modify: `deploy_split/code/app/ml/image_proctor.py:708`

- [ ] **Step 1: Change only the business mapping and label**

Change `ACTION_CATEGORY_MAP["turn_body"]` to `视线偏移`. Keep `ActionType.TURN_BODY` unchanged. Change the result label from `离开座位(考生转身)` to `视线偏移(考生转身)` in both application copies. Do not alter the shoulder-distance rule or its priority.

- [ ] **Step 2: Run focused tests**

Run:
`\.venv\Scripts\python.exe -m pytest tests/test_verify_actions_v2.py tests/test_image_proctor_behaviors.py -q`

Expected: all focused tests pass.

- [ ] **Step 3: Run the strict 305-image verification**

Run:
`\.venv\Scripts\python.exe scripts/verify_actions_v2.py`

Expected acceptance: `正常考试 37/37`, `视线偏移` at least `54/68`, overall at least `256/305`, and no category other than gaze-away loses a pass compared with the baseline. Record the generated report before proceeding.

- [ ] **Step 4: Commit the classification fix**

Run:
`git add app/ml/image_proctor.py deploy_split/code/app/ml/image_proctor.py scripts/verify_actions_v2.py reports/detection_report.md reports/detection_results.csv tests/test_verify_actions_v2.py tests/test_image_proctor_behaviors.py`
`git commit -m "fix: classify seated turns as gaze away"`

### Task 3: Add an isolated, testable head-direction decision boundary

**Files:**
- Modify: `app/ml/image_proctor.py:431-479`
- Modify: `deploy_split/code/app/ml/image_proctor.py:431-479`
- Modify: `tests/test_face_angle_params.py`

- [ ] **Step 1: Write failing unit tests for the pure boundary helper**

Add tests for a helper that receives `(pitch, yaw)` and the four active thresholds and returns `0` for normal and a non-zero direction for each exceeded boundary. Add a test proving custom `FaceAngleThresholds` still affect the helper through the existing `analyze()` path and reset to defaults on the next request.

- [ ] **Step 2: Run the focused tests to verify failure**

Run:
`\.venv\Scripts\python.exe -m pytest tests/test_face_angle_params.py -q`

Expected: failure because the helper does not yet exist.

- [ ] **Step 3: Implement the pure helper and call it from `_get_face_angle()`**

Extract only the existing comparisons from `_get_face_angle()` into a side-effect-free method. Preserve current direction priority: right, left, down, up. Keep threshold storage and request reset unchanged.

- [ ] **Step 4: Run the focused tests**

Run:
`\.venv\Scripts\python.exe -m pytest tests/test_face_angle_params.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit the refactor before tuning**

Run:
`git add app/ml/image_proctor.py deploy_split/code/app/ml/image_proctor.py tests/test_face_angle_params.py`
`git commit -m "refactor: isolate head direction boundary"`

### Task 4: Evaluate and apply only a safe head-angle candidate

**Files:**
- Modify only if a candidate passes all guards: `app/ml/image_proctor.py:49-53`
- Modify only if a candidate passes all guards: `deploy_split/code/app/ml/image_proctor.py:49-53`
- Modify only if needed: `tests/test_face_angle_params.py`

- [ ] **Step 1: Establish the post-classification baseline**

Run the strict verifier again and save the category counts from `reports/detection_report.md` and `reports/detection_results.csv`.

- [ ] **Step 2: Test one candidate direction at a time**

Use the existing `FaceAngleThresholds` override path to evaluate a candidate on all 305 images. Start with the smallest change that could catch the known missed upward/head-turn samples; do not change more than one of `max_left_angle`, `max_right_angle`, `max_up_angle`, or `max_down_angle` per trial.

- [ ] **Step 3: Apply the candidate only when all acceptance guards pass**

Keep the candidate only if normal remains `37/37`, gaze-away improves, and leave-seat, multi-person, phone-call, and stretch-arm do not decline. Otherwise leave defaults unchanged and document that no safe threshold candidate exists in this dataset.

- [ ] **Step 4: Run the full test suite and lint**

Run:
`\.venv\Scripts\python.exe -m pytest -q`
`\.venv\Scripts\python.exe -m ruff check app tests scripts`

Expected: all tests pass and Ruff reports no errors.

- [ ] **Step 5: Run final strict verification and commit**

Run:
`\.venv\Scripts\python.exe scripts/verify_actions_v2.py`

Confirm normal false positives are `0/37`, then commit all approved source, mirrored deployment, test, and report changes with:
`git add app deploy_split/code/app scripts tests reports`
`git commit -m "tune: improve gaze-away detection with regression guards"`

### Task 5: Final consistency check

**Files:**
- Verify: `app/ml`, `deploy_split/code/app/ml`, `scripts/verify_actions_v2.py`, `reports/detection_report.md`

- [ ] **Step 1: Confirm source and split deployment copies match**

Run:
`git diff --no-index -- app/ml/image_proctor.py deploy_split/code/app/ml/image_proctor.py`

Expected: no differences.

- [ ] **Step 2: Confirm working tree and recent commits**

Run:
`git status --short`
`git log -4 --oneline`

Expected: clean working tree and separate commits for tests, classification fix, boundary refactor, and approved tuning.
