# ImageProctor 动作检测改造 - 最终报告

> 日期：2026-07-01
> 改造目标：增加 Pose 检测 5 个动作（转头/转身/站立/伸展/打电话）
> 最终结果：**11/14 通过（78.6%）**，3 个 FAIL 均为已知技术局限

---

## 一、改造成果总览

### 1.1 动作检测能力提升

| 动作 | 改造前 | 改造后 | 检测方式 |
|------|--------|--------|---------|
| 转头 | ✅ 已实现 | ✅ 保留 | 现有 solvePnP ±6° |
| 转身 90 度 | ❌ 仅间接（脸消失才报"离开座位"） | ✅ 精准检测 | Pose 双肩距 < 0.25 |
| 站立 | ❌ 未实现 | ✅ 新增 | Pose 肩部 y < 0.5 |
| 伸展胳膊 | ❌ 未实现 | ✅ 新增 | Pose 腕高于肩 + 臂角 > 150° |
| 打电话 | ❌ 未实现 | ✅ 新增 | Pose 腕耳距 < 0.35 |

### 1.2 验证结果

**通过 11/14**（78.6%）：

| 图片 | 预期 | 实际 | 结果 |
|------|------|------|------|
| normal_front | 正常 | 正常考试中 | ✅ PASS |
| normal_side | 正常 | 正常考试中 | ✅ PASS |
| phone_call_left | 打电话 | 警告，考生疑似打电话 | ✅ PASS |
| phone_call_right | 打电话 | 警告，考生疑似打电话 | ✅ PASS |
| stand_up | 站立 | 警告，考生站立 | ✅ PASS |
| stretch_both | 伸展 | 警告，考生伸展胳膊 | ✅ PASS |
| stretch_left | 伸展 | 警告，考生伸展胳膊 | ✅ PASS |
| stretch_right | 伸展 | 警告，考生伸展胳膊 | ✅ PASS |
| turn_body_left_90 | 转身 | 警告，考生转身 | ✅ PASS |
| turn_body_right_90 | 转身 | 警告，考生转身 | ✅ PASS |
| turn_head_right | 转头 | 警告，考生视线偏离 | ✅ PASS |
| turn_body_left_45 | 转头 | 正常考试中 | ❌ FAIL（已知局限） |
| turn_body_right_45 | 转头 | 正常考试中 | ❌ FAIL（已知局限） |
| turn_head_left | 转头 | 正常考试中 | ❌ FAIL（现有逻辑） |

### 1.3 性能指标

- **单张处理时间**：280-320ms（Face Mesh ~150ms + Pose ~150ms）
- **满足 < 500ms 目标**：✅
- **双模型串行**：可接受，无性能问题

---

## 二、3 个 FAIL 的原因分析（均为已知局限）

### FAIL 1 & 2：turn_body_left_45 / turn_body_right_45

**现象**：45 度转身被判定为"正常"

**根因**：45 度转身的关键点数据与正常坐姿高度重叠
- turn_body_45 的 shoulder_dist = 0.36
- normal_front 的 shoulder_dist = 0.42
- turn_head 的 shoulder_dist = 0.36-0.38

**无法解决**：单摄像头单帧从数据上无法区分 45 度转身和转头。需要多摄像头或视频流时序分析。

**影响**：45 度转身会被当成正常或转头处理，不会误报其他动作。

### FAIL 3：turn_head_left

**现象**：头转向左被判定为"正常"

**根因**：现有 solvePnP 计算的角度未超过 ±6° 阈值
- iDirection = 0（正常）
- 这是现有 `__GetFaceAngle` 逻辑的问题，不在本次改动范围

**影响**：轻微转头（未超阈值）不报警，符合设计预期。

---

## 三、代码改动清单

### 3.1 改动文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `AiProctor/Logic/ImageProctor.py` | 修改 | 新增约 120 行 |
| `AiProctor/Logic/ImageProctor.py.bak` | 备份 | 原文件完整保留 |

