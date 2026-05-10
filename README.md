# 校园网自动登录助手

校园网自动登录助手是一个 Windows 绿色版桌面客户端，用于识别常见校园网 Web Portal 协议，并在识别成功后保存登录配置、手动登录或后台常驻自动登录。

## 功能

- 首次使用先输入校园网登录页网址，软件自动识别协议。
- 识别失败时停止在识别页，不要求用户填写账号和密码。
- 支持复制脱敏诊断信息，便于后续新增协议适配。
- 内置第一批协议适配器：
  - Dr.COM / ePortal
  - Ruijie / 锐捷 Web Portal
  - Srun / 深澜
  - H3C / iNode Web Portal
  - 通用表单登录模板
- 支持电信、移动、联通、校园网/无后缀、自定义运营商后缀。
- 密码使用 Windows DPAPI 加密保存，只能在当前 Windows 用户环境下解密。
- 支持多配置档案、立即登录、注销、暂停/恢复、托盘常驻、开机自启。
- 已保存配置支持在主界面重新命名，便于区分不同校园网或运营商组合。
- 常驻时可选择防止电脑自动睡眠/休眠，适合需要远程控制的场景。
- 支持唤醒后自动立即检测网络，并在断网时尝试重新登录。
- 支持多个断网检测地址，减少单个网站不可达导致的误判。
- 支持一键健康检查，快速查看托盘、常驻、开机自启、密码解密、网关和外网检测状态。
- Windows 睡眠/休眠恢复后可通过系统电源事件更快触发网络检测。
- 运行日志在界面内显示时间戳，方便排查登录失败、已在线、重试等事件。
- 支持复制/清空日志、打开日志目录、导出脱敏诊断包和检查 GitHub 最新版本。
- 使用 PyInstaller 生成 `onedir` 绿色版目录，解压即可运行。

## 已试用学校

- 绍兴大学

## 使用方式

### 下载绿色版

在仓库右侧或顶部进入 **Releases**，下载最新版本中的：

```text
CampusAutoLogin-v0.3.0-windows-x64-portable.zip
```

下载后解压，双击运行：

```text
CampusAutoLogin\CampusAutoLogin.exe
```

绿色版不会写入安装目录以外的系统位置；运行后会在程序目录下生成本地 `data` 文件夹，用于保存配置和日志。密码使用 Windows DPAPI 加密保存，复制到其他电脑后需要重新输入密码。

也可以使用网盘镜像下载：

- 夸克网盘：[https://pan.quark.cn/s/60f8c714e21f](https://pan.quark.cn/s/60f8c714e21f)，提取码：`NUYP`
- 百度网盘：[https://pan.baidu.com/s/19yV5blA-Aym847HX2wJkww](https://pan.baidu.com/s/19yV5blA-Aym847HX2wJkww)，提取码：`1v9n`

### 开发环境运行

```powershell
python -m pip install -r requirements.txt
python main.py
```

### 首次配置

1. 打开程序。
2. 输入校园网登录页网址，例如 `http://portal.example.edu/`。
3. 点击“识别协议”。
4. 识别成功后填写账号、密码和运营商。
5. 保存配置后，可以点击“立即登录”，也可以勾选“启动常驻”。

如果协议无法识别，程序会显示“暂未适配该网站”，并提供诊断信息复制按钮。诊断信息会脱敏处理，不会导出密码、token、cookie 等敏感内容。

### 常驻和远程控制

- 勾选“启动常驻”后，程序会留在后台定时检测网络；托盘菜单也可以手动触发“检测网络”。
- 勾选“常驻时防止睡眠/休眠”后，Windows 会保持系统运行，避免休眠后远程控制断开。
- 勾选“唤醒后立即检查”后，如果电脑从睡眠/休眠恢复，程序会立刻检查网络并在需要时重新登录。
- 主界面可以调整“检测间隔”“定期重登”和多个“断网检测地址”。

## 打包绿色版

```powershell
.\build_green.ps1
```

如果系统默认 `python` 不是安装了 PySide6 / PyInstaller 的解释器，可以指定 Python 路径：

```powershell
.\build_green.ps1 -PythonPath "C:\Users\26354\AppData\Local\Programs\Python\Python312\python.exe"
```

打包建议使用官方 Python 3.12 x64。部分 conda 环境可能导致 PyInstaller 漏带 `_ctypes` 依赖，打出的绿色包会在启动时报 “DLL load failed while importing _ctypes”。

打包完成后，绿色版目录位于：

```text
dist\CampusAutoLogin
```

主程序为：

```text
dist\CampusAutoLogin\CampusAutoLogin.exe
```

## 常用辅助脚本

停止已经运行的客户端：

```powershell
.\stop_campus_auto_login.ps1
```

以安全模式打开客户端：

```cmd
open_safe_mode.bat
```

安全模式会跳过单实例限制，适合排查托盘、常驻或启动异常。

## 日志和配置

绿色版运行时会在程序目录下生成本地数据：

```text
dist\CampusAutoLogin\data
```

其中包含配置、日志和启动错误信息。这些文件可能包含本机状态或加密后的密码，不应提交到 Git。

## 安全说明

- 程序不会在协议无法识别时盲目提交账号密码。
- 密码不会明文写入配置文件，而是使用 Windows DPAPI 加密。
- 换电脑或换 Windows 用户后，已保存密码无法解密，需要重新输入。
- 诊断信息会尽量脱敏 URL 参数、密码、token、cookie、session 等字段。

## 开发测试

运行协议识别和登录结果解析测试：

```powershell
python -m unittest discover -s tests
```

## 仓库状态

当前项目仍处于早期调试阶段，欢迎根据实际校园网环境提交诊断信息、问题反馈和协议适配建议。
