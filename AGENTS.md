# classmagic-sign — 班级魔方自动签到（AutoCheckBJMF）

自动 GPS 定位签到：多账号/多班级/多定位点/时间窗轮询。✅ **2026-09-06 已上线运行**（服务器 pm2 常驻 + TG 告警 + git 化部署），历史三 bug（重启循环/静默退出/cookie 覆盖）已修复并实测验证。

## 三端格局（职责固定）

| 端 | 位置 | 职责 |
|----|------|------|
| WSL 主仓 | `~/projects/classmagic-sign/AutoCheckBJMF`（git main 分支） | **唯一开发地**：代码只在这里改，commit + push 即完成发布准备 |
| GitHub | `Kuromi-zyzy/AutoCheckBJMF`（main，公开仓） | 备份 + 部署源，服务器与 WSL 以它为准同步 |
| 服务器生产 | `tang@20.89.98.255:/opt/AutoCheckBJMF`（pm2 常驻） | 运行；代码只经 `deploy.sh` 从 GitHub 拉取，**不要手改** |
| Win 侧 | `D:\Tools\ClassMagicSign\AutoCheckBJMF` | **纯扫码入口**（Chrome+微信抓 cookie），代码已同步但别在那里开发 |

## 日常运营（三条命令）

1. **部署/更新服务器代码**（WSL 侧执行）：
   `ssh tang@20.89.98.255 -i ~/.ssh/zhaoyang.pem 'bash /opt/AutoCheckBJMF_git/deploy.sh'`
   → 影子仓 git reset 到 origin/main + rsync 到运行目录 + `uv sync` + pm2 restart；已是最新则自动跳过
2. **Cookie 续期**（失效时 TG 会先收到告警）：
   `bash AutoCheckBJMF/renew_cookie.sh`（WSL 侧；浏览器弹出后微信扫码，自动完成 合并→上传→重启→验证）
3. **看运行状态**：
   `ssh tang@20.89.98.255 -i ~/.ssh/zhaoyang.pem 'pm2 ls; tail -20 /opt/AutoCheckBJMF/logs/sign_log.txt'`

## 告警（TG bot @banjimofangbot「班级魔方签到」→ chat 7451198265）

- 服务器 cron 每 30 分钟跑 `/opt/AutoCheckBJMF_git/healthcheck.sh`：pm2 非 online 或 sign_log 20 分钟内出现 `Login state invalid` → TG 推送；状态变化才发（不重复轰炸），恢复也报一条
- 凭据 `.tg_token` / `.tg_chat` 在 `/opt/AutoCheckBJMF_git/`（chmod 600，不入 git）
- 手动自测：`echo bad > /opt/AutoCheckBJMF_git/.health_state && bash /opt/AutoCheckBJMF_git/healthcheck.sh` 应收到恢复消息

## 部署状态（2026-09-06）

- 服务器 `.venv` = uv 管理 Python 3.11.15（旧 pip venv/ 与备份目录已清）；影子仓 `/opt/AutoCheckBJMF_git/` rsync 时排除 `config.json`/`logs/`/`.venv/`/`DEPLOY_VERSION`
- `DEPLOY_VERSION` 文件记录运行中代码的 commit
- cookie 已于 2026-09-06 扫码续期，服务器实测 HTTP 200 登录有效
- 实机验证：23:00 窗口结束后进程睡眠不退出（重启循环 bug 根治）、SIGTERM 优雅停机
- `config.json` 含 cookie，各处 .gitignore 均排除，服务器上 chmod 600

## 已知限制

- 签到窗口不支持跨午夜（start < end 会立即结束进入睡眠）；`scheduletimes` 固定 ["auto"]
- BJMF cookie 无刷新机制，过期只能微信扫码重抓（TG 会告警提醒）
- **拍照签到不支持**（2026-09-06 决策：暂不做）：脚本仅支持 GPS 定位签到；遇到拍照任务会明确提示"需要拍照信息，请手动签到"，不会误报成功

## 服务器侧上下文

SSH/pm2/日志命令、服务全景见 `~/projects/vm-server/服务器Wiki.md`（权威）与 `服务器运维指南.md` §7；服务器内存仅 898Mi，勿加本地模型/重依赖。
