# 双 AI 协作闭环 — 踩坑记录（troubleshooting.md）

> 真实项目（QuickTrans）中踩过的坑与解法。遇到问题先查这里。

## 1. git commit 卡住 / 任务挂起

**症状**：agent 写完代码，但 commit 一直不完成；或 SSE 读不到最终回复
**根因**：CLI serve 默认权限模式下，`git commit` 属于需确认操作，无人确认 → 挂起
**解法**：serve 启动必须带 `--permission-mode auto`
**验证**：派个只要求 commit 的任务，能秒过即正常

## 2. git 报 "user.name / user.email 未配置"

**症状**：`git commit` 直接失败
**解法**：仓库级配置（避免污染全局）：
```
git config user.name "workbuddy-agent"
git config user.email "agent@local"
```
**注意**：新 `git init` 的仓库默认没有身份，项目初始化时必须先配

## 3. SSE 读不到 agent 文本输出

**症状**：派活成功（runId 有了），但脚本打印 "(agent 未返回文本内容)"
**可能原因与排查顺序**：
1. **权限卡住**（最常见）→ 任务实际没完成，检查产物是否存在；加 `--permission-mode auto` 重启 serve
2. 任务还在跑 → 用 `--timeout` 给足时间
3. 事件结构差异 → `--debug` 打印原始事件，看 data 里有没有 text/markdown
4. 流提前断 → 任务完成后重新 `GET /api/v1/runs/{runId}/stream`（部分场景可重放）

## 4. token 过期 / 401

**症状**：`token: 无效` 或派活 401
**解法**：
1. 确认 WorkBuddy 桌面版在运行且已登录
2. 删除 `.cache/wb_token.txt`（强制重新提取）
3. `python dispatch.py --status` 验证

**有效期**：约 28 天。过期前重开一次 WorkBuddy 即自动刷新内存 token。

## 5. 环境变量用错（已走过的死路，勿重试）

| 尝试 | 结果 |
|---|---|
| `CODEBUDDY_API_KEY=<JWT>` | ❌ 401（token-type:ApiKey）——正确变量是 `CODEBUDDY_AUTH_TOKEN` |
| 裸跑 CLI（无 token） | ❌ 401（Authentication required. Please use /login） |
| `CODEBUDDY_HOST=workbuddy-desktop` 裸跑 | ❌ 401 |
| 网关端口 51740/56464/63093 Bearer=JWT | ❌ 401（网关不接受云 JWT） |
| 端口 18488/53816/61917 | ❌ 不可达/404 |
| 桌面设置里找 Remote Control | ❌ 不存在 |
| bin\codebuddy CLI | ❌ 坏入口（require 不存在的 dist/codebuddy） |

## 6. serve 启动失败

**排查**：
1. 看日志：`.cache/serve.log`
2. 端口占用：`netstat -ano | Select-String 51741` → 杀占用进程
3. token 无效 → 见 #4
4. 删 `.cache/serve.pid`（残留 pid 文件会误导）

## 7. 桌面版与 CLI 并发冲突

**症状**：CLI 派活时桌面版也在改同一文件 → 工作区互相覆盖/commit 内容错乱
**规则**：
- 派活前检查乙方活跃度：`inbox/worker_alive.txt` 更新时间、最近文件改动时间
- 乙方活跃 → CLI 不碰同一工作区（或等它 commit）
- 需要并行 → 用独立沙盒仓库（如 `demo/` 子目录独立 git init）

## 8. selftest 失败 ≠ 代码缺陷

**症状**：测试报 requests/pynput 等模块不存在
**判断**：看失败项是"环境依赖缺失"还是"逻辑断言失败"
- 环境缺失 → 装依赖（`pip install -r requirements.txt`），不算 P0
- 逻辑失败 → 真 bug，报 P0/P1

## 9. 审核基线误判

**症状**：定时任务每轮都说"有新提交"或"无新提交"都不对
**解法**：检查 `inbox/last_reviewed_commit.txt` 与 `git rev-parse HEAD` 是否同步；审核方每次审完必须更新基线

## 10. 心跳文件不更新

**症状**：`audit_heartbeat.txt` 长时间没新行
**可能**：定时任务没触发（查定时任务列表）/ 触发但脚本中途退出（查 query 里的命令是否可执行）
**注意**：用户要求每小时必须收到运行状态消息，**禁止静默**——即使无新提交也要汇报

## 11. 模式 B 任务队列的坑

**症状 1**：poll_tasks.py 报"任务目录不存在"
**解法**：先建 `inbox/tasks/`、`inbox/results/` 目录；任务单文件名必须 `NNN_*.md`（三位序号 + 下划线）

