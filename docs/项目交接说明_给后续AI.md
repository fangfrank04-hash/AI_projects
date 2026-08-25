# AI 监考项目交接说明（给后续 AI / 接手开发者）

> 目的：让接手这个项目的人（或 AI）快速搞清楚——**这是什么项目、代码怎么组织、有哪些脚本怎么用、当前到了什么状态、最近改了什么、还有哪些坑没填**。
> 最近更新：2026-07-31（本版 1.1.0：准确率 83.61%、并发改造、专业化升级、仅分离版交付）。

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
- 数据源：默认扫 `samples_v2/` + `targeted_samples/` 两套共 **305 张**（6 大类）
- **自动输出到文件**（不用再从控制台复制粘贴）：
  - `reports/detection_report.md`：总体通过率、各类通过率、P95 耗时、失败样本清单
  - `reports/detection_results.csv`：逐张明细
- 文件名前缀 → 预期类别的映射在脚本顶部的 `CATEGORY_MAP`，改分类口径就改这里。
- 可用 `--samples-dir` 参数指定其他目录。

### 其它脚本
- `curate_targeted_samples.py`：筛选/整理拍摄的样本
- （原 `back_camera.py` 后置摄像头 YOLO 调试脚本已随 YOLO 依赖整体移除而删除）

### 控制台中文乱码提醒
Windows PowerShell 下脚本的中文输出会乱码（数字/英文正常）。**别依赖控制台看结果，直接读 `reports/` 下的 md/csv 文件。** PowerShell 不支持 `&&`（用 `;`），没有 `tail`/`head`（用 `Select-String`）。

---

## 四、当前状态（截至 2026-07-30，版本 1.1.0）

### 性能：✅ 达标
- 单张 P95 约 **250ms**（目标 <500ms）。
- 关键手段：**MediaPipe 模型只加载一次、跨请求复用**（原来每张图都重建 3 个模型）。

### 并发：✅ 已改造（支持高并发同步调用）
- 场景：80~120 台电脑每 5~10 秒截图，Java **同步调用**（组长 07-30 确认），峰值约 24 张/秒。
- 手段：**模型池（进程内并行）+ uvicorn workers（多进程）+ 多机负载均衡**。压测：改造前 4.37 QPS → 后 9.6（单进程翻倍），workers=2 比 1 再提升 51%。
- 详见 `deploy_split/高并发部署指南.md`。

### 准确率：当前总体 **83.61%**（305 张验证集，从 73% 提升）
各类通过率：
| 类别 | 通过率 |
|------|-------|
| 正常考试 | 92.5% |
| 视线偏移 | 90% |
| 打电话 | 94.29% |
| 伸胳膊 | 85%（肘部特征改造后）|
| 多人 | 72.86%（PoseLandmarker 兜底后）|
| 离开座位 | 70% |

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
| `max_down_angle` | -0.5 | 上下角 < 该值 → 向下看 |

### 5. （2026-07-30）验证集扩容：180 → 305 张
`verify_actions_v2.py` 默认扫 `samples_v2` + `targeted_samples` 两套数据源，`CATEGORY_MAP` 补了 `person_enter`/`person_pass_behind` 前缀。只改测试脚本，不影响业务代码/镜像。

### 6. （2026-07-30）伸胳膊肘部特征改造：56.67% → 85%
旧规则靠手腕（visibility 极低不可靠）。新增 `_is_elbow_stretch_arm`：用“肘齐肩/高于肩”（elbow_dy ≤ 0.5）判定（肘比腕可靠）。数据：伸胳膊 elbow_dy avg -0.05，其他类≥ 0.69，分界干净。零副作用（其他类不退步）。

### 7. （2026-07-30）多人 PoseLandmarker 兜底：62.86% → 72.86%
人脸检测数不出背影/侧脸的第二人。新增 MediaPipe Tasks **PoseLandmarker**（模型 `models/pose_landmarker_lite.task`）数“身体”兜底，置信度 0.2（`multi_person_pose_confidence`）；加**间距护栏** `_poses_are_separated`（两体肩中点水平距 ≥ 0.15 才算多人，排除单人转头被误拆）。模型用 `model_asset_buffer`（自读字节）加载——Windows 下传路径会报错。

### 8. （2026-07-30）告警标签格式优化
`turn_head` 标签→“视线偏移(考生转头)”，`turn_body` →“离开座位(考生转身)”，消除与大类名撞名的歧义（只改 action_label，不影响验证）。