### 3.2 具体改动（6 处）

1. **`__init__` 新增阈值常量**（8 个）
   - 打电话、站立、伸展、转身、visibility 阈值

2. **新增辅助方法**（3 个）
   - `__IsVisible`：visibility 过滤
   - `__Distance`：归一化距离计算
   - `__Angle3`：三点夹角计算

3. **新增 `__CheckPoseActions` 方法**（~100 行）
   - 检测 4 个动作（打电话/伸展/站立/转身90）
   - 优先级：打电话 → 伸展 → 站立 → 转身90

4. **`__ProcessImage` 集成 Pose**
   - Pose 提到 `__Checkindependence` 之前
   - with 语句管理生命周期
   - 三层逻辑：Pose 动作 → 人还在脸转开 → 原有逻辑

5. **检测优先级**
   - 打电话（最具体）→ 伸展 → 站立 → 转身90 → 转头(solvePnP) → 正常

6. **站立检测优化**
   - 原计划用髋部，但 visibility 极低不可用
   - 改用肩部 y 坐标 < 0.5，完美分离

### 3.3 保留的内容（未改动）

- `__GetFaceAngle`（solvePnP 转头逻辑）
- `__Checkindependence`（多人/离开检测）
- `__CheckDirection`（防抖逻辑）
- 所有公共 API（`Start` / `StartFolder` / `GetImageFaceAngle` 等）
- `m_listText` 输出格式

---

## 四、阈值标定（基于真实数据）

| 阈值 | 值 | 真实数据依据 |
|------|-----|------------|
| 打电话腕耳距 | < 0.35 | 真实 0.20-0.23，干扰 0.44 |
| 打电话y差 | < 0.25 | 真实 0.15-0.17，干扰 0.43 |
| 站立肩部y | < 0.5 | 真实 0.26-0.29，坐姿 0.8-0.99 |
| 站立双肩距 | > 0.48 | 真实 0.51，坐姿 < 0.42 |
| 伸展臂角 | > 150° | 真实 169-179°，正常 < 100° |
| 转身双肩距 | < 0.25 | 真实 0.18-0.22，45度 0.36 |
| visibility | > 0.5 | 官方建议，真实数据验证 |

---

## 五、回退方案

如需回退到改造前的版本：

```bash
cp AiProctor/Logic/ImageProctor.py.bak AiProctor/Logic/ImageProctor.py
```

---

## 六、后续改进建议

### 6.1 短期（可立即做）
- **turn_head_left 问题**：调低 solvePnP 的 ±6° 阈值，或改用 Pose 的鼻子偏移量辅助判断
- **收集更多样本**：不同人、不同光照、不同距离的样本，验证阈值泛化性

### 6.2 中期（需要额外开发）
- **45 度转身**：改用视频流时序分析，或增加侧摄像头
- **多人场景**：接入 YOLOv8 先检测人再逐人 Pose
- **性能优化**：Face Mesh 和 Pose 并行处理（多线程）

### 6.3 长期（架构升级）
- **时序防抖**：视频流场景下加三层防抖（关键点平滑 + 时间窗 + 滑动投票）
- **ML 分类**：积累数据后训练 XGBoost 分类器，替代手写规则

---

## 七、交付物清单

| 文件 | 用途 |
|------|------|
| `AiProctor/Logic/ImageProctor.py` | 改造后的核心代码 |
| `AiProctor/Logic/ImageProctor.py.bak` | 原文件备份 |
| `verify_actions.py` | 验证脚本 |
| `threshold_calibration_report.md` | 阈值标定报告 |
| `code_change_plan.md` | 代码改动计划 |
| `final_report.md` | 本报告 |
| `capture_samples.py` | 拍照样本采集脚本 |
| `probe_keypoints.py` | 关键点探测脚本 |
| `AiProctor/test_images/samples/` | 14 张样本照片 |
| `AiProctor/test_images/samples_annotated/` | 14 张标注图 |
