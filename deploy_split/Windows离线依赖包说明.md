# Windows 离线依赖包使用说明（wheels_win/）

> 这是什么：给你**内网 Windows 开发/调试机**准备的完整离线运行环境——不用外网、不用 Docker，
> 在内网 Windows 电脑上把项目跑起来（改代码、跑测试、本地起服务调试都靠它）。

## 一、目录内容

| 内容 | 大小 | 说明 |
|---|---|---|
| `wheels_win/`（44 个 .whl） | 约 264MB | 全部依赖的 Windows x64 版（含 mediapipe、opencv、jaxlib 等二进制包） |
| `python-3.12.9-amd64.exe` | 约 26MB | Python 官方安装包（内网没外网装不了 Python，必须带上） |
| `requirements.txt`（项目根目录） | 几 KB | 安装清单，与 wheels 配套 |

所有 wheel 的 sha256 已逐一和 uv.lock 校验一致（与 Docker 镜像同源同版本）。

## 二、内网 Windows 电脑从零安装（照抄即可）

```powershell
# 1. 装 Python（双击 python-3.12.9-amd64.exe，务必勾选 "Add python.exe to PATH"）

# 2. 在项目根目录（有 app/ 的地方）建虚拟环境并离线装依赖
python -m venv .venv
.venv\Scripts\activate
pip install --no-index --find-links deploy_split\wheels_win -r requirements.txt

# 3. 跑测试验证环境 OK
python -m pytest tests/ -q

# 4. 本地起服务调试
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# 浏览器打开 http://localhost:8000/docs 可看接口文档
```

## 三、常见问题

- **装依赖报 "not a supported wheel"**：Python 装的不是 3.12（cmd 里 `python --version` 确认）
- **公司统一用 uv 时**（替代上面第 2 步）：
  `uv venv --python 3.12` 然后 `uv pip install --no-index --find-links deploy_split\wheels_win -r requirements.txt`
- **改了依赖要重新生成**：在外网机器改完 pyproject/uv.lock 后，重新导出 requirements.txt 并重下：
  `pip download -r requirements.txt -d wheels_win --platform win_amd64 --python-version 3.12 --implementation cp --only-binary=:all:`
- Windows 上跑本项目**不需要**额外装系统图形库（那是 Linux 裸机才要的 libgl1）

## 四、三套交付物分工（别搞混）

| 交付物 | 平台 | 用途 |
|---|---|---|
| `aiproctor_base_1.1.0.tar` | Linux/Docker | **正式部署**：内网 Linux 服务器跑生产服务 |
| `wheels_linux/` | Linux x86_64 | 备用：内网 Linux 裸机（不走 Docker）跑服务 |
| `wheels_win/` + Python 安装包 | Windows x64 | **你的内网开发机**：改代码、调试、跑测试 |

三者的依赖版本来自同一份 uv.lock，哈希已互相校验一致。
