# Test Answer Manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reviewed 305-image answer manifest and make the validation script score every image strictly against that manifest.

**Architecture:** Keep answer data in `assets/test_images/test_answers.csv` as the scoring source of truth. Put CSV loading and validation in a small test-support module, use a deterministic one-time builder to create the initial 305 rows, and change `verify_actions_v2.py` to consume validated rows instead of inferring answers at runtime from filenames.

**Tech Stack:** Python 3.10+, standard-library `csv` and `pathlib`, Pillow, `unittest`, existing MediaPipe `ImageProctor`.

---

## File Map

- Create `scripts/answer_manifest.py`: answer-row type, CSV reader, validation, allowed categories.
- Create `scripts/build_test_answers.py`: deterministic initial construction from the two original photo sets.
- Create `assets/test_images/test_answers.csv`: committed, human-readable 305-row answer table.
- Create `tests/test_answer_manifest.py`: manifest validation and 305-image inventory tests.
- Modify `scripts/verify_actions_v2.py`: read the answer table and apply strict category matching.
- Modify `tests/test_verify_actions_v2.py`: strict scoring and report tests.
- Modify `scripts/curate_targeted_samples.py`: stop rejecting the three confirmed turn samples.
- Modify `tests/test_curate_targeted_samples.py`: lock the corrected curation decision.
- Regenerate `reports/detection_results.csv` and `reports/detection_report.md`: new strict baseline.

### Task 1: Add Manifest Loading And Validation

**Files:**
- Create: `scripts/answer_manifest.py`
- Create: `tests/test_answer_manifest.py`

- [ ] **Step 1: Write failing validation tests**

Add tests that create temporary CSV files and prove the loader rejects duplicate paths, unsupported categories, missing files, absolute paths, and parent-directory paths. Include this valid-row test shape:

```python
def test_loads_one_valid_answer_row(self):
    image = self.root / "assets" / "test_images" / "sample.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"jpeg")
    self.write_csv([
        {
            "image_path": "assets/test_images/sample.jpg",
            "source_set": "main",
            "scenario": "normal_front",
            "expected_category": "正常考试",
            "split": "eval",
            "include_in_main": "1",
            "note": "",
        }
    ])

    rows = load_answer_manifest(self.csv_path, self.root)

    self.assertEqual(1, len(rows))
    self.assertEqual("正常考试", rows[0].expected_category)
```

- [ ] **Step 2: Run tests and confirm they fail because the module does not exist**

Run: `.venv\Scripts\python.exe -m unittest tests.test_answer_manifest -v`

Expected: import failure for `scripts.answer_manifest`.

- [ ] **Step 3: Implement the focused manifest module**

Define an immutable `AnswerRow` with these fields:

```python
@dataclass(frozen=True)
class AnswerRow:
    image_path: str
    source_set: str
    scenario: str
    expected_category: str
    split: str
    include_in_main: bool
    note: str
```

Define the exact allowed categories:

```python
ALLOWED_CATEGORIES = {
    "正常考试", "视线偏移", "离开座位", "多人", "打电话", "伸胳膊"
}
```

Implement `load_answer_manifest(csv_path: Path, root_dir: Path) -> list[AnswerRow]`. It must read `utf-8-sig`, require all seven columns, accept only `0` or `1` for `include_in_main`, reject duplicate relative paths, reject absolute paths and `..`, verify each referenced file exists, and include the CSV row number in every `ValueError`.

- [ ] **Step 4: Run the focused tests**

Run: `.venv\Scripts\python.exe -m unittest tests.test_answer_manifest -v`

Expected: all manifest validation tests pass.

- [ ] **Step 5: Commit the isolated manifest loader**

Run:

```powershell
git add scripts/answer_manifest.py tests/test_answer_manifest.py
git commit -m "test: add image answer manifest validation"
```

### Task 2: Build And Verify The 305-Image Answer Table

**Files:**
- Create: `scripts/build_test_answers.py`
- Create: `assets/test_images/test_answers.csv`
- Modify: `tests/test_answer_manifest.py`

- [ ] **Step 1: Write failing inventory and category-count tests**

Add an integration test that loads the real CSV and asserts:

```python
EXPECTED_COUNTS = {
    "正常考试": 37,
    "视线偏移": 68,
    "离开座位": 15,
    "多人": 70,
    "打电话": 35,
    "伸胳膊": 80,
}

rows = load_answer_manifest(ANSWERS_PATH, ROOT_DIR)
main_rows = [row for row in rows if row.include_in_main]
self.assertEqual(305, len(main_rows))
self.assertEqual(EXPECTED_COUNTS, Counter(row.expected_category for row in main_rows))
self.assertFalse(any("annotated" in row.image_path for row in main_rows))
self.assertFalse(any("targeted_samples_clean" in row.image_path for row in main_rows))
```

