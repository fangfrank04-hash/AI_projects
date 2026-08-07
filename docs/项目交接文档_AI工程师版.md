# AiProctor0623 项目交接文档（AI 工程师版）

> 交接对象：接手本项目的 AI 工程师 / AI 助手
> 文档日期：2026-07-31 ｜ 项目版本：1.1.0
> 原则：本文所有数据来自实际运行记录，不编造；无法核实的内容标记为 **[待确认]**。
> 本文档取代 `docs/项目交接说明_给后续AI.md` 中的概要信息，后者可作为速览版保留。

---

## 1. 项目目标、使用场景、业务边界

### 目标
基于单张图片的 AI 考场监控（AI 监考）识别服务：接收考生电脑摄像头截图，用 MediaPipe 分析人脸角度与身体姿态，判断是否违规，同步返回结构化结果。

### 实际使用场景
- 调用方：Java 后端（组长为资深 Java 后台）。
- 规模：80~120 台考生电脑，每台每 5~10 秒截图一张，经 Java 调用本服务。
- 峰值估算：120 台 ÷ 5 秒 ≈ **24 张/秒**（推算值，真实峰值 **[待确认]**，需 Java 侧给准数）。
- 调用模式：**同步 HTTP**（Java 发一张等一张返回），组长 2026-07-30 明确确认"先同步的吧，应该能满足要求"。
- 部署环境：内网 Linux 服务器（多台 4 核 16G，具体台数/配置 **[待确认]**），**完全离线**（无外网、无私服），Docker + docker-compose 部署。

### 业务边界（明确不做的）
- 只做单张静态图识别，不做视频流/跨帧时序分析。
- 不做人脸身份识别（不认人，只测姿态/角度/人数）。
- 不存储图片，不落库；结果仅同步返回（无回调/MQ）。
- 检测 6 大业务类：正常考试 / 视线偏移 / 离开座位 / 多人 / 打电话 / 伸胳膊。

---

## 2. 已完成的功能与改动原因（时间线）

| 时间 | 改动 | 原因 |
|---|---|---|
| 07-02 | 工程重构：分层架构（api/services/ml/schemas/core）、uv 包管理、ruff+pytest | 原代码全堆在 main.py，无法维护 |
| 07-03~17 | 拍摄验证集：samples_v2(180张) + targeted_samples(125张) | 建立可量化的准确率基线 |
| 07-20 | 响应体标准化 `{code,message,data}`（HTTP 风格码） | 对齐后端规范，Java 统一按 code 处理 |
| 07-20 | 模型只加载一次+跨请求复用（原每张图重建 3 个模型） | P95 从 ~1s 压到 ~250ms |
| 07-20 | 大幅转头归"视线偏移"口径（改 verify 的 CATEGORY_MAP） | 业务确认口径，视线偏移 66%→90% |
| 07-20 | 面部角度 4 阈值做成接口可选参数 | 组长需求：Java 不传用默认、传了用传的 |
| 07-30 | 验证集扩容 180→305（verify 默认扫双数据源） | 数字更可信；发现伸胳膊真实水平 80% 而非 56% |
| 07-30 | 伸胳膊肘部特征 `_is_elbow_stretch_arm`：56.67%→85% | 手腕 visibility 极低不可靠，改用肘（数据分界干净） |
| 07-30 | 多人 PoseLandmarker 兜底+间距护栏：62.86%→72.86% | 人脸检测抓不到背影/侧脸的第二人；护栏防单人误拆 |
| 07-30 | 标签优化：turn_head→"视线偏移(考生转头)"、turn_body→"离开座位(考生转身)" | 消除细类与大类撞名歧义（用户提出） |
| 07-30 | PEP 8 全量重构（907 处，映射表+词边界正则） | 去匈牙利命名；verify 逐类指标与改前完全一致（零行为漂移） |
| 07-30 | Python 统一 3.12.9（.python-version pin + 镜像 FROM） | 与内网版本一致（用户强调"必须和内网一致"） |
| 07-30 | 高并发改造：ProctorPool 模型池 + run_in_threadpool | 原全局锁串行仅 ~4.4 QPS，扛不住 24 峰值 |
| 07-31 | lifespan 优雅停机、/ping 池状态、请求日志中间件 | 生产标配：停机释放资源、探活可信、请求可追溯 |
| 07-31 | Dockerfile 重写：多阶段+slim、钉 uv 0.10.12、PYTHONUNBUFFERED、UV_COMPILE_BYTECODE、非 root | 对标 FastAPI 官方模板/uv 官方指南；tar 2.22GB→1.32GB |
| 07-31 | 删无用依赖 `logic`；交付只保留分离版（deploy/ 整包版删除） | logic 从未被 import；用户确认长期频繁改代码，分离版更合适 |

