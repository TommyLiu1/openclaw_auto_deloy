# OpenClaw 一键部署工具

支持 **Windows、Mac、Linux** 的 OpenClaw 一键部署。使用前需输入 **License Key**，在**服务器端**完成与本机机器码的绑定与验证，**一个 License Key 只能绑定一台机器**，服务器验证通过后用户才能继续一键部署。

## 功能

- **服务器端 License 验证**：预置有效 License Key（含有效期），用户启动工具输入 Key 后，将本机 machine_id 上传至服务器激活；一台设备只能绑定一个 Key，绑定后仅该机器可验证通过。
- **一键部署**：验证通过后，优先使用 Docker 部署 OpenClaw，无 Docker 时在 Linux/Mac 上可走 Node.js 安装。
- **跨平台**：Windows / macOS / Linux 统一命令行入口。
- **日志**：工具端与服务端均使用 **loguru** 记录日志，便于排查问题。
- **可执行文件**：工具端可用 **PyInstaller** 打包为单文件 exe（Windows）/ 可执行文件（Mac/Linux），用户**双击即可运行**，无需安装 Python。

## 环境要求

- Python 3.8+
- 网络可访问 **License 授权服务器**（地址可通过环境变量 `OPENCLAW_LICENSE_SERVER` 配置）
- 部署方式二选一：
  - **Docker**（推荐）：已安装 Docker，可一键拉取并运行 OpenClaw 镜像。
  - **Node.js 22+**：仅在 Linux/Mac 下作为备选，Windows 建议使用 Docker。

## 安装（客户端）

```bash
cd openclaw_tool
pip install -e .
```

安装后可使用：

```bash
openclaw-deploy --help
```

### 打包为可执行文件（用户双击运行）

无需安装 Python 即可使用：在项目根目录执行以下命令，将工具打包为单文件可执行程序：

```bash
pip install pyinstaller
python build_exe.py
```

- **Windows**：生成 `dist/openclaw-deploy.exe`，用户双击运行即可。若未配置 License 或运行出错，窗口会提示并等待按回车后关闭。
- **Mac / Linux**：生成 `dist/openclaw-deploy`，赋予执行权限后可直接运行或双击（视系统而定）。

日志仍会写入用户目录：`~/.openclaw_deploy/logs/tool.log`。

## 使用步骤（用户侧）

### 1. 获取预置的 License Key

从授权方获取一个**有效的 License Key**（含有效期）。该 Key 在首次激活前未绑定任何设备。

### 2. 输入 License Key 并完成激活

在需要部署的电脑上执行：

```bash
openclaw-deploy --license "你的License_Key"
```

工具会将本机 **machine_id** 上传到授权服务器：
- 若该 Key 尚未绑定任何设备，则**绑定到本机**，验证通过，可继续一键部署。
- 若该 Key 已绑定本机，则直接验证通过。
- 若该 Key 已绑定其他设备，则验证失败，提示「此 License 已绑定到其他设备」。

**一个 License Key 只能绑定一台机器**，服务器验证通过后，用户才能继续执行部署。

### 3. 一键部署（可选：通道配置）

首次验证通过后，License 会保存到本地，之后可直接执行：

```bash
openclaw-deploy
```

无需重复输入 License（每次仍会向服务器验证，确保 Key 仍有效且绑定本机）。

**配置 QQ / 钉钉 / 企业微信 / 飞书**：通道配置文件应放在**与可执行文件同一目录**下，文件名为 `channels.json`。用户启动程序后会自动读取该文件并用于部署。

- **打包为 exe 时**：将 `channels.json` 与 `openclaw-deploy.exe` 放在同一目录，双击运行即可自动应用通道配置。
- **命令行运行且未指定 `--config` 时**：默认读取当前工作目录下的 `channels.json`；也可显式指定：`openclaw-deploy --config /path/to/channels.json`。
- 配置文件格式：顶层 key 为通道名 `feishu`、`wecom`、`dingtalk`、`qq`，每项为对应 OpenClaw 通道配置（与官方 `openclaw.json` 中 `channels.*` 结构一致）。有则合并进 OpenClaw 并重启网关，**配置完成后会校验是否写入成功**。
- 示例见项目根目录 `channels.example.json`，复制为 `channels.json` 并按需修改后放在 exe 同目录即可。