**症状 2**：任务重复处理
**解法**：处理完必须 `python poll_tasks.py --mark NNN`；确认 `inbox/last_task_processed.txt` 内容正确

**症状 3**：结果单找不到对应任务
**解法**：结果单文件名 NNN 必须与任务单完全一致（如任务单 `001_审代码.md` → 结果单 `001_审代码.md`）

**症状 4**：WorkBuddy 说"看不到豆包的结果"
**解法**：检查结果是否写在 `<cwd>/inbox/results/`（不是任务目录）；确认 WorkBuddy 读取的是同一绝对路径；必要时用户手动提示 WorkBuddy 去读

## 12. 角色互换时的常见误区

- 模式 B 下豆包是干活方：**不要**顺手去改 PRD/CHECKLIST/审核基线（那是审核方/契约文件的权限）
- 模式 A 下 WorkBuddy 干活：**不要**因为"它写得快"就让豆包直接改代码（违反审核方铁律）
- 谁当审核方以"谁对验收标准最有把握"为准；模棱两可时先问用户，不要猜

## 13. agent 写完代码但漏 commit（D2W 复测发现，2026-10-10）

**症状**：任务文本明确要求 commit，csv_summary.py 也写出来了，但 `git log` 显示仓库无 commit（run 状态 active:false 说明任务已结束）
**判断**：git 身份已配置也照样可能漏——这是 agent 执行完整性的问题，不是身份问题
**解法**：
1. 派活文本把 commit 列为硬性验收并让 agent"完成后汇报 hash"（能减少漏 commit，但不能杜绝）
2. 审核第一步**必须** `git log --oneline -3` 验证 commit 真的存在（SKILL.md 已把这条列为审核第 0 步）
3. 没 commit → 视为未完成，review 里标 P1"未完成 commit"，派修补 commit
4. 首次审核时无基线可对比，尤其要主动查 commit（别只对比 last_reviewed_commit.txt）

## 14. 派活报 502 Bad Gateway（环境代理劫持 loopback，2026-10-10 实测）

**症状**：`--status` 显示 `serve: 运行中`，但一派活就 `ERR: 派任务失败 502: upstream connect failed`；
或启动 serve 后 `/api/v1/health` 返回 502，而 `netstat` 里根本没人监听该端口
**根因**：环境里设了 `HTTP_PROXY` / `HTTPS_PROXY`（如 WorkBuddy 自带的本地代理 127.0.0.1:65009）。
Python `urllib` **默认走环境代理**，于是连 `127.0.0.1:51741` 的请求也被塞给代理 → 代理返回 502。
更坑的是旧 `port_busy()` 把任何 `HTTPError` 都当"服务活着"，502 也被判存活 → 跳过启动、直接派活失败。
**解法（已修入 dispatch.py）**：
1. 所有 loopback 请求统一走 `urllib.request.build_opener(urllib.request.ProxyHandler({}))`（空代理=直连）
2. `port_busy()` 把 502/503/504 视为**不存活**，只有 200/401/403 才算服务在跑
**自测**：`python -c "import urllib.request as u;print(u.urlopen(u.Request('http://127.0.0.1:51741/api/v1/health',headers={'x-codebuddy-request':'x'})).status)"`
拿到 502 就是被代理劫持；用空 ProxyHandler 拿到 401/200 才是正常的服务响应。

## 15. 派活报 401 AUTH_REQUIRED（新版 CLI 的 --auth none 失效，2026-10-10 实测）

**症状**：serve 正常启动、日志打印了端点，但 `POST /api/v1/runs` 返回
`401 {"error":{"code":"AUTH_REQUIRED","message":"Authentication required"}}`；health 也 401
**根因**：CLI v2.156+ 起，`--auth none` **会被 settings 的 gateway 配置 / 内建默认覆盖**。
服务端最终选定的模式优先级是：
`CODEBUDDY_GATEWAY_AUTH` 环境变量 > `--auth` 标志 > settings.json 的 `gateway.auth` > 内建默认 `password`。
本机 settings 里 `gateway` 为 null，于是回落到默认 `password`，而脚本没传密码 → 401。
（启动日志会打印 `Auth enabled (mode: password)` 并给出一个随机 Web UI 密码，可作判据。）
**解法（已修入 dispatch.py）**：启动 serve 时显式设环境变量 `CODEBUDDY_GATEWAY_AUTH=none`。
启动日志会出现 `⚠ Authentication is DISABLED.`，此时 `/api/v1/health` 无鉴权头也返回 200。
**备选**（不想关鉴权）：从 `.cache/serve.log` 或启动日志里取 password，请求带
`?password=<pw>` / `Authorization: Bearer <pw>` 之一即可（见 CLI 的 authenticate 实现）。

