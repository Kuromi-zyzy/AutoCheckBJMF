# classmagic-sign — 班级魔方自动签到（AutoCheckBJMF）

自动 GPS 定位签到：多账号/多班级/多定位点/时间窗轮询。⏸️ **2026-07-28 主动停跑过暑假（pm2 stop），开学（2026-09）上线**——上线前必修的三个 bug **已于 2026-08-29 全部修完（本地，待同步服务器）**，checklist 见文末。

## 目录与运行形态

- 本仓：`AutoCheckBJMF/` 子目录（src/main.py 主循环、src/once.py 单次签到、src/update_cookie.py、config.json、logs/sign_log.txt；**本地 .venv 由 uv 管理（Python 3.11），依赖=pyproject.toml + uv.lock，`uv sync` 一键装**；install.bat 已改 uv，勿再手装 pip 包）
- 服务器：`/opt/AutoCheckBJMF`（属主 tang:tang；**无 git**，代码停在 2026-07-08 版，本地领先——部署=打包 scp 上传，流程见 vm-server 旧手册 git 历史或记忆 notes://classmagic_bjmf_server_status；服务器旧 venv= pip 手建，上线时建议换 uv sync 重建为 .venv 并更新 pm2 script 路径）
- 守护：pm2（tang 用户），script=venv python src/main.py；开机自启待 `pm2 save && pm2 startup` 复核

## 三个必修 bug —— 全部已修（2026-08-29，本地）

1. **重启循环** ✅：窗口结束后不再 break 退出，改为分片（≤30min）睡眠到次日窗口开始（`seconds_until_next_start()`，每次醒来重读墙钟，防 NTP 校时漂移），并重置 last_scan/dynamic_interval。根治 pm2 42 万次重启循环（E2E 状态机测试已验证：窗口结束分支进程保持存活、SIGTERM 可优雅停机）
2. **静默退出** ✅：load_config 三种失败（文件不存在/JSON 非法/缺必需键）均写 stderr 后 exit(1)；pm2 error log 可见。非零退出码受 pm2 unstable 保护（连续快速崩溃 16 次自动标 errored），不会再形成正常退出的死循环
3. **update_cookie.py 覆盖 cookies 列表** ✅：改为按 `username=` 提取账号比对——同账号替换旧 cookie、新账号追加，多账号配置不再丢数据；常量改用 constants.py 统一来源

顺手修：qiandao 每账号独立 Session（杜绝跨账号 Set-Cookie 串扰）；日志降噪（"No active check-in tasks" 降 debug，无活动轮询 30 分钟一条 Idle heartbeat，日志量 ~2MB/天 → 大幅下降）；logs/.gitkeep 恢复；install.bat 弃 pip 清华源改 `uv sync`；README 同步（uv 安装指引、窗口外行为、文件树补 update_cookie）

## 上线 checklist（bug 已修，剩部署步骤）

1. 同步代码上服务器（scp 打包 src/ + pyproject.toml + uv.lock + bat 脚本；config.json 按需）→ 服务器 `uv sync` 重建 .venv（旧 venv/ 可留作回滚）
2. pm2 更新 script 路径（若换 .venv）→ `pm2 reset` 清 42 万计数
3. Windows 扫码向导抓新 Cookie 上传 config.json（停跑 1 个月+ 大概率过期）
4. `pm2 restart AutoCheckBJMF` → `pm2 save && pm2 startup`（确认开机自启）
5. 观察一天：`pm2 logs` 无异常、sign_log 有记录、**重启计数不再增长**（窗口 23:00 结束后进程应保持 online 而非反复重启）

已知限制：签到窗口不支持跨午夜（start < end，如 20:00→02:00 会立即结束窗口）；`scheduletimes` 固定 ["auto"]。

## 服务器侧上下文

SSH/pm2/日志命令、服务全景见 `~/projects/vm-server/服务器Wiki.md`（权威）与 `服务器运维指南.md` §7；服务器内存仅 898Mi，勿加本地模型/重依赖。
