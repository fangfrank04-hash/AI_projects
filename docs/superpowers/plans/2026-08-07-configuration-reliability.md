# Configuration Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `.env`, process environment variables, validation, and every active recognition threshold use one reliable configuration source without changing default detections.

**Architecture:** Replace the hand-written environment readers with a Pydantic `BaseSettings` model and inject a `Settings` instance into `ImageProctor`. Preserve current runtime constants as defaults, retain per-request face-angle overrides, and mirror the two deployment code trees. Compare structured per-image actions before and after the change on both committed test manifests.

**Tech Stack:** Python 3.10+, pydantic-settings, MediaPipe, pytest/unittest, Ruff, uv.

---

### Task 1: Introduce validated settings and `.env` loading

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `app/core/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Add the standard settings dependency**

Run `uv add pydantic-settings` with the existing root virtual environment active so `pyproject.toml` and `uv.lock` are updated together.

- [ ] **Step 2: Write failing precedence and validation tests**

Create `tests/test_config.py` with tests that construct `Settings(_env_file=temporary_path)`, verify `.env` values load, verify `os.environ` overrides `.env`, and verify invalid `port`, `log_level`, confidence, visibility, pool size, and pose count raise `pydantic.ValidationError`.

- [ ] **Step 3: Run the tests and observe the expected failure**

Run `python -m pytest tests/test_config.py -q`. Expected: failure because current `Settings` does not accept `_env_file`, does not load dotenv files, and does not validate ranges.

- [ ] **Step 4: Implement `BaseSettings` with current runtime defaults**

Use `SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")`. Define typed fields with `Field` bounds, normalize and validate `log_level`, keep path defaults derived from `BASE_DIR`, and instantiate `settings = Settings()`.

- [ ] **Step 5: Run focused tests and commit**

Run `python -m pytest tests/test_config.py -q` and `python -m ruff check app/core/config.py tests/test_config.py`. Commit with `git commit -m "feat: load and validate runtime configuration"`.

### Task 2: Wire every active threshold into `ImageProctor`

**Files:**
- Modify: `app/ml/image_proctor.py`
- Modify: `tests/test_face_angle_params.py`
- Modify: `tests/test_image_proctor_behaviors.py`

- [ ] **Step 1: Write failing injection tests**

Add tests constructing `Settings(_env_file=None, phone_wrist_ear_dist=0.44, phone_arm_angle=26, stretch_arm_angle=139, horizontal_stretch_arm_angle=151, horizontal_stretch_visibility=0.45, horizontal_stretch_arm_length=1.1, horizontal_stretch_wrist_ear_dist=1.7, elbow_stretch_visibility=0.3, elbow_stretch_max_dy=0.4, elbow_stretch_min_reach=0.8, turn_body_shoulder_dist=0.2, visibility_threshold=0.6)` and assert an injected `ImageProctor(config)` exposes exactly those values. Add a face-angle reset test using injected defaults rather than module constants.

- [ ] **Step 2: Run focused tests and observe failure**

Run `python -m pytest tests/test_face_angle_params.py tests/test_image_proctor_behaviors.py -q`. Expected: failure because `ImageProctor` currently takes no config and hard-codes action thresholds.

- [ ] **Step 3: Implement settings injection**

Change `ImageProctor.__init__(config: Settings | None = None)`, store `self._config = config or settings`, initialize all active action and face defaults from it, and make `_apply_face_angles(None)` restore the injected service defaults. Keep `FaceAngleThresholds` and explicit request overrides compatible.

- [ ] **Step 4: Run focused tests and commit**

Run `python -m pytest tests/test_config.py tests/test_face_angle_params.py tests/test_image_proctor_behaviors.py -q` and Ruff on changed files. Commit with `git commit -m "refactor: source proctor thresholds from settings"`.

### Task 3: Synchronize deployment copy and public configuration template

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `deploy_split/code/app/core/config.py`
- Modify: `deploy_split/code/app/ml/image_proctor.py`
- Create: `tests/test_deploy_sync.py`

- [ ] **Step 1: Write a failing source-sync test**

Create a test that compares bytes for `app/core/config.py` against `deploy_split/code/app/core/config.py` and `app/ml/image_proctor.py` against `deploy_split/code/app/ml/image_proctor.py`. Expected initial failure because only the primary app has been changed.

- [ ] **Step 2: Synchronize the deployment files**

Copy the two changed primary source files to their split-deployment counterparts without modifying content.

- [ ] **Step 3: Correct `.env.example` and README**

Replace stale phone and stretch defaults with current runtime values, remove unused `PHONE_WRIST_EAR_Y_DIFF` and `STAND_*`, add every active horizontal/elbow threshold, and document precedence `environment > .env > defaults` plus restart requirements.

- [ ] **Step 4: Run sync and configuration tests and commit**

Run `python -m pytest tests/test_config.py tests/test_deploy_sync.py -q` and Ruff on `app`, `tests`, and the two mirrored files. Commit with `git commit -m "docs: align deployment configuration and defaults"`.

### Task 4: Prove default behavior did not change

**Files:**
- Verify: `assets/test_images/test_answers.csv`
- Verify: `assets/test_images/fixed_rear_45deg/test_answers.csv`
- Verify: `reports/detection_results.csv`
- Verify: `reports/fixed_rear_45deg/detection_results.csv`

- [ ] **Step 1: Run both manifests into temporary report directories**

Run `scripts/verify_actions_v2.py` once with the 305-image manifest and once with the 7-image manifest, writing outside tracked report paths.

- [ ] **Step 2: Compare structured actions row by row**

Compare `image_path` and `actual_action_type` from the temporary CSVs against the two committed baseline CSVs. Require zero changed rows; also require main `245/305`, normal `37/37`, and rear-camera `3/7`.

- [ ] **Step 3: Run complete verification**

Run `python -m pytest -q`, `python -m ruff check app tests`, `docker compose config --quiet`, and `docker compose -f deploy_split/docker-compose.yml config --quiet`.

- [ ] **Step 4: Commit any lock or documentation normalization only if present**

Review `git diff --check` and `git status --short`. If no remaining intended changes exist, do not create an empty commit.
