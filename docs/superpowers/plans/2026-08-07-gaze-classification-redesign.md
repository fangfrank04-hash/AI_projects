# Gaze Classification Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Distinguish seated turns from generic body turns and conservatively improve downward gaze detection while preserving every normal-exam result.

**Architecture:** Add a machine-readable `seated_turn` subtype selected only after the existing narrow-shoulder rule and a new dual-hip visibility guard. Keep generic `turn_body` behavior unchanged, isolate the face-direction boundary as a pure method, and adjust only the configured downward boundary from `-1` to `-0.5`.

**Tech Stack:** Python 3.10+, MediaPipe, OpenCV, Pydantic Settings, pytest/unittest, Ruff, Docker Compose.

---

### Task 1: Add the seated-turn configuration and action contract

**Files:**
- Modify: `app/core/config.py`
- Modify: `app/schemas/proctor.py`
- Modify: `deploy_split/code/app/core/config.py`
- Modify: `deploy_split/code/app/schemas/proctor.py`
- Modify: `.env.example`
- Modify: `README.md`
- Test: `tests/test_config.py`
- Test: `tests/test_deploy_sync.py`

- [ ] **Step 1: Write failing configuration and schema tests**

Assert that `Settings(_env_file=None).seated_turn_max_hip_visibility == 0.05`, values outside `0..1` raise `ValidationError`, and `ActionType.SEATED_TURN.value == "seated_turn"`. Extend deployment byte-sync coverage to `app/schemas/proctor.py`.

```python
self.assertEqual(0.05, Settings(_env_file=None).seated_turn_max_hip_visibility)
self.assertEqual("seated_turn", ActionType.SEATED_TURN.value)
with self.assertRaises(ValidationError):
    Settings(_env_file=None, seated_turn_max_hip_visibility=1.01)
```

- [ ] **Step 2: Run tests and verify the expected failures**

Run `python -m pytest tests/test_config.py tests/test_deploy_sync.py -q`. Expected: failure because the field, enum member, and schema sync entry do not exist.

- [ ] **Step 3: Implement the minimal contract**

Add `seated_turn_max_hip_visibility: float = Field(default=0.05, ge=0, le=1)` and `SEATED_TURN = "seated_turn"`. Synchronize both deployment files and document `SEATED_TURN_MAX_HIP_VISIBILITY=0.05` in `.env.example` and README.

```python
seated_turn_max_hip_visibility: float = Field(default=0.05, ge=0, le=1)

class ActionType(str, Enum):
    SEATED_TURN = "seated_turn"
```

- [ ] **Step 4: Run focused tests and commit**

Run `python -m pytest tests/test_config.py tests/test_deploy_sync.py -q` and Ruff on the changed Python files. Commit as `feat: define seated turn classification contract`.

### Task 2: Classify narrow-shoulder, hidden-hip poses as seated turns

**Files:**
- Modify: `app/ml/image_proctor.py`
- Modify: `deploy_split/code/app/ml/image_proctor.py`
- Modify: `scripts/verify_actions_v2.py`
- Test: `tests/test_image_proctor_behaviors.py`
- Test: `tests/test_verify_actions_v2.py`

- [ ] **Step 1: Write failing unit and real-image tests**

Add a landmark-fixture test proving narrow shoulders plus both hips at or below `0.05` returns `SEATED_TURN`, while visible hips retain `TURN_BODY`. Add a real-image test for `turn_body_left_90_01_174519.jpg`, and assert the verifier maps `seated_turn` to `视线偏移` while `turn_body` remains `离开座位`.

```python
self.assertTrue(proctor._is_seated_turn(hidden_left_hip, hidden_right_hip))
self.assertFalse(proctor._is_seated_turn(visible_left_hip, visible_right_hip))
self.assertEqual("视线偏移", ACTION_CATEGORY_MAP["seated_turn"])
self.assertEqual("离开座位", ACTION_CATEGORY_MAP["turn_body"])
```

- [ ] **Step 2: Run tests and verify failures**

Run `python -m pytest tests/test_image_proctor_behaviors.py tests/test_verify_actions_v2.py -q`. Expected: seated-turn assertions fail because the subtype is not emitted or mapped.

- [ ] **Step 3: Implement the minimal classifier**