### 4. 仅校验 License（不部署）

```bash
openclaw-deploy --verify --license "你的License_Key"
```

### 5. 查看本机机器码

```bash
openclaw-deploy --machine-id
```

---

## 授权服务端（License Server）

工具需连接授权服务器进行激活/验证。本仓库提供参考实现，部署后由授权方维护 License 与绑定关系。

### 安装与运行

```bash
pip install -r license_server/requirements.txt
python -m license_server.app --host 0.0.0.0 --port 8080
```

默认监听 `http://0.0.0.0:8080`。数据文件为当前目录下 `licenses.json`（可通过环境变量 `OPENCLAW_LICENSE_DATA` 指定目录）。服务端使用 **loguru** 记录日志，日志文件位于该数据目录下的 `logs/app.log`。

### 预置 License Key（含有效期）

在服务端添加可用的 License Key（有效期格式：`YYYY-MM-DD HH:MM:SS`）：

```bash
# 自动生成 Key，默认有效期至 2026-12-31 23:59:59
python -m license_server.add_license

# 指定过期时间
python -m license_server.add_license --expires "2027-06-30 23:59:59"

# 指定自定义 Key
python -m license_server.add_license --key "MY-CUSTOM-KEY-001" --expires "2026-12-31 23:59:59"
```

将输出的 License Key 发给用户。用户在本机输入该 Key 并运行工具时，会将该 Key 绑定到本机 machine_id，此后该 Key 仅能在此机器上验证通过。

### 客户端指定服务器地址

默认请求 `http://127.0.0.1:8080`。若授权服务部署在其他地址，请设置环境变量：

```bash
export OPENCLAW_LICENSE_SERVER=https://your-license-server.com
openclaw-deploy --license "你的License_Key"
```

---

## 部署结果说明

- **Docker 部署**：容器名 `openclaw`，管理界面为 `http://127.0.0.1:18789/`。首次需在容器内完成 onboarding：  
  `docker exec -it openclaw openclaw onboard`
- **Node 部署**（Linux/Mac）：全局安装 `openclaw`，端口 18789，使用系统服务或 `openclaw` 命令管理。

## 项目结构

```
openclaw_tool/
├── openclaw_deploy/          # 客户端：一键部署 + License 校验
│   ├── __init__.py
│   ├── __main__.py           # 入口（python -m / PyInstaller 打包）
│   ├── cli.py                # 命令行入口
│   ├── channels_config.py   # 通道配置解析、合并与校验（QQ/钉钉/企业微信/飞书）
│   ├── deploy.py             # Docker / Node 部署逻辑，应用配置并校验
│   ├── license.py             # 调用服务器激活/验证（上传 machine_id）
│   ├── logger.py              # loguru 日志配置
│   └── machine_id.py          # 本机机器码
├── channels.example.json     # 通道配置示例（feishu/wecom/dingtalk/qq）
├── license_server/            # 服务端：预置 License + 绑定 machine_id
│   ├── __init__.py
│   ├── app.py                # Flask 服务，/api/activate，loguru 日志
│   ├── add_license.py         # 预置 License Key（含有效期）
│   └── requirements.txt
├── openclaw_deploy.spec      # PyInstaller 打包配置
├── build_exe.py              # 一键打包脚本
├── requirements.txt
├── pyproject.toml
└── README.md
```

## License 机制简述

- **预置 License**：授权方在服务器预置有效 License Key 及有效期。
- **激活/验证**：用户输入 Key 后，工具将当前 **machine_id** 上传至服务器；服务器校验 Key 有效且未过期，且**一个 Key 只能绑定一台机器**（未绑定则绑定本机，已绑定本机则通过，已绑定他机则拒绝）。
- **通过后部署**：仅当服务器返回验证通过时，工具才允许继续执行一键部署。

## 许可证

MIT
