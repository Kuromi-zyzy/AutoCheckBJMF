# AutoCheckBJMF — 班级魔方 GPS 自动签到

班级魔方（bj.k8n.cn）自动定位签到工具：多账号、多班级、多定位点、时间窗轮询，无需人工守着打卡。

> 详细使用文档见 [`AutoCheckBJMF/README.md`](AutoCheckBJMF/README.md)

## 功能特性

- **时间窗轮询**：窗口内按间隔自动扫描签到任务（config 中配置，如 18:00–22:00），签到成功后自动拉长扫描间隔
- **多账号 / 多班级**：每个账号独立 Session，杜绝跨账号 Cookie 串扰
- **GPS 随机偏移**：每次签到在定位点附近 ±15 m 随机抖动，多定位点随机选取
- **稳定常驻**：窗口结束自动睡眠到次日，不退出进程（配合 pm2 不会循环重启）；SIGTERM 优雅停机
- **失败退避重试**：单账号失败 30s / 300s 两轮自动重试
- **日志降噪**：无任务时段 30 分钟一条心跳，日志量极小

## 快速开始（Windows，零基础双击即用）

```text
1. 安装 uv：powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
2. 双击 install.bat          # uv sync 自动装依赖
3. 双击 config_wizard.bat    # 配置班级/定位/账号
4. 双击 update_cookie.bat    # 微信扫码抓取 cookie
5. 双击 start_checkin.bat    # 后台常驻运行
```

## 服务器部署（Linux + pm2 + uv）

```bash
git clone https://github.com/Kuromi-zyzy/AutoCheckBJMF.git
cd AutoCheckBJMF/AutoCheckBJMF && uv sync --python 3.11
# 准备 config.json 后：
pm2 start .venv/bin/python --name AutoCheckBJMF --interpreter none -- src/main.py
```

## 运维体系

| 组件 | 说明 |
|------|------|
| `deploy.sh` | 服务器一键部署：影子仓 git pull → rsync 运行目录 → uv sync → pm2 restart |
| `renew_cookie.sh` | Cookie 一键续期：拉起 Windows 扫码 → 合并 → 上传服务器 → 重启验证 |
| `healthcheck.sh` | 每 30 分钟自检 pm2 状态与登录态，异常推 Telegram 告警（@banjimofangbot） |

## 目录结构

```text
AutoCheckBJMF/          # 项目本体（本仓所有代码都在这个子目录）
├── src/main.py         # 主循环：窗口轮询状态机
├── src/once.py         # 单次签到
├── src/update_cookie.py# 微信扫码抓 cookie（DrissionPage）
├── install.bat / start_checkin.bat / update_cookie.bat / config_wizard.bat
├── pyproject.toml + uv.lock
└── config.json         # 运行配置（含 cookie，不入 git）
```

## 已知限制

- 签到窗口不支持跨午夜（如 20:00→02:00 会立即结束窗口）
- BJMF Cookie 无刷新机制，过期需微信扫码重抓

## License

MIT — 见 [LICENSE](AutoCheckBJMF/LICENSE)