---

## 3. 关键技术决策、阈值来源、模型与数据集

### 3.1 关键决策及依据
| 决策 | 依据 |
|---|---|
| 同步接口（不上 MQ/回调） | 单张 ~150ms 属快接口；组长确认；离线内网多一个中间件多一份负担 |
| 并发 = 模型池(进程内) × workers(多进程) × 多机 | 压测证明单进程受 CPU 核数限制有天花板（池 2→4 QPS 仅 9.6→10.4）；MediaPipe 推理释放 GIL，多线程+独立实例可真并行 |
| PoseLandmarker 而非 YOLO 做多人兜底 | YOLO 需 torch(+~1GB 镜像/延迟风险)；PoseLandmarker 仅 5.5MB 且 mediapipe 自带 |
| 分离版部署（镜像/代码分开+挂载） | 沿用团队既有习惯；改代码只拷 13MB code/ 重启，不动 2GB 镜像 |
| 镜像自包含（离线可跑） | 内网零联网；运行命令直接用 /app/.venv/bin/python，不经 uv |

### 3.2 阈值全表（定义于 `app/ml/image_proctor.py` 的 `ImageProctor.__init__`）
所有阈值基于 305 张真实样本用 probe 脚本采数标定，非拍脑袋：

| 阈值 | 值 | 含义/来源 |
|---|---|---|
| max_left/right/up/down_angle | 6 / -6 / 6 / -1 | 头部 yaw/pitch 判向（可被接口参数覆盖，常量 DEFAULT_MAX_*_ANGLE） |
| phone_wrist_ear_dist | 0.55 | 打电话：腕耳归一化距 |
| phone_arm_angle | 30 | 打电话：臂角<30°（弯臂贴头） |
| stretch_arm_angle | 140 | 腕高于肩规则的臂角下限（代码内联另有 >120 判断） |
| horizontal_stretch_arm_angle / _visibility / _arm_length / _wrist_ear_dist | 155 / 0.4 / 1.05 / 1.6 | 水平伸展规则（4 组实验后的最优平衡点，详见第 6 节"坑"） |
| elbow_stretch_visibility / _max_dy / _min_reach | 0.25 / 0.5 / 0.7 | 肘部兜底：伸胳膊 elbow_dy avg -0.05，其他类最小 ≥0.69，0.5 在分界空隙内 |
| turn_body_shoulder_dist | 0.25 | 转身：双肩归一化距塌缩 |
| visibility_threshold | 0.5 | 通用关键点可见度门槛 |
| multi_person_pose_confidence | 0.2 | PoseLandmarker 置信度（0.3 检出少，0.1 正常图 20% 误判，0.2 为甜点） |
| multi_person_min_separation | 0.15 | 两身体肩中点水平距护栏（误拆 ≤0.08，真多人 ≥0.19） |
| proctor_pool_size | 2（环境变量 PROCTOR_POOL_SIZE） | 4 核机 workers=2×pool=2 匹配核数 |

### 3.3 模型
| 模型 | 文件/来源 | 用途 |
|---|---|---|
| MediaPipe FaceMesh (solutions) | mediapipe==0.10.20 内置 | 数脸、solvePnP 头部角度 |
| MediaPipe FaceDetection (solutions) | 同上 | 多人兜底第一层 |
| MediaPipe Pose (solutions) | 同上 | 姿态动作（打电话/伸胳膊/转身） |
| PoseLandmarker (Tasks API) | `models/pose_landmarker_lite.task`（5.5MB，Google 官方 CDN 下载） | 多人兜底第二层（数"身体"） |
| yolo11n.pt | `models/weights/yolo11n.pt` | **未使用**（ultralytics 已卸载，.dockerignore 已排除） |

