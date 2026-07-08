# ImageProctor.py 代码改动计划

> 日期：2026-07-01
> 改动目标：增加 Pose 检测 5 个动作（转头/转身/站立/伸展/打电话）
> 改动原则：最小侵入，保留现有逻辑，可回退

---

## 一、联网搜索最新实践要点

基于 2026 年 1 月、3 月发布的 MediaPipe Pose 实战文章：

1. **`with` 语句管理 Pose 生命周期**：避免批量处理图片时内存泄漏
2. **`static_image_mode=True`**：单帧图片必须开启，否则追踪逻辑失效
3. **`model_complexity=1`**：Full 模型，平衡精度与速度（小方测试用的就是这个）
4. **`min_detection_confidence=0.3`**：小方测试用的 0.3，比默认 0.5 更宽松，避免侧身漏检
5. **Face Mesh 和 Pose 必须分别初始化、分别 process 调用**：不能合并
6. **Python 版本注意**：MediaPipe 对 3.11+ 支持不稳定，小方用 3.12 但已跑通测试

---

## 二、结合真实数据的修正

基于小方 14 张样本照片的 probe_keypoints.py 输出：

| 原计划 | 真实数据修正 |
|--------|------------|
| 站立用膝盖 y 坐标 | ❌ 髋/膝 visibility 全部 < 0.01，不可信。改用 torso_height > 1.20 + shoulder_dist > 0.48 |
| 打电话阈值 0.08（业界推导） | ❌ 太严。真实数据 0.20-0.23，定 0.35 |
| 转身 45 度单独检测 | ❌ shoulder_dist=0.36，与转头(0.36)重叠。归入转头处理 |
| 转身 90 度用躯干角 | ❌ 躯干角全部 < 3°，无区分度。改用 shoulder_dist < 0.25 |
| 伸展胳膊只用臂角 > 150° | ❌ normal_side 的右臂角 171°，会误报。加条件：腕.y < 肩.y |

---

## 三、改动前的安全措施

### 3.1 备份原文件
```
AiProctor/Logic/ImageProctor.py          ← 原文件（不动）
AiProctor/Logic/ImageProctor.py.bak      ← 备份（改动前创建）
```

### 3.2 回退方案
- 如果改动后 14 张样本测试失败，直接 `cp ImageProctor.py.bak ImageProctor.py` 回退
- 新增的方法都是独立的，删除即可恢复原状

---

## 四、代码改动点清单（共 6 处）

### 改动 1：新增 import（文件头部）
**位置**：第 1-8 行附近
**内容**：新增 `mediapipe as mp` 的 Pose 相关导入（mp 已导入，无需新增）
**风险**：无

### 改动 2：__init__ 新增 Pose 配置常量
**位置**：第 13-24 行 `__init__` 方法内
**内容**：新增 5 个动作的阈值常量
```python
# Pose 动作检测阈值（基于 14 张真实样本标定）
self.m_fPhoneWristEarDist = 0.35      # 打电话：腕耳距 < 0.35
self.m_fPhoneWristEarYDiff = 0.25     # 打电话：腕耳y差 < 0.25
self.m_fStandTorsoHeight = 1.20       # 站立：躯干高度 > 1.20
self.m_fStandShoulderDist = 0.48      # 站立：双肩距 > 0.48（辅助）
self.m_fStretchArmAngle = 150         # 伸展：臂角 > 150°
self.m_fTurnBodyShoulderDist = 0.25   # 转身90：双肩距 < 0.25
self.m_fVisibilityThreshold = 0.5     # visibility 过滤阈值
```
**风险**：低，只是新增常量，不影响现有逻辑

### 改动 3：__ProcessImage 新增 Pose 处理分支
**位置**：第 105-163 行 `__ProcessImage` 方法内
**内容**：在现有 Face Mesh 处理之后，新增 Pose 处理调用
```python
# 现有 Face Mesh 逻辑保持不变（第 107-157 行）

# ===== 新增：Pose 动作检测 =====
stPoseSolution = mp.solutions.pose
with stPoseSolution.Pose(
    static_image_mode=True,
    model_complexity=1,
    min_detection_confidence=0.3,
) as stPose:
    stImageRGB = cv2.cvtColor(stImage, cv2.COLOR_BGR2RGB)  # 复用现有变量
    stPoseResult = stPose.process(stImageRGB)

    if stPoseResult.pose_landmarks:
        self.__CheckPoseActions(stPoseResult.pose_landmarks.landmark)
# ===== 新增结束 =====

# 现有的 __Checkindependence 调用保持不变
```
**风险**：中，核心改动点。需要注意变量名冲突（stImageRGB 已在 Face Mesh 部分定义）

### 改动 4：新增 __CheckPoseActions 方法
**位置**：第 214 行后（`__CheckDirection` 方法之后）
**内容**：新增整个方法，约 60 行
```python
def __CheckPoseActions(self, in_stLandmarks):
    """检测 4 个新动作：打电话/伸展/站立/转身90（转头由现有 solvePnP 处理）"""
    # 提取关键点（带 visibility 过滤）
    # 检测优先级：打电话 → 伸展 → 站立 → 转身90
    # 命中任一动作则设置 m_listText 并返回
    # 都没命中则不修改 m_listText（让现有逻辑继续判断转头）
```
**风险**：低，纯新增方法，不改现有方法

