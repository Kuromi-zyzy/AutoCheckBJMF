# 班级魔方 GPS 自动签到 — AutoCheckBJMF

> 自动完成班级魔方（k8n.cn）的 GPS 定位签到。
> 面向 **零代码基础** 用户 —— 全程无需敲命令，双击鼠标即可。
>
> **本项目借鉴于 [Moeus/AutoCheckBJMF](https://github.com/Moeus/AutoCheckBJMF)，在此表示诚挚感谢。**

[安装问题](#第一步安装环境仅首次) | [常见问题](#常见问题排查)

---

## 目录

- [项目能做什么](#项目能做什么)
- [三步上手（最快 3 分钟）](#三步上手最快-3-分钟)
- [详细操作说明](#详细操作说明)
  - [第一步：安装环境（仅首次）](#第一步安装环境仅首次)
  - [第二步：扫码配置（仅首次 / 更新 Cookie 时）](#第二步扫码配置仅首次--更新-cookie-时)
  - [第三步：启动签到（每天用）](#第三步启动签到每天用)
- [进阶功能](#进阶功能)
  - [立即签到一次](#立即签到一次)
  - [开机自动启动签到](#开机自动启动签到)
  - [手动修改配置](#手动修改配置)
  - [查看签到日志](#查看签到日志)
  - [停止签到](#停止签到)
- [常见问题排查](#常见问题排查)
- [文件功能一览](#文件功能一览)
- [配置文件格式](#配置文件格式)
- [服务器部署（进阶）](#服务器部署进阶)
- [注意事项 & 免责声明](#注意事项--免责声明)

---

## 项目能做什么

自动完成 "班级魔方" 平台上的 GPS 定位签到，功能包括：

- **GPS 定位签到** — 自动检测并完成签到，无需手动操作
- **多账号** — 同时为多人签到，每人坐标随机微偏移 ±15m，不会被检测
- **多班级** — 配置多个班级 ID，依次全部签到
- **多定位点** — 支持多个坐标随机选取
- **窗口扫描** — 设置时间段（如 08:00-22:00），程序自动每隔 N 分钟检测一次
- **失败重试** — 签到失败后自动重试（30 秒 + 5 分钟后各一次）
- **后台静默运行** — 关掉终端窗口照样跑，不占屏幕

---

## 三步上手（最快 3 分钟）

| 步骤 | 操作 | 什么时候做 |
|------|------|------------|
| **① 安装** | 双击 `install.bat`，等待完成 | 仅首次 |
| **② 配置** | 双击 `config_wizard.bat`，按提示操作 | 首次 / Cookie 过期后 |
| **③ 签到** | 双击 `start_checkin.bat` | 每天启动 |

```
双击 install.bat          ← ① 装环境（等几分钟，仅一次）
双击 config_wizard.bat    ← ② 扫码配置班级、位置、时间
双击 start_checkin.bat    ← ③ 以后每天双击它，开始自动签到
```

> 配置完成后，以后每天只需要做第 ③ 步。

---

## 详细操作说明

### 第一步：安装环境（仅首次）

**双击 `install.bat`**，等待窗口显示"安装完成！"后按任意键关闭。

程序会自动做以下事情（全程无需你操作）：
1. 检查电脑有没有装 Python
2. 创建一个独立的 Python 运行环境
3. 自动下载安装需要的工具包（使用清华镜像，速度很快）

整个过程大约 2-5 分钟，取决于网速。

> **双击后闪退？** 说明电脑没有安装 Python。到 [python.org](https://www.python.org/downloads/) 下载安装，安装时 **一定要勾选** "Add Python to PATH"。

> **窗口提示 "access denied"？** 右键 `install.bat` → "以管理员身份运行"。

---

### 第二步：扫码配置（仅首次 / 更新 Cookie 时）

**双击 `config_wizard.bat`**，会弹出一个命令行窗口和一个浏览器窗口。

#### 子步骤 2.1 — 扫码获取班级和账号

1. 程序自动打开浏览器，显示 **微信扫码登录** 页面
2. 打开手机微信 → 扫一扫 → 扫描屏幕上的二维码 → 手机上点确认登录
3. 登录成功后，程序自动读取班级列表并抓取登录凭证（Cookie）
4. 如果有多个人需要签到（比如帮室友），程序会问"是否继续添加账号？"，选是之后换另一个人的微信扫码
5. 全部添加完毕后选否，程序列出检测到的班级 ID
6. 如有未检测到的班级，直接输入班级 ID 数字手动补充

#### 子步骤 2.2 — 设置签到位置

1. 程序自动打开 [腾讯坐标拾取工具](https://lbs.qq.com/getPoint/)
2. 在浏览器地图上 **点击你平时签到的地点**（教室、宿舍楼等）
3. 右侧显示该点的 **纬度** 和 **经度**，复制到命令行窗口
4. 尽量保留 8 位小数（如 `28.06705800`），海拔直接回车用默认 10
5. 可添加多个位置，完成后关闭地图

> 每个账号签到时坐标会自动做微小随机偏移，不需要手动设置多个相似坐标。

#### 子步骤 2.3 — 设置签到时间窗口

设置一个时间段和扫描间隔：

- **窗口开始** — 什么时候开始自动签到（如 `08:00`）
- **窗口结束** — 什么时候停止（如 `22:00`）
- **扫描间隔** — 隔几分钟查一次有没有签到任务（推荐 5 分钟）

#### 子步骤 2.4 — 确认保存

- 调试模式选"否"即可（出问题时再开）
- 确认保存，配置完成

---

### 第三步：启动签到（每天用）

**双击 `start_checkin.bat`**，窗口显示"[OK] 签到程序已在后台静默运行"后自动关闭。

程序在后台静默运行，到你设置的签到窗口时间（`schedule_window_start` - `schedule_window_end`）就会自动每隔 N 分钟（`schedule_interval`）检测并签到。

确认程序是否在运行：右键任务栏 → 任务管理器 → 详细信息 → 查找 `pythonw.exe`。

> ⚠️ **注意**：程序**仅在配置的时间窗口内**执行签到。窗口外会静默等待或退出，任务管理器可能看不到进程，这是正常行为。

---

## 进阶功能

### pwsh 7 命令行快速操作

如果你安装了 [PowerShell 7（pwsh）](https://github.com/PowerShell/PowerShell/releases)，可以用命令更灵活地操作：

```powershell
# 进入项目目录（替换为你的实际路径）
cd "D:\Tools\ClassMagicSign\AutoCheckBJMF"

# 启动后台签到
Start-Process -WindowStyle Hidden -FilePath ".venv\Scripts\pythonw.exe" -ArgumentList "src\main.py"

# 立即签到一次
.venv\Scripts\python.exe src\once.py

# 查看最近 20 条签到记录
Get-Content logs\sign_log.txt -Tail 20 -Encoding UTF8

# 实时监控签到日志（持续刷新）
Get-Content logs\sign_log.txt -Wait -Tail 10 -Encoding UTF8

# 查看签到进程是否在运行
Get-Process pythonw -ErrorAction SilentlyContinue

# 停止签到
Stop-Process -Name pythonw -Force -ErrorAction SilentlyContinue

# 用记事本打开配置文件
notepad config.json
```

### 立即签到一次

偶尔需要马上签一次到（不等窗口时间）：

| 方式 | 操作 |
|------|------|
| 右键运行 | 右键 `checkin_now.ps1` → "使用 PowerShell 运行" |
| 命令行 | `python src\once.py` |

### 开机自动启动签到

| 方式 | 操作 |
|------|------|
| 双击 bat | 双击 `SetAutoStart.bat`，提示"添加成功！"即完成 |

以后每次开机签到程序自动后台运行。

**取消开机自启：**

| 方式 | 操作 |
|------|------|
| 手动删除 | 打开 `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`，删除里面的 `start_checkin.bat` |

### 手动修改配置

**方法一（推荐）：** 重新双击 `config_wizard.bat`，程序会保留之前的配置，只改要改的部分。

**方法二：** 用记事本打开 `config.json` 修改后保存，然后重新启动签到程序。

### 查看签到日志

用记事本打开 `logs\sign_log.txt`，每次签到都会记录：

```
2026-06-20 08:05:12 - UID[1 <张三>] | 班级[102513] | Result: 签到成功
2026-06-20 08:05:15 - UID[2 <李四>] | 班级[102513] | Result: 签到成功
```

### 停止签到

| 方式 | 操作 |
|------|------|
| 任务管理器 | `Ctrl+Shift+Esc` → 找到 `pythonw.exe` → 结束任务 |

---

## 常见问题排查

**Q：双击 bat 一闪而过？**
A：检查是否运行过 `install.bat`。没安装的话先双击它。

**Q：签到失败 / 日志显示"登录状态异常"？**
A：99% 是 Cookie 过期了。双击 `config_wizard.bat`，选"不清空现有配置"，重新扫码登录后保存，再重启签到。

**Q：扫码页面白屏 / 打开很慢？**
A：首次打开浏览器较慢，等一两分钟。检查网络是否能访问 `k8n.cn`。

**Q：配置向导打开浏览器报错？**
A：可能缺少 Chrome。装了 Chrome 或 Edge 一般无需额外处理。报 "Chrome not found" 请安装 [Chrome](https://www.google.com/chrome/)。

**Q：日志显示"无签到任务"？**
A：不是 bug。老师还没发布签到任务，等发布后程序会自动检测到。

**Q：多人坐标会不会一模一样？**
A：不会。每个账号签到自动随机偏移约 ±15 米。

**Q：经纬度填多少合适？**
A：[腾讯坐标拾取](https://lbs.qq.com/getPoint/) 点击位置获取，8 位小数最佳。

**Q：能手机上运行吗？**
A：不能。仅支持 Windows 电脑（或 Linux 服务器）。

**Q：sign_log.txt 没有记录？**
A：说明当前没有可签到的任务。有任务时会自动记录。

**Q：关掉终端窗口后程序还会跑吗？**
A：会。后台签到使用 `pythonw.exe` 独立运行，不依赖终端窗口。

---

## 文件功能一览

```
AutoCheckBJMF/
│
├── install.bat             安装环境（仅首次，自动创建虚拟环境 + 装依赖）
├── config_wizard.bat       配置向导入口（双击打开，扫码登录、设置定位和时间）
├── start_checkin.bat       启动后台签到（双击后自动在后台运行，关窗口不中断）
├── SetAutoStart.bat        设置开机自启（把 start_checkin.bat 加入启动文件夹）
├── checkin_now.ps1         立即签到一次（右键 → 使用 PowerShell 运行）
├── config.json             配置文件（向导生成，含班级、账号、定位、时间窗口）
├── config.example.json     配置示例文件（参考格式用）
│
├── src/                    核心代码
│   ├── main.py             后台签到主程序（定时检测 + 自动签到，无控制台输出）
│   ├── once.py             立即签到程序（手动运行，签到一次后退出）
│   ├── make_config.py      配置向导程序（交互式配置班级、Cookie、定位、时间）
│   ├── constants.py        公共常量（路径、URL、UA 等，被各模块引用）
│   └── banner.py           启动画面 & 控制台对象（供配置向导和签到脚本共用）
│
├── logs/                   签到日志目录
│   ├── sign_log.txt        签到记录（每次签到结果都写在这里）
│   ├── AutoCheckBJMF.log   调试日志（debug 模式开启时记录详细信息）
│   └── .gitkeep            占位文件（确保 logs 目录被 Git 追踪）
│
├── pyproject.toml          项目元数据 & 依赖列表
├── uv.lock                 依赖版本锁定文件（uv 用）
├── .python-version         Python 版本要求（3.11）
├── .gitignore              Git 忽略规则
├── LICENSE                 GPL v3 开源协议
│
└── .venv/                  Python 虚拟环境（install.bat 自动生成，不要手动动）
```

---

## 配置文件格式

`config.json` 各字段说明（可用记事本打开编辑）：

```json
{
    "classes":       ["102513", "139098"],     // 班级 ID 列表
    "locations": [                              // 签到位置
        {"lat": "28.067058", "lng": "113.009303", "acc": "10"}
    ],
    "cookies":       ["remember_student_59ba36...=xxxxx"],  // 登录凭证
    "scheduletimes": ["auto"],                  // 固定为 auto（自动检测模式）
    "schedule_window_start": "08:00",           // 签到窗口开始时间
    "schedule_window_end":   "22:00",           // 签到窗口结束时间
    "schedule_interval":     5,                 // 扫描间隔（分钟）
    "debug":        false                       // 调试模式（出问题时开）
}
```

---

## 服务器部署（进阶）

如果你有一台 24 小时开机的 Linux 服务器：

> **前提：** 先在 Windows 上完成第二步（扫码配置），然后把整个项目文件夹上传到服务器。

### 安装依赖

```bash
# uv（推荐，速度快）
uv sync

# 或 pip
pip install beautifulsoup4 drissionpage prompt-toolkit questionary requests rich schedule
```

### pm2 管理进程

```bash
npm install -g pm2
pm2 start src/main.py --name AutoCheckBJMF --interpreter python3
pm2 startup && pm2 save

# 查看状态 / 日志
pm2 status
pm2 logs AutoCheckBJMF
```

> Cookie 过期后，在 Windows 上重新运行配置向导，把新的 `config.json` 上传到服务器，执行 `pm2 restart AutoCheckBJMF`。

---

## 注意事项 & 免责声明

- 电脑需要保持开机程序才能签到
- 修改 `config.json` 后需要 **重新启动** 签到程序才能生效
- Cookie 会不定期过期（通常几周到几个月），过期后需重新扫码
- 签到窗口时间建议设宽裕些（如 06:00 - 23:00），避免错过
- 多人签到时请确认每个人都在这些班级里
- 云服务器无图形界面，请在 Windows 上运行配置向导后再上传配置

> **免责声明：** 本项目仅供学习交流使用，请勿用于作弊等违规行为。使用本项目产生的一切后果由使用者自行承担。

---

*[github.com/Moeus/AutoCheckBJMF](https://github.com/Moeus/AutoCheckBJMF)*