### 3.4 数据集（不进镜像，仅本地验证用）
| 目录 | 张数 | 说明 |
|---|---|---|
| `assets/test_images/samples_v2/` | 180 | 07-03 拍，6 大类子目录 |
| `assets/test_images/targeted_samples/` | 125 | 07-08/17 拍：多人40/正常20/打电话15/伸胳膊50 |
| 文件名前缀→预期类别映射 | — | `scripts/verify_actions_v2.py` 的 CATEGORY_MAP |

---

## 4. 已运行的命令、测试、压测与结论

### 4.1 常用命令（全部实际验证过）
```powershell
uv sync                                        # 装依赖（Python 3.12.9，.python-version 已 pin）
uv run ruff check app tests                    # lint（app 全过；scripts 有 10 条历史遗留见 5.3）
uv run pytest -q                               # 23 个测试
uv run python scripts/verify_actions_v2.py     # 准确率验证（305 张，报告写 reports/）
uv run python scripts/probe_keypoints_v2.py    # 关键点特征采数（调阈值前必跑）
uv run python scripts/load_test.py --url http://127.0.0.1:8000 --concurrency 24 --total 120   # 并发压测
docker build -t aiproctor-base:1.1.0 -f Dockerfile.base .   # 环境镜像（需联网，仅本机）
docker save -o deploy_split/aiproctor_base_1.1.0.tar aiproctor-base:1.1.0
```

### 4.2 测试与验证结果（最终状态）
| 项 | 结果 |
|---|---|
| pytest | **23/23 通过**（含面部角度参数、行为回归、service 单测） |
| ruff（app/） | 全过 |
| 准确率（305 张） | **总体 83.61%**：伸胳膊 85 / 多人 72.86 / 打电话 94.29 / 正常 92.5 / 视线偏移 90 / 离座 70 |
| 单张延迟 | avg ~150ms，P95 ~253ms（本机容器实测） |
| 容器冒烟（分离版 compose） | healthy、运行身份 appuser、/ping 含池状态、多人图→multi_person、正常图→normal |
| tar 完整性 | docker load 回读校验通过 |

### 4.3 压测记录（本机 Docker/WSL，仅趋势参考，内网真机会更高）
| 配置 | QPS | P95 延迟 | 结论 |
|---|---|---|---|
| 改造前（单实例+全局锁） | 4.37 | 9.8s | 扛不住，会雪崩 |
| 模型池=2, workers=1 | 5.87 | 4.4s | 池生效 |
| 模型池=2, workers=2 | 8.85~9.60 | 2.8~4.5s | workers +51% |
| 模型池=4, workers=1 | 10.36 | 2.5s | 单进程见顶（核数限制） |

**容量结论**：4 核内网机预估单机 ~15 QPS（workers=2×pool=2）；**2 台 + 负载均衡 ≈ 30 QPS**，可扛 24 峰值并容错。**上线前必须在内网真机用 load_test.py 实测定台数**。

---

## 5. 当前未提交改动、部署方式、已知问题与风险

### 5.1 Git 状态（截至 2026-07-31，**大量改动未提交**）
- 最后一次 commit：`5af6e57 chore: consolidate scripts into app modules...`（07-20 之前）。
- **07-20 以来的全部改动均未提交**，包括：修改 19 个文件（app 全部核心代码、pyproject、uv.lock、两份 docs、verify 脚本、测试）+ 新增 8 项（.dockerignore、.python-version、Dockerfile.base、app/core/middleware.py、deploy_split/、docker-compose.yml、models/pose_landmarker_lite.task、scripts/load_test.py）。
- **建议接手后第一件事：分批提交**（如：功能改动 / 部署文件 / 文档 三笔），避免继续裸奔。
- 注意：`deploy_split/aiproctor_base_1.1.0.tar`（1.32GB）**不应进 git**，提交前加入 .gitignore **[待确认：团队 git 大文件策略]**。

