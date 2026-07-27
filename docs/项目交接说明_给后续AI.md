# AI 监考项目交接说明（给后续 AI / 接手开发者）

> 目的：让接手这个项目的人（或 AI）快速搞清楚——**这是什么项目、代码怎么组织、有哪些脚本怎么用、当前到了什么状态、最近改了什么、还有哪些坑没填**。
> 最近更新：2026-07-20。

---

## 一、项目是什么

一个**基于图片的 AI 考场监控（AI 监考）识别服务**。核心能力：接收一张考生图片，用 MediaPipe 分析人脸角度和身体姿态，判断考生是否有违规动作，返回结构化结果。

**6 大检测类别**：正常考试 / 视线偏移 / 离开座位 / 多人出现 / 打电话 / 伸展胳膊。

**调用方**：Java 后端调用本 Python 服务的 HTTP 接口（传图片，拿检测结果）。

**技术栈**：Python + FastAPI（Web 框架）、MediaPipe（FaceMesh + Pose + FaceDetection 三个模型）、OpenCV、Pydantic。包管理用 `uv`，lint 用 `ruff`，测试用 `pytest`。

---

## 二、代码怎么组织（分层架构）

标准 FastAPI 分层，`app/` 下：

| 目录 | 职责 | 关键文件 |
|------|------|---------|
| `app/api/v1/` | 路由层：只收请求、调 service、返响应，不写业务逻辑 | `proctor.py`（3 个接口） |
| `app/schemas/` | 数据模型：请求/响应体结构，统一响应格式 | `proctor.py`（`ApiResponse`、`ActionType`、`StatusCode`） |
| `app/services/` | 业务编排层：读文件、转格式、调模型、异常处理 | `proctor_service.py` |
| `app/ml/` | 算法层：MediaPipe 识别核心逻辑、阈值 | `image_proctor.py`（**最核心**，600+ 行） |
| `app/core/` | 配置、离线文档页 | `config.py`、`offline_docs.py` |

**统一响应格式**：`{"code": 200, "message": "success", "data": {...}}`。code 复用 HTTP 状态码语义（200 成功 / 400 输入错误 / 404 资源不存在 / 413 文件过大 / 500 服务端错误）。

**3 个接口**（地址稳定，不要乱改）：
- `GET /test`：用内置图片 `assets/test_images/person2.jpg` 做自测
- `GET /ping`：健康检查
- `POST /upload_face`：上传图片识别（Java 线上实际调这个，multipart 传图）

---

## 三、脚本工作流（调阈值 / 测准确率时用）

所有脚本在 `scripts/` 下，项目根目录运行。**这是调优的标准工作流**：

### 1. 拍样本 —— `capture_targeted_samples.py`
用摄像头按提示拍各类动作的样本图，存到 `assets/test_images/` 下。补数据时用。

### 2. 探关键点数值 —— `probe_keypoints_v2.py`
```
uv run python scripts/probe_keypoints_v2.py
```
扫描 `samples_v2/` 下 6 大类子目录，打印每类的关键点特征值（臂角、腕耳距、可见度等）的 min/max/avg 区间，并把带标注的图存到 `samples_v2_annotated/`。**调阈值前先跑它看数据分布。**

### 3. 跑准确率 + 耗时验证 —— `verify_actions_v2.py`（最常用）
```
uv run python scripts/verify_actions_v2.py
```
- 数据源：`assets/test_images/samples_v2/`（当前 180 张，6 大类）
- **自动输出到文件**（不用再从控制台复制粘贴）：
  - `reports/detection_report.md`：总体通过率、各类通过率、P95 耗时、失败样本清单
  - `reports/detection_results.csv`：逐张明细
- 文件名前缀 → 预期类别的映射在脚本顶部的 `CATEGORY_MAP`，改分类口径就改这里。

> ⚠️ 已知小坑：`verify_actions_v2.py` 的 `SAMPLES_DIR` 目前硬编码 `samples_v2`（180 张），`assets/test_images/` 下还有 `targeted_samples` 等未纳入验证。要扩大验证集需改这里。

### 其它脚本
- `curate_targeted_samples.py`：筛选/整理拍摄的样本
- `back_camera.py`：后置摄像头相关（YOLO），当前主链路没用到

### 控制台中文乱码提醒
Windows PowerShell 下脚本的中文输出会乱码（数字/英文正常）。**别依赖控制台看结果，直接读 `reports/` 下的 md/csv 文件。** PowerShell 不支持 `&&`（用 `;`），没有 `tail`/`head`（用 `Select-String`）。

---

## 四、当前状态（截至 2026-07-20）

### 性能：✅ 达标（远超目标）
- P95 响应从约 **597ms 降到约 156~174ms**（目标 <500ms），平均耗时 421ms → ~120ms。
- 关键手段：**MediaPipe 模型只加载一次、跨请求复用**（原来每张图都重建 3 个模型）。见下节。

### 准确率：当前总体 **80%**（目标是从 73% 提上去，已达成）
各类通过率（80% 版本）：
| 类别 | 通过率 |
|------|-------|
| 正常考试 | 100% |
| 视线偏移 | 90% |
| 打电话 | 90% |
| 多人 | 76.67% |
| 离开座位 | 70% |
| 伸胳膊 | 56.67% ⚠️ |

