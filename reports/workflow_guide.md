# AI 监考样本采集 → 验证 → 调优 完整流程

## 流程总览

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  ① 拍照     │ ──▶ │  ② 探测关键点     │ ──▶ │  ③ AI 标定阈值    │
│  capture    │     │  probe_keypoints  │     │  改 image_proctor │
└─────────────┘     └──────────────────┘     └──────────────────┘
                                                      │
                                                      ▼
┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  ④ 再拍照   │ ◀── │  ③ AI 改代码     │ ◀── │  ⑤ 验证准确率     │
│  (补漏)     │     │  (修阈值/规则)   │     │  verify_actions   │
└─────────────┘     └──────────────────┘     └──────────────────┘
```

---

## 涉及的脚本

| 脚本 | 作用 | 输入 | 输出 | 状态 |
|------|------|------|------|------|
| `scripts/capture_targeted_samples.py` | 拍照 | 摄像头 | `targeted_samples/{类别}/` | ✅ 在用 |
| `scripts/probe_keypoints_v2.py` | 扫描照片，打印指标区间 | `samples_v2/` | 终端打印 + 标注图 | ⚠️ 需更新 |
| `scripts/verify_actions_v2.py` | 验证检测准确率 | `samples_v2/` | `reports/detection_report.md` | ⚠️ 需更新 |

### 已废弃的脚本

| 脚本 | 原因 |
|------|------|
| `scripts/capture_samples.py` | 最早版，14张太粗糙 |
| `scripts/capture_multi_person.py` | 被 capture_targeted --plan multi 替代 |
| `scripts/capture_single_person.py` | 被 capture_targeted --plan single 替代 |
| `scripts/probe_keypoints.py` | v1，扫的是废弃的 samples/ |
| `scripts/verify_actions.py` | v1，扫的是废弃的 samples/ |

---

## 涉及的数据目录

| 目录 | 来源 | 数量 | 作用 |
|------|------|------|------|
| `assets/test_images/samples/` | 最早版 | 14张 | ❌ 扔 |
| `assets/test_images/samples_v2/` | 7/3 旧脚本拍 | 180张 | ✅ 保留（基础数据） |
| `assets/test_images/targeted_samples/` | 7/8+7/17 新脚本拍 | 120张 | ✅ 保留（针对性补充） |

---

## 步骤详解

### ① 拍照

```bash
# 只拍单人（伸胳膊/正常/打电话，~80张）
python scripts/capture_targeted_samples.py

# 只拍多人（半入镜/背后经过，40张）
python scripts/capture_targeted_samples.py --plan multi

# 全部拍（单人+多人，~120张）
python scripts/capture_targeted_samples.py --plan focused
```

- 空格拍照，n 跳过，b 回退，r 重拍，q 退出
- 照片保存到 `assets/test_images/targeted_samples/{类别}/`
- 同时生成 `samples_manifest.csv`（记录 tune/eval 分组）

---

### ② 探测关键点（probe_keypoints_v2.py）

```bash
python scripts/probe_keypoints_v2.py
```

**做什么**：用 MediaPipe Pose 扫描所有照片，计算每张图的动作特征值：
- `shoulder_dist`（双肩距，判断转身）
- `shoulder_mid_y`（肩部Y坐标，判断站立）
- `left_arm_angle / right_arm_angle`（臂角，判断伸展）
- `min_wrist_ear_dist`（腕耳距，判断打电话）
- `nose_offset_x`（鼻子偏移，判断转头）

**输出**：
1. 终端打印每张图的关键指标值
2. 保存带骨架标注的图片到 `samples_v2_annotated/`
3. 最后按大类汇总 min/max/avg 区间

**然后怎么做**：把终端最后一截的汇总表复制给 AI，AI 根据各指标区间来标定新阈值。

---

### ③ AI 改 image_proctor.py

根据 probe 输出的指标区间，AI 修改 `app/ml/image_proctor.py` 里的阈值和判断逻辑。

例如：
- 伸胳膊阈值从 140° 降到 120°（因为数据里最小臂角是 141°）
- 打电话加臂角排除（≤30° 才算打电话，否则可能是伸胳膊）
- 转身90 用 shoulder_dist < 0.25

---

### ④ 验证准确率（verify_actions_v2.py）

```bash
python scripts/verify_actions_v2.py
```

**做什么**：用 `ImageProctor` 跑所有照片，对比实际检测结果和预期结果。

**输出**：
- `reports/detection_report.md` — Markdown 报告（每类通过率/失败清单）
- `reports/detection_results.csv` — CSV 明细

**然后怎么做**：把 `detection_report.md` 或失败样本列表给 AI，AI 分析哪些类误判多、调整规则。

---

## ⚠️ 当前问题：probe 和 verify 只扫旧数据

`probe_keypoints_v2.py` 第 32 行：
```python
SAMPLES_DIR = os.path.join(ROOT_DIR, "assets", "test_images", "samples_v2")
```

`verify_actions_v2.py` 第 29 行：
```python
SAMPLES_DIR = ROOT_DIR / "assets" / "test_images" / "samples_v2"
```

都是硬编码 `samples_v2/`，**不认识 `targeted_samples/`**。

新拍的 120 张 targeted_samples 没有被包含在探测和验证中。

---

## 建议的下一步

1. **更新 probe_keypoints_v2.py**：让它同时扫 `samples_v2/` 和 `targeted_samples/`
2. **更新 verify_actions_v2.py**：同样支持两套数据，并补上 targeted_samples 的新子类映射（person_enter_left_edge 等）
3. **跑一遍全量探测**：用 300 张照片重新标定阈值
4. **跑一遍全量验证**：用 300 张照片重新算准确率

---

## 旧流程 vs 新流程

| | 旧流程 (7/3) | 新流程 (现在) |
|---|---|---|
| 拍照脚本 | capture_single/multi_person.py | capture_targeted_samples.py |
| 照片目录 | samples_v2/ | samples_v2/ + targeted_samples/ |
| 关键点探测 | probe_keypoints_v2.py | 同脚本，但需更新数据源 |
| 验证准确率 | verify_actions_v2.py | 同脚本，但需更新数据源 |
| 修改代码 | 改 image_proctor.py | 改 image_proctor.py |