### 5.2 部署方式（唯一交付：`deploy_split/`，1.37GB）
```
deploy_split/
├── aiproctor_base_1.1.0.tar     环境镜像（Python3.12.9+依赖，多阶段构建，非root）
├── code/                        业务代码+资源+模型（约13MB，改代码只动这里）
├── docker-compose.yml           已配 workers=2 + PROCTOR_POOL_SIZE=2 + healthcheck
├── 内网部署步骤_分离模式.md       部署3条命令 + Java对接参数表
└── 高并发部署指南.md             多机/负载均衡/调优速查
```
内网流程：拷文件夹 → `docker load -i *.tar` → `docker compose up -d` → curl /ping 验证。**全程零联网**。
代码更新流程：替换 code/ → `docker compose restart`（依赖变了才需重建镜像）。

### 5.3 已知问题
| 问题 | 影响 | 说明 |
|---|---|---|
| 多人 72.86% | 背影/半入镜仍漏 | 人脸+姿态双兜底已到轻量方案上限 |
| 离开座位 70% | 转身/转头边界案例误报为视线偏移 | 未专项攻坚 |
| 伸胳膊剩 15% | 肘也被遮挡的极端样本 | 需手部检测模型 |
| scripts/ 有 10 条 ruff 历史遗留 | 无功能影响 | back_camera/probe_keypoints_v2/capture/curate 的 import 排序、未用变量等；ruff 配置已 exclude scripts |
| tests/test_api.py 依赖本机防火墙放行 | 仅开发机 | TestClient 走回环 socket；新 Python 解释器需 Windows 防火墙入站放行（曾致 pytest 卡死，已修） |
| 开发机 Docker Desktop/WSL 频繁崩溃 | 仅开发机 | 已配 .wslconfig（内存10G/swap8G）缓解；构建失败重试通常即恢复 |

### 5.4 风险
- **内网真实 QPS 未实测**（本机数据仅趋势），上线前必须真机压测。
- 部署机具体核数/台数/Docker 版本 **[待确认]**——影响 workers 与台数决策。
- 内网 Java 客户端超时设置 **[待确认]**——建议 10~30s，防极端排队被误判超时。
- 验证集 305 张均为同一环境/人员拍摄，光线/机位多样性有限；真实考场准确率可能有偏差。

---

## 6. 后续优化优先级 + 明确不要重复踩的坑

### 优先级（高→低）
1. **P1 内网真机压测**：用 scripts/load_test.py 实测单机 QPS，确定 workers 数与机器台数（半天工作量）。
2. **P2 多人识别**：引入人体检测（如 YOLO/更强 pose 模型）。代价：torch 依赖镜像 +1~2GB、延迟增加，需与收益权衡。
3. **P3 伸胳膊剩余 15%**：MediaPipe Hands 手部检测辅助（同样有延迟代价）。
4. **P4 离开座位**：转身/转头边界案例专项（先 probe 采数再定方案）。
5. **P5 样本扩充**：不同光线/机位/人员的样本，verify 支持 --samples-dir 多目录。

### ⚠️ 不要重复踩的坑（每条都付出过代价）
1. **伸胳膊不要靠调手腕相关阈值硬刚**：手腕 visibility 天生 0.06~0.30，4 组实验证明放宽必误伤其他类（总体 80%→63%）。已用肘部特征解决大头，剩余需新特征。
2. **改任何阈值后必跑 verify 并逐类核对**，不要只看总体通过率——多次靠这习惯抓住"单类暴涨、其他类崩盘"。
3. **不要退回"每请求 new ImageProctor / 每张图重建模型"**：P95 会回到 ~1 秒。
4. **提升并发不要无脑加大模型池**：单进程受核数天花板（实测池 2→4 仅 +8%），要加 workers/机器。
5. **分离版不要把整个 /app 挂载覆盖**：会盖掉镜像内 /app/.venv（Python 环境），必须按 app/assets/models 三个子目录挂。
6. **MediaPipe Tasks 在 Windows 加载 .task 模型不要传路径**（会错误拼接 site-packages 前缀报错），用 `model_asset_buffer` 读字节，代码已如此实现，别改回去。
7. **Dockerfile 不要用 `uv:latest`**：已钉 0.10.12，latest 漂移会破坏构建可复现性。
8. **本机构建失败先重试**：WSL/BuildKit 偶发 EOF 崩溃，缓存在，重试通常直接成功；连续失败再查（参考 docker 代理配置：Docker Desktop 需手动配 Manual proxy 指向本机代理端口，"自动检测系统代理"只在启动时生效）。
9. **压测脚本对照实验要控变量**：测 A 配置时停掉 B 容器，避免抢 CPU 污染数据。