Also assert that the three `normal_side_guard_002/003/004` rows have expected category `视线偏移`, note `坐着转身`, and `include_in_main=True`.

- [ ] **Step 2: Run the inventory test and confirm the CSV is missing**

Run: `.venv\Scripts\python.exe -m unittest tests.test_answer_manifest -v`

Expected: failure because `assets/test_images/test_answers.csv` does not exist.

- [ ] **Step 3: Implement deterministic initial answer generation**

The builder must scan only `samples_v2` and the 125 image rows in `targeted_samples/samples_manifest.csv`. Apply these exact business rules:

```python
SAMPLES_V2_RULES = {
    "normal_front": "正常考试",
    "normal_side": "正常考试",
    "normal_writing": "视线偏移",
    "face_hidden": "视线偏移",
    "head_turn_large": "视线偏移",
    "phone_look_down": "视线偏移",
    "turn_body_left_90": "视线偏移",
    "turn_body_right_90": "视线偏移",
    "turn_head": "视线偏移",
    "person_gone": "离开座位",
    "stand_up": "离开座位",
    "two_persons": "多人",
    "person_entering": "多人",
    "two_persons_talking": "多人",
    "phone_left": "打电话",
    "phone_right": "打电话",
    "stretch_left": "伸胳膊",
    "stretch_right": "伸胳膊",
    "stretch_both": "伸胳膊",
}
```

For targeted samples, translate the manifest category directly, except `normal_side_guard` shots `2`, `3`, and `4`, which must be overridden to `视线偏移` with note `坐着转身`. Sort output by `image_path`, write `utf-8-sig`, and fail unless there are exactly 305 unique existing images with the expected category counts.

Set `source_set` to `samples_v2` or `targeted_samples`. For `samples_v2`, mark sequence numbers 1-7 as `tune` and 8-10 as `eval`; for targeted samples, copy the existing manifest split. All 305 rows start with `include_in_main=1`.

- [ ] **Step 4: Generate the answer table**

Run: `.venv\Scripts\python.exe scripts\build_test_answers.py`

Expected output:

```text
Wrote 305 answers to assets\test_images\test_answers.csv
正常考试=37 视线偏移=68 离开座位=15 多人=70 打电话=35 伸胳膊=80
```

- [ ] **Step 5: Run manifest tests and inspect the three overrides**

Run: `.venv\Scripts\python.exe -m unittest tests.test_answer_manifest -v`

Run: `Select-String -LiteralPath assets\test_images\test_answers.csv -Pattern 'normal_side_guard_00[234]'`

Expected: tests pass and all three rows show `视线偏移` plus `坐着转身`.

- [ ] **Step 6: Commit the builder and answer table**

Run:

```powershell
git add scripts/build_test_answers.py assets/test_images/test_answers.csv tests/test_answer_manifest.py
git commit -m "data: add strict answers for 305 proctor images"
```

### Task 3: Make Verification Strict And Manifest-Driven

**Files:**
- Modify: `scripts/verify_actions_v2.py`
- Modify: `tests/test_verify_actions_v2.py`

- [ ] **Step 1: Write failing strict-scoring tests**

Replace keyword-based leniency tests with exact business expectations:

```python
def test_gaze_away_does_not_accept_normal(self):
    self.assertFalse(report.is_passed("视线偏移", "正常考试中"))

def test_gaze_away_accepts_gaze_warning(self):
    self.assertTrue(report.is_passed("视线偏移", "警告，视线偏移"))

def test_seated_turn_does_not_accept_leave_seat(self):
    self.assertFalse(report.is_passed("视线偏移", "离开座位(考生转身)"))

def test_normal_rejects_every_warning_category(self):
    for actual in ["视线偏移", "离开座位", "多人", "打电话", "伸展胳膊"]:
        self.assertFalse(report.is_passed("正常考试", actual))
```

Add a collection test proving only manifest rows with `include_in_main=True` are scheduled and duplicate directories are never scanned.

- [ ] **Step 2: Run focused tests and confirm current lenient behavior fails**

Run: `.venv\Scripts\python.exe -m unittest tests.test_verify_actions_v2 -v`

Expected: failures for `normal_writing`/`phone_look_down` leniency and manifest collection.

- [ ] **Step 3: Replace runtime filename guessing with manifest input**

Remove `CATEGORY_MAP`, `get_expected`, and the `expected_keyword is None` branch. Add:

```python
ANSWERS_PATH = ROOT_DIR / "assets" / "test_images" / "test_answers.csv"

def collect_images(answers_path=ANSWERS_PATH):
    rows = load_answer_manifest(Path(answers_path), ROOT_DIR)
    return [row for row in rows if row.include_in_main]
```

Change `run_single` to receive `AnswerRow`, open `ROOT_DIR / answer.image_path`, and store `source_set`, `scenario`, and `expected_category` in the result. Implement strict matching:

