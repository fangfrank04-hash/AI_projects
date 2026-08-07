# AiProctor 智能监考服务

基于 MediaPipe FaceMesh + Pose 的 AI 监考服务，检测考生的人脸朝向、打电话、伸展胳膊、站立、转身等违规动作。

## 快速开始

### 环境要求

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)（包管理工具）

### 安装

```bash
# 1. 安装依赖（uv 会自动创建 .venv 虚拟环境）
uv sync

# 2. 复制配置模板（可选，不复制则用默认值）
cp .env.example .env
```

### 运行

```bash
# 方式一：直接运行
uv run python -m app.main

# 方式二：用 uvicorn（支持热重载）
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

服务启动后访问 http://localhost:8000/docs 查看 API 文档。

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/ping` | 健康检查 |
| GET | `/test` | 用内置测试图片测试人脸识别 |
| POST | `/upload_face` | 上传图片识别监考动作 |

所有业务接口统一返回 `{code, message, data}` 格式（`code=200` 表示成功，非 200 为业务错误，code 复用 HTTP 状态码语义）。
`data` 为结构化检测结果，字段见 `app/schemas/proctor.py` 的 `DetectionData`。

```json
{ "code": 200, "message": "识别成功", "data": { "warning": false, "action_type": "normal", "action_label": "正常考试中", "warning_count": 0, "person_count": 1 } }
```

### 上传图片示例

```bash
curl -X POST http://localhost:8000/upload_face \
  -F "file=@your_photo.jpg"
```

## 项目结构

```
AiProctor0623/
├── app/                    应用主包
│   ├── main.py             FastAPI 入口
│   ├── api/v1/proctor.py   路由层（接收请求）
│   ├── schemas/proctor.py  数据模型（定义响应格式）
│   ├── services/           业务编排层（协调 api 和 ml）
│   ├── core/               基础设施（config 配置 / logging 日志 / exceptions 异常）
│   └── ml/                 机器学习核心代码
│       ├── image_proctor.py    图片监考（核心逻辑，~570行）
│       ├── front_camera.py     前置摄像头实时监考
│       └── Toolkit.py          工具函数（写中文文字）
├── assets/                 静态资源
│   ├── fonts/             字体文件
│   └── test_images/       测试图片
├── models/                 模型文件
│   ├── face_landmarker.task
│   └── weights/yolo11n.pt
├── scripts/                调试和工具脚本
├── tests/                  测试
├── .env.example            配置模板
├── pyproject.toml          依赖声明（唯一来源）
├── uv.lock                 依赖版本锁定（必须提交）
└── Dockerfile              容器构建
```

## 配置说明

实际参与识别的检测阈值都可以在 `.env` 文件中调整，不用改代码。配置优先级为：
系统环境变量（含 Docker `environment`）> 项目根目录 `.env` > 代码默认值。类型或范围错误时
服务会在启动阶段明确报错，不会带着错误配置继续运行。修改配置后必须重启服务，完整字段见
[`.env.example`](.env.example)。其中坐姿转身会同时检查双肩距离和左右髋关键点可见度，
对应 `TURN_BODY_SHOULDER_DIST` 与 `SEATED_TURN_MAX_HIP_VISIBILITY`。

## 新手向文档

不熟悉后台分层结构的同学，先看 [`docs/新手向_后台架构说明.md`](docs/新手向_后台架构说明.md)，
用「饭店」比喻讲清每层职责、请求全链路、以及如何自己动手验收。

## Docker 部署

```bash
docker build -t aiproctor .
docker run -p 8000:8000 aiproctor
```