### 改动 5：新增辅助方法 __IsVisible / __Distance / __Angle
**位置**：`__CheckPoseActions` 之前
**内容**：3 个小工具方法
```python
def __IsVisible(self, in_stPoint):
    """判断关键点是否可见（visibility > 阈值）"""
    return in_stPoint.visibility > self.m_fVisibilityThreshold

def __Distance(self, a, b):
    """计算两点归一化距离"""
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5

def __Angle3(self, a, b, c):
    """计算三点夹角（b是顶点），返回角度"""
    # 向量夹角公式
```
**风险**：无，纯新增

### 改动 6：检测优先级逻辑
**位置**：`__CheckPoseActions` 内部
**内容**：
1. 先判打电话（最具体）→ 命中则 return
2. 再判伸展胳膊 → 命中则 return
3. 再判站立 → 命中则 return
4. 再判转身 90 度 → 命中则 return
5. 都没命中 → 不修改 m_listText，让现有 __CheckDirection 继续判转头
**风险**：低，优先级逻辑在单一方法内

---

## 五、不改动的内容（明确边界）

| 现有内容 | 是否改动 | 原因 |
|---------|---------|------|
| `__GetFaceAngle`（165-214行） | ❌ 不动 | 转头逻辑保留，solvePnP 仍可用 |
| `__Checkindependence`（216-239行） | ❌ 不动 | 多人/离开检测保留 |
| `__CheckDirection`（241-263行） | ❌ 不动 | 现有防抖逻辑保留 |
| `Start` / `StartFolder` / `GetImageFaceAngle` 等公共方法 | ❌ 不动 | API 接口不变 |
| `m_listText` 输出格式 | ❌ 不动 | 复用现有 `[("文字", (R,G,B))]` 格式 |
| `__ResetState` | ❌ 不动 | 状态重置逻辑不变 |

---

## 六、验证计划

### 6.1 单元验证（改完后立即跑）
对小方 14 张样本照片逐张调用 `GetImageFaceAngle`，预期结果：

| 图片 | 预期检测动作 |
|------|-----------|
| normal_front | 正常（不触发任何动作） |
| normal_side | 正常 |
| turn_head_left | 转头（现有 solvePnP） |
| turn_head_right | 转头（现有 solvePnP） |
| turn_body_left_45 | 转头（归入转头） |
| turn_body_right_45 | 转头（归入转头） |
| turn_body_left_90 | **转身**（新增 Pose） |
| turn_body_right_90 | **转身**（新增 Pose） |
| stand_up | **站立**（新增 Pose） |
| stretch_left | **伸展胳膊**（新增 Pose） |
| stretch_right | **伸展胳膊**（新增 Pose） |
| stretch_both | **伸展胳膊**（新增 Pose） |
| phone_call_left | **打电话**（新增 Pose） |
| phone_call_right | **打电话**（新增 Pose） |

### 6.2 回归验证
- 用原有的 `test_images/person2.jpg` 跑一遍，确保现有功能不报错
- 检查 `m_listText` 输出格式是否与原来一致

### 6.3 性能验证
- 单张图片处理时间应 < 500ms（Face Mesh ~200ms + Pose ~200ms）

---

## 七、改动文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `AiProctor/Logic/ImageProctor.py` | 备份 | 改动前先复制为 `.bak` |
| `AiProctor/Logic/ImageProctor.py` | 修改 | 6 处改动，新增约 100 行 |
| `verify_actions.py` | 新建 | 验证脚本，跑 14 张样本 |

---

## 八、执行顺序

1. ✅ 备份 `ImageProctor.py` → `ImageProctor.py.bak`
2. ✅ 改动 1-2：import + 常量（低风险）
3. ✅ 改动 5：辅助方法（低风险）
4. ✅ 改动 4：`__CheckPoseActions` 主体（中风险）
5. ✅ 改动 3：`__ProcessImage` 调用 Pose（中风险）
6. ✅ 改动 6：优先级逻辑（已在改动 4 内）
7. ✅ 新建 `verify_actions.py` 验证脚本
8. ✅ 小方跑验证脚本，贴结果给我
9. ✅ 如有问题，调试或回退

---

## 九、风险与应对

| 风险 | 概率 | 应对 |
|------|------|------|
| Pose 检测失败（侧身 90 度） | 中 | 已验证 14 张全部检测成功 |
| 变量名冲突（stImageRGB） | 低 | 复用现有变量，不重新定义 |
| 性能下降（双模型串行） | 低 | 单帧 400ms 可接受 |
| 现有转头逻辑误判 | 低 | 新动作优先级高于转头，命中即 return |
| visibility 过滤太严 | 低 | 小方数据肩部 visibility 0.8-0.99，0.5 阈值安全 |