### 9. （2026-07-30）高并发模型池改造
拆掉全局锁，新增 `ProctorPool`（`queue.Queue` 借还 N 个 `ImageProctor` 实例，真并行）；service 用 `run_in_threadpool` 把 CPU 密集的 analyze 丢线程池，不阻塞 async 事件循环。`PROCTOR_POOL_SIZE` 环境变量可调（默认 2）。

### 10. （2026-07-30）PEP 8 全量重构 + 镜像交付
- 907 处匈牙利命名→snake_case（m_fXxx/stXxx/in_stXxx），方法名 PascalCase→snake_case，Toolkit.py→toolkit.py。verify 逐类指标与改前一致。
- Python 统一 3.12.9（与内网一致，`.python-version` pin）。
- 交付模式：**仅分离版 `deploy_split/`**（环境镜像+挂载代码，改代码只拷 code/ 重启）；整包版 deploy/ 已于 07-31 退役删除（用户确认长期频繁改代码，分离版更合适）。

### 11. （2026-07-31）专业化升级（对标 FastAPI 官方模板/uv 官方指南）
- **代码**：删无用依赖 logic；main.py 加 lifespan（停机时释放模型池）；新增请求日志中间件 `app/core/middleware.py`；`/ping` 返回 `pool_ready`/`pool_size`（真健康检查）。
- **镜像**（两个 Dockerfile 重写）：多阶段构建 + slim 基座（**tar 2.22GB→1.32GB，瘦 40%**）；钉死 uv 版本 0.10.12（不用 latest，保构建可复现）；`PYTHONUNBUFFERED=1`（日志实时）；`UV_COMPILE_BYTECODE=1`（启动提速）；**非 root 运行**（appuser，安全基线）。
- 容器实测：healthy、appuser、新 ping、多人/正常识别全对；tar load 校验通过。

---

## 六、已知问题 / 下一步（重要，别踩坑）

### 伸胳膊早期是硬骨头（已部分解决：56.67% → 85%）
旧结论：MediaPipe 对伸直手臂的**手腕** visibility 极低（0.06~0.30），靠手腕调阈值是死结。
**07-30 突破口**：改用更可靠的**肘部**特征（`_is_elbow_stretch_arm`，“肘齐肩”），从 56.67% 提到 85% 且零副作用。剩下的 15% 是肘也被遮挡的极端样本，需手部检测模型才能再进一步。

### 剩余提升空间（下一轮可做）
- **多人 72.86%**：背影/半入镜仍有漏，要再提升需人体检测（YOLO/更强模型），但会增加镜像体积和延迟，需权衡。
- **离开座位 70%**：转身/转头的边界案例。

### 阈值都在 `image_proctor.__init__` 里
姿势类阈值（`phone_*`、`horizontal_stretch_*`、`elbow_stretch_*`、`turn_body_*` 等）都是标定值，改前先跑 `probe_keypoints_v2.py` 看数据、改后必跑 `verify_actions_v2.py` **确认各类没连带退步**（这个习惯多次帮我们及时发现回退）。

> 2026-07-30：全项目已完成匈牙利命名→PEP 8 重构（m_fXxx/stXxx/in_stXxx 全部改为 snake_case，
> 方法名 PascalCase→snake_case，Toolkit.py→toolkit.py），907 处改名后 verify 逐类指标与改前完全一致。

### 验证集已扩到 305 张
已含 `samples_v2`(180) + `targeted_samples`(125)。要更可信可继续拍片扩充，`verify_actions_v2.py` 支持 `--samples-dir` 多目录。

---

## 七、常用命令速查

```powershell
# 装依赖
uv sync

# 起服务（开发，单进程）
uv run uvicorn app.main:app --reload

# 起服务（接近生产，多进程）
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2

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
3. **并发靠 `ProctorPool` 模型池 + `run_in_threadpool`**：任何新的"按请求变化的状态"（如面部角度参数）都应在单次 analyze 内临时套用、用完复位，不要在实例上留残留。
4. **高并发靠多进程（uvicorn --workers）+ 多机**，不是无限加大模型池（单进程受 CPU 核数限制有天花板）。
5. 用户是 Python 后台新手，交流用**中文**、讲清楚"为什么"、别堆术语。