---

## 五、本轮（2026-07 会话）改了什么

### 1. 响应体格式标准化
`{status, msg, data}` → `{code, message, data}`，code 用 HTTP 风格码。涉及 schemas / services / api / docs。

### 2. 性能优化（模型复用）—— `image_proctor.py` + `proctor_service.py`
- `ImageProctor.__init__` 里**一次性创建** `_face_mesh` / `_face_detection` / `_pose` 三个模型，全生命周期复用。
- 加 `threading.Lock`：MediaPipe solution 对象非线程安全，`analyze()` 内用 `with self._lock:` 把单次分析串行化（因为 service 用共享单例）。
- 加 `close()` 释放资源。
- service 层用**模块级单例** `_proctor = ImageProctor()`，跨请求复用。

### 3. 准确率调优（口径对齐 + 阈值实验）
- **分类口径对齐**：业务确认「大幅转头」归**视线偏移**（不是离开座位），改了 `verify_actions_v2.py` 的 `CATEGORY_MAP`。这一步让视线偏移 66%→90%，总体 73%→80%。
- 伸胳膊阈值做了 4 组实验（见下节"已知问题"），最终**回退到总体最优的 80% 版本**。

### 4. 面部角度阈值可传参（接口改造，2026-07-20）
判断视线偏移/转头方向的 4 个角度阈值，做成了**接口可选参数**：
- 默认常量 `DEFAULT_MAX_LEFT/RIGHT/UP/DOWN_ANGLE`（在 `image_proctor.py` 顶部）+ `FaceAngleThresholds` 数据类。
- `analyze(pil_img, face_angles=None)`：在**锁内**临时套用本次阈值，用完自动回默认（不污染共享单例）。
- service 的 `_build_face_angles()`：全不传→None（走默认）；传部分→未传字段补默认。
- `GET /test` 用 Query 参数，`POST /upload_face` 用 Form 字段。
- **不传任何参数 = 行为与改造前完全一致。**
- 详见 `docs/新手向_后台架构说明.md` 的「三点五」节。

参数表：

| 参数名 | 默认 | 含义 |
|--------|-----:|------|
| `max_left_angle` | 6 | 左右角 > 该值 → 向左看 |
| `max_right_angle` | -6 | 左右角 < 该值 → 向右看 |
| `max_up_angle` | 6 | 上下角 > 该值 → 向上看 |
| `max_down_angle` | -1 | 上下角 < 该值 → 向下看 |

---

## 六、已知问题 / 下一步（重要，别踩坑）

### 伸胳膊类精度是硬骨头（56.67%，别用调阈值硬刚）
根因诊断结论：**MediaPipe 对伸直的手臂，手腕关键点的 visibility 天生极低（0.06~0.30）**。做过的 4 组实验证明这是个**精度/召回的死结**：
- 只要放宽阈值把伸胳膊逼到 100%，正常/离座/视线偏移就被"幻觉手腕"大量误报，总体反而掉到 63~70%。
- 实测：visibility 门槛 0.4→0.25→0.05，伸胳膊 56%→90%→100%，但总体 80%→75%→63%。

**结论**：这不是调阈值能解开的，需要**更好的特征**（比如引入手部检测模型、或对低可见度关键点做专门处理），建议作为**专门的下一轮迭代**，而不是继续在阈值上打转。当前 80% 是这套特征体系下的最优平衡点。

### 阈值都在 `image_proctor.__init__` 里
姿势类阈值（`m_fPhone*`、`m_fHorizontalStretch*`、`m_fTurnBody*` 等）都是标定值，改前先跑 `probe_keypoints_v2.py` 看数据、改后必跑 `verify_actions_v2.py` **确认各类没连带退步**（这个习惯多次帮我们及时发现回退）。

### 验证集偏小
只有 180 张（`samples_v2`）。要更可信的准确率，需扩充样本并修 `verify_actions_v2.py` 的 `SAMPLES_DIR`。

---

## 七、常用命令速查

```powershell
# 装依赖
uv sync

# 起服务（开发）
uv run uvicorn app.main:app --reload

# lint
uv run ruff check app tests

# 测试
uv run pytest -q

# 跑准确率验证（结果看 reports/detection_report.md）
uv run python scripts/verify_actions_v2.py

# 看关键点数据分布
uv run python scripts/probe_keypoints_v2.py
```

---

## 八、给后续 AI 的提醒

1. **改 `image_proctor.py` 的阈值后，必跑 `verify_actions_v2.py` 并逐类核对**，别只看总体通过率。
2. **性能已优化，别退回"每次请求 new 一个 ImageProctor"或"每张图重建模型"** —— 那会让 P95 回到近 1 秒。
3. 共享单例 + 锁的设计要保住：任何新的"按请求变化的状态"（如面部角度参数）都应在锁内临时套用、用完复位，不要在共享实例上留残留。
4. 用户是 Python 后台新手，交流用**中文**、讲清楚"为什么"，别堆术语。