## 16. 模式 B：--mark 乱序处理会静默吞任务（2026-10-10 实测并修复）

**症状**：任务 1/2/3/4/5 都在，直接 `--mark 4`，再 `poll` 时 1/2/3 **消失**（显示"已处理到序号 4"）
**根因**：旧实现用**单个最大序号**当游标，`--mark N` 等于宣布"≤N 全部已处理"，乱序场景必然丢任务
**解法（已修入 poll_tasks.py）**：改为**已处理序号集合**（`last_task_processed.txt` 存 `1,3,4` 逗号分隔）
- `--mark N` 只追加 N，不牵连其它序号；支持 `--mark` 传多次
- 新增 `--unmark N` 撤销
- **兼容旧格式**：文件里是单个纯数字（如 `4`）时按集合 `{4}` 读，行为与语义都不破坏
- 脏值（非数字项）自动忽略，不再整文件判废
**注意**：若沿用旧文件里的 `5`（表示"已审到 5"），新语义会认为只有任务 5 已完成、
1–4 重新变待办。迁移时按需把文件改成明确集合（如 `1,2,3,4,5`）。

## 17. SSE 中断 / 任务只写了一半没 commit（2026-10-12 实测）

**症状**：派活时要求"写 core 引擎 + ui 框架"等多个文件，agent 只完成一部分 SSE 就断了；
回来检查发现**没有 commit**（git log 无新提交），已写的一半代码也没落盘或零散在工作区
**根因**：
1. SSE 是流式连接，随时可能断（网络抖动、超时、代理、serve 重启都触发）
2. 一次派太多文件，agent 还没到"收尾 commit"步骤就断了 → 进度全丢
**解法（已写入 SKILL.md 与 methodology §5.14）**：
1. **分模块派活**：一次只派 1～2 个文件（core → ui → 测试 → 集成），逐模块推进
2. **每模块立即 commit**：任务文本必须写明"每写完一个模块立即 git commit，提交信息写模块名"，
   禁止攒到全部写完再提交
3. **断点续跑**：`git log --oneline` 看已到哪个模块 → 派"继续写下一个模块 XX，从上次 commit
   之后继续，不要重写已提交部分"
4. 验收也按模块走，别等全写完
**判据**：任务结束后 `git log --oneline -3` 没有新 commit 且产物文件不完整 → 视为断连未完成，走续跑或重派

## 18. 打包 EXE / 安装程序踩坑（2026-10-12 沉淀）

**症状 1：PyInstaller 打包失败**
- `RecursionError` / `ModuleNotFoundError`：隐式导入没带 → `--hidden-import <模块>`（动态 import、pandas、requests 等常见）
- 打包出来启动报缺文件/报错：数据文件没打进 → `--add-data "src;dst"`（注意 Windows 用 `;` 分隔）
- 缓存残留导致怪问题：`--clean`（清缓存重打）；还不行删 `build/` 目录
- 体积巨大 / 启动慢：换 `--onedir`（目录版，启动快体积分摊），或用 Nuitka（更小，但编译慢、依赖 MinGW）
- **先区分**：报错是打包期还是运行期（打包期=参数/依赖；运行期=隐式导入/数据文件/环境路径）

**症状 2：打包后的 EXE 界面错位 / 字体丢失 / 图标不显示**
- 高频原因：**资源/字体/图标未打进包**（`--add-data` / `--icon` 没带对），或代码里用了相对路径找资源
- 解法：派活时明确"资源路径用 `sys._MEIPASS` 拼接（打包态）回退项目根（源码态）"；
  审核时**打包版必须重跑 L 组界面验收**（源码界面好 ≠ 打包版好）

**症状 3：杀软误报**
- 常见于 onefile + 无签名的小程序；解法：产物说明、代码不加密不混淆（混淆反而更容易误报）、
  必要时代码签名证书；告知用户"首次运行信任即可"

**症状 4：Inno Setup 中文乱码**
- 用 UTF-8 写脚本；中文 AppName/路径确认安装器语言支持；安装后中文不乱码才算过

## 19. 需求中途变更（2026-10-12 沉淀）

**症状**：开发中用户口头加功能，直接塞进下一次派活文本 → 乙方做偏、CHECKLIST 对不上、验收扯皮
**解法（已写入 methodology §5.18）**：
1. 变更先走契约：豆包起草 PRD/CHECKLIST 增量 → **用户确认** → 再派活
2. 明确"在现有基础上改，不动已验收部分"；CHECKLIST 新条目单独编号，只复核新增/受影响项
3. 变更影响核心架构 → 重新分模块派活，别一次全塞
**判据**：派活文本里出现"顺便加个…"这类追加 → 先停，回 PRD/CHECKLIST 流程

