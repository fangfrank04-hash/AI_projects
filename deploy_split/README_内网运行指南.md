# 内网运行指南（README）

> 本文档是内网部署/运行的总入口：**依赖到底装什么 → 场景 A（Windows 开发机）怎么跑 → 场景 B（Linux 服务器）怎么跑 → 常见问题**。
> 全程**不需要外网、不需要 uv、不需要 poetry**，只用到 Python 自带的 pip（或 Docker）。

---

## 一、requirements.txt 里的依赖都是必须的吗？

**是的，一个都不能少。** 但它们分两类，了解结构你就放心了：

### 8 个直接依赖（项目代码直接用到）

| 依赖 | 干什么用 |
|---|---|
| fastapi | Web 框架（提供 HTTP 接口） |
| uvicorn | 运行 fastapi 的服务器 |
| python-multipart | 支持文件上传（/upload_face 接口必需） |
| pydantic-settings | 读取 .env 配置 |
| mediapipe | **核心**：人脸/姿态识别模型 |
| opencv-python | 图片解码、像素处理 |
| numpy | 数值计算（图片就是数组） |
| pillow | 图片格式转换 |

### 其余全部是"依赖的依赖"（间接依赖，删不掉）

它们是被上面 8 个自动拉进来的，**少一个 pip 就装不上或运行就报错**。大头都来自 mediapipe：

```
mediapipe（人脸识别核心）
├── jax + jaxlib + scipy + ml-dtypes     ← Google 推理计算库（77MB 大包在这）
├── matplotlib + contourpy + fonttools…  ← 画图库（mediapipe 内部用）
├── opencv-contrib-python                ← mediapipe 自己要求装 contrib 版
├── protobuf / flatbuffers / sentencepiece…  ← 模型文件解析
└── sounddevice / cffi…                  ← mediapipe 声音相关（虽用不到但强制依赖）

fastapi → pydantic → pydantic-core → typing-extensions…（数据校验链）
uvicorn → click / h11…（命令行/网络协议）
```

> 简单说：**requirements.txt 是 pip 解析完整依赖树后的结果，45 个包缺一不可**。
> 之前确认过没有冗余（没用的 YOLO 全套已删除）。

---

## 二、场景 A：内网 Windows 开发机（改代码、调试、跑测试）

**需要准备**：`wheels_win/` 文件夹 + `python-3.12.9-amd64.exe` + 项目代码（含 `requirements.txt`）

### 第 1 步：装 Python（每台机器只需一次）

双击 `python-3.12.9-amd64.exe`，安装界面**务必勾选 "Add python.exe to PATH"**，然后一路 Next。

验证：打开 cmd 输入 `python --version`，显示 `Python 3.12.9` 即成功。

### 第 2 步：装依赖（每次更新代码包后，依赖没变可跳过）

cmd 进入项目根目录（`app/` 文件夹所在的目录）：

```bat
python -m venv .venv
.venv\Scripts\activate
pip install --no-index --find-links deploy_split\wheels_win -r requirements.txt
```

装完会显示 `Successfully installed ...`（44 个包）。

### 第 3 步：跑测试验证环境

```bat
python -m pytest tests/ -q
```

期望最后一行类似 `56 passed`（数字可能随版本变多）。

### 第 4 步：启动服务调试

```bat
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

浏览器打开 `http://localhost:8000/docs` 能看到接口文档即成功。改完代码 Ctrl+C 停止再重启。

> 日常开发只需要记住两条：`cd 项目目录` → `.venv\Scripts\activate` → 干活。
>（venv 建一次就行，以后只是激活它）

---

## 三、场景 B：内网 Linux 服务器（正式部署跑生产）

### 方式 B1：Docker 部署（**首选**，公司流水线方式）

**需要准备**：`aiproctor_base_1.1.0.tar` + `code/` + `docker-compose.yml`（+ 可选 `.env`）

```bash
cd /opt/aiproctor    # 你的部署目录，按实际改

# 1. 首次才需要：加载基础镜像（1.4GB，加载一次以后都在）
docker load -i aiproctor_base_1.1.0.tar

# 2. 启动（compose 会自动把 code/ 挂载进容器）
docker compose up -d

# 3. 验证
curl http://127.0.0.1:8000/ping     # 期望 {"pong":true,...}
docker compose logs -f              # 看日志，Ctrl+C 退出
```

**以后更新代码**（最常用的操作）：

```bash
# 用新的 code/ 覆盖旧的，然后：
docker compose restart
```

不用碰镜像、不用装任何依赖，30 秒完成更新。

### 方式 B2：Linux 裸机 pip 部署（备用，机器不让用 Docker 时）

**需要准备**：`wheels_linux/` + `requirements.txt` + 项目代码

```bash
# 0. 系统图形库（OpenCV 需要，装一次就行；Debian/Ubuntu 为例）
sudo apt-get install -y libgl1 libglib2.0-0

# 1. 建虚拟环境并离线装依赖（服务器需有 Python 3.12）
python3.12 -m venv .venv
source .venv/bin/activate
pip install --no-index --find-links wheels_linux -r requirements.txt

# 2. 启动（--workers 2 = 开 2 个进程，一般设为 CPU 核数的一半到全部）
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

后台常驻运行建议用 systemd 或 supervisor 托管（参考《高并发部署指南.md》）。

> 裸机要求：Linux x86_64 且 glibc ≥ 2.28（CentOS 8+/Ubuntu 20.04+；CentOS 7 不行）。

---

## 四、常见问题（FAQ）

| 报错/疑问 | 原因和解决 |
|---|---|
| `No matching distribution found` | 装依赖时没加 `--no-index --find-links`，或没激活 venv |
| `not a supported wheel` | Python 不是 3.12（用 `python --version` 确认），必须 3.12.x |
| Linux 装依赖提示 glibc 相关错误 | 系统太老（CentOS 7），换新系统或走 Docker |
| 启动报 `libGL.so.1: cannot open` | Linux 裸机没装系统图形库（见 B2 第 0 步） |
| `pip` 找不到 | 没激活虚拟环境（`.venv\Scripts\activate` 或 `source .venv/bin/activate`） |
| 内网有 poetry.lock / uv.lock 要用吗 | 不用。离线安装只认 `requirements.txt` + wheels 文件夹，lock 文件是外网开发工具的产物 |
| 改了代码要重装依赖吗 | 不用。依赖只在 requirements.txt 变化时才重装；平时只重启服务 |
| 怎么确认线上跑的是新代码 | 启动日志第一行有版本号（当前 1.2.0）；或 `curl /ping` 看模型池状态 |

---

## 五、交付物清单速查

| 文件/文件夹 | 给谁用 | 何时用 |
|---|---|---|
| `code/` | 所有场景 | 业务代码+模型，更新最频繁 |
| `python-3.12.9-amd64.exe` | Windows 机器 | 装机时一次 |
| `wheels_win/` | Windows 开发机 | 建 venv 时一次 |
| `wheels_linux/` | Linux 裸机 | 建 venv 时一次 |
| `aiproctor_base_1.1.0.tar` | Linux + Docker | `docker load` 一次 |
| `docker-compose.yml` | Linux + Docker | 启动/更新时 |
| `requirements.txt` | 所有 pip 场景 | 装依赖时 |

更细的分场景说明见同目录：《Windows离线依赖包说明.md》《Linux离线依赖包说明.md》《内网部署步骤_分离模式.md》《高并发部署指南.md》。
