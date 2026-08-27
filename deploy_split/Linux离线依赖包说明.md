# Linux 离线依赖包使用说明（wheels_linux/）

> 这是什么：给**不用 Docker、直接在内网 Linux 服务器上跑 Python** 的场景准备的全部依赖包。
> 如果内网走 Docker 部署（docker-compose 那套），**用不到这个目录**，基础镜像里已含同样依赖。

## 一、适用环境（不满足装不上）

| 项目 | 要求 | 说明 |
|---|---|---|
| 操作系统 | Linux x86_64，glibc ≥ 2.28 | CentOS 8+ / Ubuntu 20.04+ / Debian 10+ 均可；**CentOS 7 不行**（glibc 2.17 太老） |
| Python | 3.12.x（推荐 3.12.9，与镜像一致） | 包是 cp312 编译的，3.10/3.11/3.13 装不上 |

## 二、目录内容

44 个 .whl 文件（共约 323MB），就是 requirements.txt 里全部 62 个依赖中带二进制和纯 Python 的包
（部分带条件标记的包按 Linux 平台只保留对应版本），从 PyPI 官方源按 Linux 平台下载，含 mediapipe、
opencv、jaxlib、scipy 等大包的 Linux 版。

## 三、内网安装（离线，无需联网）

把 `wheels_linux/` 和 `requirements.txt` 一起拷到内网服务器，然后：

```bash
# 方式一：pip（内网服务器有 Python 3.12 + pip）
python3.12 -m venv .venv
source .venv/bin/activate
pip install --no-index --find-links=wheels_linux -r requirements.txt

# 方式二：uv（公司统一用 uv 时）
uv venv --python 3.12
uv pip install --no-index --find-links wheels_linux -r requirements.txt
```

装完后在项目根目录（app/ 所在处）启动：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

系统还需要 OpenCV/MediaPipe 的图形库（Docker 镜像里已装，裸机要手动装）：

```bash
# Debian/Ubuntu
sudo apt-get install -y libgl1 libglib2.0-0
# CentOS/RHEL
sudo yum install -y libGL glib2
```

## 四、常见问题

- **安装报 "not a supported wheel"**：Python 版本不是 3.12，或系统 glibc 太老（用 `ldd --version` 查）
- **启动报 libGL 错误**：没装上面的系统图形库
- **依赖升级后如何重新生成**：在外网机器上改完 pyproject/uv.lock 后运行：
  `uv export --no-dev --no-hashes --format requirements-txt -o requirements.txt`
  再用 requirements.txt 重新下载 Linux wheel（命令见项目 docs，平台参数：manylinux_2_27/2_28/2_17/2014）

## 五、与 Docker 镜像的关系

| 交付物 | 用途 | 什么时候用 |
|---|---|---|
| aiproctor_base_1.1.0.tar | Docker 部署（含 Python+依赖） | **首选**，公司流水线/服务器支持 Docker 时 |
| wheels_linux/ | 裸机 pip 离线安装 | 备用，内网某些机器不让用 Docker 时 |

两者依赖内容一致（同一份 uv.lock 解析），只是打包形式不同。