```python
EXPECTED_MARKERS = {
    "正常考试": ("正常",),
    "视线偏移": ("视线偏移",),
    "离开座位": ("离开座位",),
    "多人": ("多人",),
    "打电话": ("电话",),
    "伸胳膊": ("伸展",),
}

def is_passed(expected_category, actual):
    return any(marker in actual for marker in EXPECTED_MARKERS[expected_category])
```

The `视线偏移` markers must not include standalone `转头` or `转身` because those words can appear inside a wrong `离开座位` result; accepting them would hide the exact category error being measured.

- [ ] **Step 4: Add normal-exam false-positive reporting**

In `build_summary`, add `normal_false_positives`: the number of rows whose expected category is `正常考试` and `passed` is false. Add that count and rate prominently before the overall pass rate in the Markdown report. Include the answer-manifest path and the warning that tune/eval frames are same-session captures.

- [ ] **Step 5: Run focused verification tests**

Run: `.venv\Scripts\python.exe -m unittest tests.test_verify_actions_v2 -v`

Expected: all strict scoring, collection, summary, and report tests pass.

- [ ] **Step 6: Commit strict verification**

Run:

```powershell
git add scripts/verify_actions_v2.py tests/test_verify_actions_v2.py
git commit -m "test: score proctor images against strict answers"
```

### Task 4: Correct The Old Clean-Subset Decision

**Files:**
- Modify: `scripts/curate_targeted_samples.py`
- Modify: `tests/test_curate_targeted_samples.py`

- [ ] **Step 1: Change the existing test to require keeping the three turn images**

```python
def test_keeps_confirmed_seated_turn_samples(self):
    for shot_index in ("2", "3", "4"):
        row = {
            "code": "normal_side_guard",
            "shot_index": shot_index,
            "filename": f"normal_side_guard_00{shot_index}.jpg",
        }
        self.assertEqual("keep", curate.classify_row(row))
```

- [ ] **Step 2: Run the curation test and confirm it fails**

Run: `.venv\Scripts\python.exe -m unittest tests.test_curate_targeted_samples -v`

Expected: failure because shots 2, 3, and 4 are currently in `MANUAL_REJECTS`.

- [ ] **Step 3: Remove only those three tuples from `MANUAL_REJECTS`**

Keep the existing stretch-image curation decisions unchanged. Do not delete or regenerate raw photos in this task.

- [ ] **Step 4: Run curation and manifest tests**

Run: `.venv\Scripts\python.exe -m unittest tests.test_curate_targeted_samples tests.test_answer_manifest -v`

Expected: all tests pass; the three samples remain in the strict answer table as `视线偏移`.

- [ ] **Step 5: Commit the curation correction**

Run:

```powershell
git add scripts/curate_targeted_samples.py tests/test_curate_targeted_samples.py
git commit -m "data: keep confirmed seated-turn samples"
```

### Task 5: Generate And Check The New Strict Baseline

**Files:**
- Modify: `reports/detection_results.csv`
- Modify: `reports/detection_report.md`

- [ ] **Step 1: Run all focused answer and report tests**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_answer_manifest tests.test_verify_actions_v2 tests.test_curate_targeted_samples -v
```

Expected: all tests pass with zero failures.

- [ ] **Step 2: Run the full 305-image verification**

Run: `.venv\Scripts\python.exe scripts\verify_actions_v2.py`

Expected: exactly 305 images are processed and both report files are regenerated. The strict score may be lower than the historical 83.61%; that is expected and must not be “fixed” by relaxing answers.

- [ ] **Step 3: Check required report invariants**

Verify the report shows all six categories with these sample counts:

```text
正常考试 37
视线偏移 68
离开座位 15
多人 70
打电话 35
伸胳膊 80
```

Verify the normal false-positive count is visible, no row has expected category `未知`, and the CSV contains exactly 305 result rows plus one header row.

- [ ] **Step 4: Run the broader test suite and lint only touched Python files**

Run:

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\ruff.exe check scripts/answer_manifest.py scripts/build_test_answers.py scripts/verify_actions_v2.py scripts/curate_targeted_samples.py tests/test_answer_manifest.py tests/test_verify_actions_v2.py tests/test_curate_targeted_samples.py
```

Expected: test suite and lint both exit successfully. Existing unrelated working-tree changes must remain untouched.

- [ ] **Step 5: Commit the strict baseline report**

Run:

```powershell
git add reports/detection_results.csv reports/detection_report.md
git commit -m "test: record strict 305-image baseline"
```

## Completion Check

Before moving to recognition-rule optimization, compare the implementation against every acceptance criterion in `docs/superpowers/specs/2026-08-03-test-answer-manifest-design.md`. Report the strict per-category results and normal false positives to the user in plain Chinese. Do not tune thresholds in the same change set.