Read landmarks 23 and 24, store the injected hip visibility limit, and within the existing narrow-shoulder branch emit `SEATED_TURN` only when `max(lh.visibility, rh.visibility) <= limit`; otherwise emit the unchanged `TURN_BODY`. Add only `seated_turn: 视线偏移` to the verifier map and synchronize the deployment source.

```python
def _is_seated_turn(self, left_hip, right_hip):
    return max(left_hip.visibility, right_hip.visibility) <= self.seated_turn_max_hip_visibility

action_type = ActionType.SEATED_TURN if self._is_seated_turn(lh, rh) else ActionType.TURN_BODY
```

- [ ] **Step 4: Run focused tests and the 305/7 image regressions**

Require main `256/305`, gaze-away `54/68`, normal `37/37`, all other categories unchanged, and rear-camera `3/7`.

- [ ] **Step 5: Commit**

Commit source, tests, and regenerated official main reports as `feat: distinguish seated turns from body turns`. Do not replace the fixed-camera baseline reports because their structured results must remain unchanged.

### Task 3: Isolate and conservatively tune downward gaze

**Files:**
- Modify: `app/core/config.py`
- Modify: `app/ml/image_proctor.py`
- Modify: `deploy_split/code/app/core/config.py`
- Modify: `deploy_split/code/app/ml/image_proctor.py`
- Modify: `app/api/v1/proctor.py`
- Modify: `deploy_split/code/app/api/v1/proctor.py`
- Modify: `.env.example`
- Test: `tests/test_config.py`
- Test: `tests/test_face_angle_params.py`

- [ ] **Step 1: Write failing boundary tests**

Specify `_classify_face_direction(pitch, yaw)` with current priority right, left, down, up. Test every boundary, including exact-value normal behavior, injected defaults, and per-request override reset.

```python
self.assertEqual(1, proctor._classify_face_direction(0, proctor.max_right_angle - 0.01))
self.assertEqual(3, proctor._classify_face_direction(0, proctor.max_left_angle + 0.01))
self.assertEqual(2, proctor._classify_face_direction(proctor.max_down_angle - 0.01, 0))
self.assertEqual(4, proctor._classify_face_direction(proctor.max_up_angle + 0.01, 0))
self.assertEqual(0, proctor._classify_face_direction(proctor.max_down_angle, 0))
```

- [ ] **Step 2: Run focused tests and verify failure**

Run `python -m pytest tests/test_config.py tests/test_face_angle_params.py -q`. Expected: failure because the helper does not exist and the default remains `-1`.

- [ ] **Step 3: Implement the pure helper and new default**

Move only the four comparisons from `_get_face_angle()` into the pure helper. Change `Settings.max_down_angle` and `.env.example` from `-1` to `-0.5`; keep the historical `57.3` scale and all other directions unchanged. Synchronize deployment files.

```python
def _classify_face_direction(self, pitch, yaw):
    if yaw < self.max_right_angle:
        return 1
    if yaw > self.max_left_angle:
        return 3
    if pitch < self.max_down_angle:
        return 2
    if pitch > self.max_up_angle:
        return 4
    return 0
```

Update both API parameter descriptions from “默认 -1” to “默认 -0.5”, and include the API files in deployment byte-sync coverage.

- [ ] **Step 4: Run focused tests and both image regressions**

Require final main `261/305`, gaze-away `59/68`, normal `37/37`, other categories unchanged, rear-camera `3/7`, and exactly the five documented new downward-gaze detections relative to Task 2.

- [ ] **Step 5: Commit**

Commit source, tests, configuration example, and regenerated official main reports as `tune: improve downward gaze classification`.

### Task 4: Final consistency and deployment verification

**Files:**
- Verify: `app/`
- Verify: `deploy_split/code/app/`
- Verify: `reports/detection_results.csv`

- [ ] **Step 1: Run complete automated verification**

Run `python -m pytest -q`, `python -m ruff check app tests`, `docker compose config --quiet`, and `docker compose -f deploy_split/docker-compose.yml config --quiet`.

- [ ] **Step 2: Run both manifests into temporary directories**

Require final main category counts `59,13,51,37,33,68` for gaze-away, leave-seat, multi-person, normal, phone, and stretch respectively, and fixed rear-camera `3/7` with zero structured changes from its committed baseline.

- [ ] **Step 3: Check source sync and working tree**

Run byte comparisons for configuration, schema, API, and recognizer files; run `git diff --check`; require a clean feature worktree. The pre-existing untracked August 4 plan in the main worktree remains untouched.