---

## 7. 关键文件路径与参数速查

### 代码（app/，会进镜像）
| 路径 | 职责 |
|---|---|
| `app/main.py` | 入口：lifespan（停机释放池）、中间件/路由注册 |
| `app/api/v1/proctor.py` | 3 接口：GET /test、GET /ping、POST /upload_face（4 个可选角度参数） |
| `app/services/proctor_service.py` | 业务编排：ProctorPool 单例、run_in_threadpool、pool_status/shutdown |
| `app/ml/image_proctor.py` | **核心算法**（~650行）：全部阈值、检测规则、ProctorPool 类 |
| `app/ml/toolkit.py` / `front_camera.py` | 归档辅助（主链路不用） |
| `app/schemas/proctor.py` | ApiResponse/ActionType(8种)/StatusCode/PingResponse |
| `app/core/config.py` | 全部可配项（环境变量优先），含 PROCTOR_POOL_SIZE、multi_person_* |
| `app/core/middleware.py` | 请求日志中间件 |
| `app/core/exceptions.py` / `logging.py` / `offline_docs.py` | 异常/日志/离线 Swagger |

### 工程与部署
| 路径 | 说明 |
|---|---|
| `Dockerfile` | 整包版（多阶段+slim+非root）；tar 已退役但文件保留可随时重建 |
| `Dockerfile.base` | 分离版环境镜像（同上，不含代码） |
| `.dockerignore` | 排除测试样本/文档/venv 等（保 person2.jpg/字体/swagger/task模型） |
| `docker-compose.yml`（根目录） | 整包版启动参考 |
| `deploy_split/` | **唯一交付物**（见 5.2） |
| `pyproject.toml` / `uv.lock` / `.python-version` | 依赖与 Python 3.12.9 锁定 |

### 脚本与测试（不进镜像）
| 路径 | 用途 |
|---|---|
| `scripts/verify_actions_v2.py` | 准确率验证（默认双数据源 305 张，输出 reports/detection_report.md+csv） |
| `scripts/probe_keypoints_v2.py` | 关键点特征采数（调阈值前跑） |
| `scripts/load_test.py` | 并发压测（QPS/P95/P99） |
| `scripts/capture_targeted_samples.py` | 拍样本（--plan single/multi/focused） |
| `tests/`（7 文件 23 用例） | api 结构/行为回归/角度参数/脚本单测 |
| `reports/detection_report.md` | 最新准确率报告（每次 verify 覆盖） |

### API 契约（Java 对接）
- `POST /upload_face`：multipart，字段 `file`；可选 Form：max_left_angle(6)/max_right_angle(-6)/max_up_angle(6)/max_down_angle(-0.5)
- 响应：`{"code":200,"message":"识别成功","data":{"warning":bool,"action_type":str,"action_label":str,"warning_count":int,"person_count":int}}`
- action_type 8 种 → 6 大类归并：视线偏移=gaze_away+turn_head；离开座位=leave_seat+turn_body；其余一对一
- `GET /ping`：`{"pong":true,...,"pool_ready":bool,"pool_size":int}`（探活用）
- 离线 API 文档：服务地址 + `/docs`

---

## 8. 脱敏声明

- 本项目**无任何 API Key、账号密码、token**（纯本地推理，无外部服务调用）。
- 文档与代码中不含内网真实 IP/域名（部署文档以 `<服务器IP>` 占位）。
- 开发机个人路径、代理端口等本机环境信息不影响项目运行，未写入交付物；deploy_split 交付内容已核查无隐私信息。
- 样本图片（assets/test_images/）为项目成员自拍的测试素材，**不进镜像**；如对外分发代码仓库需评估是否移除 **[待确认：肖像授权范围]**。

---

## 附：接手第一天建议动作清单

1. `uv sync` → `uv run pytest -q`（应 23 passed）→ `uv run python scripts/verify_actions_v2.py`（应 83.61%）——确认环境健康。
2. 阅读 `app/ml/image_proctor.py`（核心算法全在这）+ 本文档第 3.2 阈值表。
3. 处理 5.1 的未提交改动（分批 commit）。
4. 推进 P1（内网真机压测），拿到真实容量数据。
