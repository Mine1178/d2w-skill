---
name: d2w
description: 双 AI 协作开发闭环（豆包 ⇄ WorkBuddy，双向，即 Do-to-WorkBuddy / WorkBuddy-to-Do），一站式交付（开发→审核→打包 EXE→安装程序→使用手册→交付归档）。当用户要求"指挥 WorkBuddy/腾讯桌面AI 干活"、"两个 AI 协作开发/互相派活"、"审核 AI 写出的代码"、"定时给 AI 派任务并审核"、"让 AI 写代码然后审改循环"、"把 AI 干活的结果自动审核"、"处理 WorkBuddy 派给我的任务"、"双 AI 自动跑通开发流程"、"把软件打包成 EXE"、"生成安装程序"、"写产品使用手册"、"一站式交付软件"等场景时使用。核心能力：派活（dispatch.py，豆包→WorkBuddy API 直连）、任务队列（poll_tasks.py，WorkBuddy→豆包 文件信箱）、git+inbox 通信协议、P0/P1/P2 三级审核、收敛判定、定时自动审核、打包/手册/交付归档。适用于软件开发中"写代码/改 bug/补测试/审核/重构/提交归档/打包交付"类任务的自动闭环，两方角色可互换。
---

# D2W 双 AI 协作开发闭环（豆包 ⇄ WorkBuddy）

两个 AI 通过 **git + inbox 文件信箱**协作：一方派活/审核，另一方干活/改错，循环往复直到收敛。**角色可互换**——豆包指挥 WorkBuddy，或 WorkBuddy 让豆包干活，都用同一套协议。

## 〇、两种模式（先判断方向）

| 模式 | 谁干活 | 谁派活/审核 | 用什么 |
|---|---|---|---|
| **A：豆包 → WorkBuddy** | WorkBuddy | 豆包 | `scripts/dispatch.py`（API 直连，全自动） |
| **B：WorkBuddy → 豆包** | 豆包 | WorkBuddy | 任务队列（`inbox/tasks/`）+ `scripts/poll_tasks.py` |

- 模式 A：豆包直接派任务给 WorkBuddy headless CLI，拿到结果后审核，写意见再派修
- 模式 B：WorkBuddy 把任务写成任务单放进 `inbox/tasks/`；豆包定时/按需轮询，处理完写结果到 `inbox/results/`，WorkBuddy 读取
- 混用：同项目可 A/B 并行（不同工作区），或一方干活另一方审核

## 一、准备（一次性，两模式共用）

1. **环境验证**：WorkBuddy 桌面版运行并登录；`python scripts/dispatch.py --status` 应打印 `token: 有效`（无效/401 见 references/troubleshooting.md §4，提取方式见 setup.md §5）
2. **项目初始化（推荐一条命令）**：
   ```bash
   python scripts/init_project.py D:\path\新项目 --with-templates
   # 一次完成：建目录 + git init + 仓库级身份 + .gitignore + inbox/tasks+results + 复制派活桥 + 复制模板
   # 已有 PRD 时直接生成 CHECKLIST 草稿：
   python scripts/init_project.py D:\path\新项目 --with-templates --prd D:\path\PRD.md
   ```
   - 手工方式（等价）：`git init` + `git config user.name "workbuddy-agent"` / `git config user.email "agent@local"`（新仓库必做，否则 commit 报错）+ `.gitignore` 含 `.cache/`、`_*.out`、`__pycache__/` + 建 `inbox/tasks`、`inbox/results` + 复制 `scripts/dispatch.py`、`scripts/poll_tasks.py` 到项目根
3. **写契约**：用 `assets/templates/PRD.template.md` 写 PRD.md（需求）；CHECKLIST.md 可手工写或按 PRD 自动生成：
   ```bash
   python scripts/gen_checklist.py <PRD.md> --out CHECKLIST.md   # 提取功能点生成草稿，再人工增删核对
   ```
4. **（可选）定时任务**：按 `assets/templates/cron_query.template.md` 建每小时 cron（心跳 + 审核/轮询 + 强制汇报）

> 细节：references/setup.md（环境与认证）、references/methodology.md（完整方法论与双向规则）

## 二、模式 A：豆包派活 → WorkBuddy

### 派活（甲方）
```bash
python dispatch.py "在 <cwd> 目录：<任务>。要求：1) <功能点>；2) 完成后 python -m py_compile <文件> 确认语法；3) git commit，提交信息 '<信息>'。不要修改 <禁区>。" --timeout 300
```
**任务文本四要素**：明确 cwd / 做什么 / 验收要求（编译、commit）/ 边界（禁区）。指令越具体产出越好。
**第五要素（GUI/核心逻辑必带）**：要求乙方**附带 selftest**（关键函数+边界+异常各至少 1 条，写完先跑通再 commit）——审核直接跑，不只看 py_compile。样例见 `assets/templates/selftest.example.md`。
**安全边界（v1.5.0 起默认启用）**：任务文本含危险命令模式（删除/格式化/关机/清注册表/盘符级删除）会被脚本**拒绝派活**；确属安全任务加 `--danger-allow` 显式放行。详见 methodology §5.21。
- `--debug`：SSE 读不到结果时看原始事件
- `--status`：查 token / serve / CLI 路径 / 默认模型
- `--smoke`：**一条命令跑冒烟自检**（环境检查 → 派最小任务 → 验证产物与 commit 落盘）；升级 WorkBuddy / 换机后必跑
- `--stop`：停当前端口 serve；`--stop-all`：清理缓存下所有端口 serve（孤儿进程）
- `--list-runs [--limit N] [--check]`：查派活历史与 run 活跃状态（记录在 .cache/runs.json）
- `--queue tasks.txt`：批量派活（每行一个任务，可带 `[model=xxx]`，`#` 注释）；结束打印成功/失败汇总
- `--auto-review`：派活结束后自动生成审核草稿 `inbox/review_roundN.md`（自动完成变更统计 + py_compile，AI 只填判断）→ 审核管道化，见 methodology §5.22
- 换机/换项目：环境变量 `WB_CLI_PATH` / `WB_PORT` / `WB_PROJECT` / `WB_CACHE`；CLI 路径缺失时**自动探测**（WB_CLI_PATH → 常见安装目录 → **跨盘符全盘扫描 C~Z** → 进程定位兜底，换笔记本/换盘符零配置）
- **多项目并发**：同 serve 多 cwd 已支持；重度并行换端口（`WB_PORT=51742`），serve.pid/log 已按端口隔离，详见 methodology §5.19

**模型选择（默认 glm-5.3，一句话可切换）**：
- 默认模型：`glm-5.3`（GLM 旗舰，复杂软件工程/长程 Agent，1M 上下文；环境变量 `WB_MODEL` 可改全局默认）
- **派活时切换**（优先级：`--model` 参数 > 任务文本 `[model=xxx]` > `WB_MODEL`）：
  - 参数方式：`python dispatch.py "任务..." --model kimi-k3-1`
  - 文本方式：`python dispatch.py "[model=kimi-k3-1] 任务..."`（任务文本开头一句即可，脚本会自动剥离标记）
- 常用模型速查（完整清单与积分倍率见 `references/setup.md §9`）：

  | 模型 id | 定位 | 备注 |
  |---|---|---|
  | `glm-5.3` | **默认**旗舰：复杂软件工程/长程 Agent | 1M 上下文 |
  | `deep-model` | 官方「极致」档：深度与准确性优先 | 复杂分析 |
  | `kimi-k3-1` | 最强长程自主/前端，最贵档 | 1M 上下文 |
  | `hy4-preview` | 腾讯混元4 思考模型 | 960K 上下文 |
  | `step-5-preview` | 阶跃旗舰基模 | 免费档，1M |
  | `deepseek-v4-pro` | DeepSeek 旗舰 | 1M |
  | `space-bunny` | 速度+编码强、匿名模型 | 便宜档 x0.08 |

**一句话切换话术（直接照抄）**：
- **默认**（不写任何东西 = glm-5.3）：`派活默认就用 glm-5.3，不用特别说明`
- **对豆包说**（自然语言）：`这次用 kimi-k3-1 模型派活：<任务内容>`
- **任务文本开头标记**（写进任务里，脚本自动剥离）：`[model=kimi-k3-1] <任务内容>`
- **命令行参数**：`python dispatch.py "<任务内容>" --model kimi-k3-1`
- 一句对照：`[model=glm-5.3]` 默认旗舰 / `[model=kimi-k3-1]` 最强长程最贵 / `[model=deep-model]` 深度极致档 / `[model=hy4-preview]` 混元思考 / `[model=step-5-preview]` 免费档 / `[model=space-bunny]` 快而便宜
- 优先级：`--model` 参数 > 任务文本 `[model=xxx]` > `WB_MODEL` 环境变量 > 默认 `glm-5.3`
- 注意：`credits` 倍率是服务端积分计量（非桌面显示）；通道暂不扣桌面积分属观察事实，别规模化滥用

**分模块派活（大任务铁律，防断连丢进度）**：
- 一次只派 **1～2 个文件** 的活：core 引擎 → ui 框架 → 测试 → 集成，逐模块推进
- 任务文本**必须要求每写完一个模块立即 commit**（提交信息写模块名），禁止攒到全部写完再提交
- 原因：SSE 随时可能断（实测踩过：写了一半 core+ui 被断、无 commit，进度全丢）。每模块一 commit，断了就从上次 commit 续跑，最多损失一个模块
- 断点续跑：先 `git log --oneline` 看已到哪个模块，再派"继续写下一个模块 XX"，并明确"从上次 commit 之后继续，不要重写已提交部分"
- 验收同理：按模块逐个审核（每模块 py_compile + 对应功能实测），别等全写完才审

**界面质量硬性要求（GUI 类任务必带，派活文本直接附上）**：
- **布局统一（默认 Wifibond 风格）**：多页面工具默认「左侧深色导航 + 右侧浅色内容 + 卡片化」布局，详细规范见 `assets/ui_spec/UI_LAYOUT_SPEC.md`（色板/字号/间距令牌、组件规范、响应式、检查清单）；产品形态确不适合（单窗小工具/浮窗/Web）才换风格，**先向用户说明理由，且同一软件内全程统一，禁止混搭**
- **布局合理**：控件对齐、间距统一、窗口尺寸适配内容，缩放/高 DPI（125%/150%）不遮挡
- **美化**：配色协调有层次（深色导航 + 浅色内容 + 橙/蓝/绿/红语义强调色）、圆角、留白适度
- **按钮整齐划一**：同尺寸、同间距、对齐网格，五级语义底色（primary/info/success/danger/secondary），有 hover/按下反馈
- **字体显示完全无遮挡**：微软雅黑层级（20/12/10/9pt），文字不截断、不重叠，长文本自动换行或自适应，字号有层级
- **文本排版无孤行**（v1.5.9 新增，代码产出软件最高频缺陷）：所有多行文本必设 `wraplength` 随窗口宽度刷新；段落末尾不孤字/孤行；正文 `justify=LEFT` 而非 CENTER；label 与控件同基线不重叠；不截断不省略号（详细规范见 `assets/ui_spec/UI_LAYOUT_SPEC.md §4.4`）
- **关于页赞助弹窗（v1.5.4 起必带，v1.5.8 细化）**：
  - 按钮：关于页底部版权信息上方，文案「☕ 赞助作者」，secondary 浅底深字（bg=#f1f5f9, fg=正文色, relief=SOLID, bd=1, padx=16, pady=6, cursor=hand2, hover activebg=#e2e8f0）
  - 弹窗：Toplevel 模态，默认 1060×880，minsize 720×560，resizable(True,True)，屏幕居中（不跟随按钮），transient+grab_set
  - 内部：顶部 ☕ 36pt 橙色 → 主文案"如果你喜欢这个工具"（section+4 加粗居中）→ 副文案"可以请作者喝杯咖啡，感谢赞助"（body+2 灰）→ 中间码图区 expand=True fill=BOTH（两列等宽 grid，480×480 thumbnail LANCZOS 白底 bd=2，下方「📱 支付宝扫码」/「💬 微信扫码」）→ 底部「⤢ 放大」+「关闭」并排居中
  - 一键放大：点「⤢ 放大」保存 geometry → `dlg.state("zoomed")` 全屏 → 按钮变「🗗 还原」；再点恢复 geometry；闭包存 `state={"zoomed":False,"normal_geom":...}`
  - 码图路径：项目里读 `assets/alipay.jpg` / `assets/wechatpay.jpg`（派活时把技能包 `assets/money_code/{alipay,wechatpay}.jpg` 复制进项目 `assets/`），用 `_resource_path()`（PyInstaller `_MEIPASS` 兼容），打包 `--add-data "<项目根>/assets;assets"`
- **验收方式**：实际运行 + 截图目检逐项过（布局/遮挡/对齐/DPI），发现"布局错乱/文字截断/按钮不对齐"按 P0/P1 报
- CHECKLIST 用 L 组（界面质量 GUI 必检，L1~L11 含布局统一与赞助按钮）逐条打勾

### 审核（甲方）
0. **先验证 commit 是否真的产生**：`git log --oneline -3`——agent 可能写完代码却漏 commit（真实踩过），无 commit 视为未完成，进 P1
1. `git rev-parse HEAD` vs `inbox/last_reviewed_commit.txt` 判断有无新产出
2. 读所有产出文件 + 对照 CHECKLIST.md 逐条打勾
3. 跑验证：py_compile、**乙方自带 selftest**、关键路径实测（先区分"环境缺依赖"与"真 bug"）
4. **5 维评分**（正确性/可维护性/性能/安全/界面，各 1-5 分；**非 GUI 项目界面维记 N/A 并从分母剔除；收敛线 = 实际评维数 × 4**；锚定标准见 methodology §5.25 / review_round.template.md）
5. 用 `assets/templates/review_round.template.md` 写 `inbox/review_roundN.md`（N 递增）：
   - 总体结论 + **评分表** + 逐条问题（**现象 / 根因 / 修改方向**）+ 验收标准
   - 分级：**P0** 阻塞必须改 / **P1** 该改 / **P2** 建议
   - **关键模块填"复审"段**（双审/交叉审核，见 methodology §3.6）：另一模型 `[model=xxx]` / WorkBuddy 模式 B / 用户，独立审或抽查 30%
   - 无 P0 → 末行写 `STATUS: NO_P0`
6. 更新基线：当前 commit hash 写入 `inbox/last_reviewed_commit.txt`

### 派修与收敛
- 派修：`python dispatch.py "请阅读 <cwd>/inbox/review_roundN.md 并按意见修改。改完 py_compile + 跑 selftest + git commit + 汇报 hash。"`
- 收敛：**连续两轮 `STATUS: NO_P0` → 宣布收敛**，告知用户可过目（建议同时总分 ≥ 收敛线）
- 有 P0 → 继续循环（每轮 N+1）

## 三、模式 B：WorkBuddy 派活 → 豆包

### WorkBuddy 侧（来源方）
- 用 `assets/templates/task_request.template.md` 把任务写成 `inbox/tasks/NNN_<简述>.md`（NNN 三位序号递增）
- 任务单写明：需求 / 验收标准 / 参考文件 / 禁区

### 豆包侧（处理方）
1. 轮询：`python poll_tasks.py`（列出 `inbox/tasks/` 中序号大于 `inbox/last_task_processed.txt` 的任务）
2. 逐个处理：读任务单 → 执行（写代码/审核/查资料/润色等）→ 用 `assets/templates/task_result.template.md` 写结果到 `inbox/results/NNN_<同简述>.md`
3. 标记：`python poll_tasks.py --mark NNN`（更新 last_task_processed.txt，防重复）

### 工作流触发方式
- **按需**：用户说"看下任务队列" → 跑 poll_tasks.py 处理
- **定时**：建每小时 cron 任务（模板 B，见 assets/templates/cron_query.template.md），到点自动轮询处理并汇报
- WorkBuddy 侧由用户告知约定：任务写 inbox/tasks/，结果读 inbox/results/

## 四、公共通信协议（两模式通用）

| 文件/约定 | 谁写 | 内容 |
|---|---|---|
| `inbox/review_roundN.md` | 审核方 | 第 N 轮审核意见（N 递增） |
| `inbox/last_reviewed_commit.txt` | 审核方 | 最近已审核 commit hash（基线） |
| `inbox/tasks/NNN_*.md` | 来源方 | 任务单（模式 B） |
| `inbox/results/NNN_*.md` | 处理方 | 结果单（模式 B，NNN 与任务单一致） |
| `inbox/last_task_processed.txt` | 处理方 | 已处理到的任务序号（防重复） |
| `inbox/audit_heartbeat.txt` | 定时任务 | 心跳留痕（用户确认任务在跑） |
| git commit | 干活方 | 一切产出的可追溯记录（提交信息写清做了什么） |

**铁律**：审核方只审不改代码；干活方无权改 PRD.md / CHECKLIST.md / 审核基线；结果单与任务单序号必须一致。

## 五、一站式交付（开发收敛后必做）

**开发收敛（连续两轮 NO_P0）只是代码完成。一站式交付 = 让用户拿到就能用的成品**，五步走完：

### 5.1 打包 EXE（派活）
```bash
python dispatch.py "在 <cwd> 目录：用 PyInstaller 打包 <入口.py>，要求：1) --onefile --noconsole --icon <图标.ico> --clean（如有隐式依赖加 --hidden-import <模块>）；2) 产物放 <cwd>/dist/，双击即用、无黑窗、体积合理；3) py_compile 确认 + git commit，提交信息 '<信息>'。不要修改 <禁区>。" --timeout 600
```
- 启动慢/体积超大 → 改用 `--onedir`（目录版）；需要安装程序时配 Inno Setup（见 5.2）
- 打包失败先查 troubleshooting §18（--clean、图标、隐式导入、Nuitka/MinGW）

### 5.2 安装程序（Inno Setup，可选但推荐）
- 派活：写 Inno Setup 脚本（应用名/版本号/安装目录/桌面快捷方式/开始菜单/卸载入口/中文不乱码），编译出 `<产品>_Setup.exe` 放 `dist/`
- 验收：安装/卸载成功、快捷方式正确、卸载干净无残留

### 5.3 产品使用手册（派活，模板 USER_MANUAL.template.md + 样式规范 USER_MANUAL_PDF_SPEC.md）
- 内容：软件简介 / 安装与启动 / 快速上手 / 功能详解（逐功能带操作步骤与示例）/ 数据与格式 / 设置 / FAQ / 快捷键 / 版本与支持
- **产物形态（硬性）：`<产品名>_使用手册.pdf`**，样式按 `assets/ui_spec/USER_MANUAL_PDF_SPEC.md`：
  A4 纵向、封面深蓝 #1F3864 主标题 + 版本信息块、目录圆点线右对齐页码、章节标题深蓝加粗、正文 12pt、表格蓝底表头、页眉页脚页码
- 生成路径（推荐 A）：python-docx 排版 → Word COM 转 PDF（docx 源同留）；备选 HTML → Edge headless 打印 PDF
- 交付前审核方**在成品 PDF 上**逐条过验收清单（PDF_SPEC §8）：封面完整、目录页码真实、中文无乱码、表格不截断、内容与软件完全一致（GUI 软件必须有真实截图）

### 5.4 交付验收（审核方必做，别只看代码）
- 在真实环境（Win10/11）跑打包后的 EXE 关键路径，不是只跑源码
- 杀软不误报；版本号与 CHANGELOG 一致；图标/应用名正确
- **界面质量 L 组在成品上复检**——打包后字体/布局可能变化（资源未打进包是高频坑）

### 5.5 归档与交付（收尾）
- 写 `<cwd>/DOD.md`（Definition of Done，模板 DOD.template.md）：交付物清单（EXE/安装包/手册/源码 commit hash）+ 验证方式与结果 + 已知缺口
- 最终产物 commit 归档
- 交付用户：产物路径 + 验证方式 + 已知缺口，一次性给全

## 六、定时自动审核/轮询（可选）

- 建每小时 cron 任务（`0 * * * *`，按 doubao-cron-scheduler 规范）
- query 直接取 `assets/templates/cron_query.template.md` 改写（模板 A 审核 / 模板 B 轮询）
- 三要素：**心跳留痕 → 干活（审核或轮询）→ 强制汇报**（禁止静默）
- 汇报模板（2-3 行）：触发时间 / 有无新产出 / P0-P1-P2 数量 或 "无新提交，任务正常运行，下次检查 {下一整点}"

## 七、常见坑（先查 references/troubleshooting.md）

| 坑 | 秒解 |
|---|---|
| 派活报 **502** / status 假报"运行中" | 环境代理劫持 loopback → 脚本已用空 ProxyHandler 直连；协议见 troubleshooting §14 |
| 派活报 **401 AUTH_REQUIRED** | 新版 CLI 的 `--auth none` 失效 → 脚本已注入 `CODEBUDDY_GATEWAY_AUTH=none`；见 §15 |
| 派活被拦"危险命令" | 任务文本含 rm/format/关机/注册表删除等模式 → 默认拒绝；确认安全加 `--danger-allow`；见 methodology §5.21 |
| CLI 找不到 | 脚本自动探测（常见安装目录 + 跨盘符全盘扫描 + 进程定位）；仍失败设 `WB_CLI_PATH` 或先启动 WorkBuddy 桌面版；见 troubleshooting §20 |
| serve 孤儿进程/端口残留 | `python dispatch.py --stop-all` 一次清理缓存下所有端口；见 troubleshooting §22 |
| commit 卡住/无文本输出 | serve 必须 `--permission-mode auto`（dispatch.py 已内置） |
| commit 报身份缺失 | 仓库级配 user.name/email |
| token 无效 | 桌面版在运行？删 `.cache/wb_token.txt` 重新提取 |
| 桌面版与 CLI 冲突 | 一方活跃时另一方别碰同一仓库；并行用独立沙盒 |
| selftest 失败 | 先判断环境缺库还是逻辑 bug |
| 任务队列序号对不上 | 任务单/结果单必须同一 NNN；完成后 `--mark NNN` |
| 队列任务"凭空消失" | `--mark` 支持乱序（已修为集合语义）；旧基线文件按 §16 迁移 |
| SSE 断了 / 只写了一半没 commit | 分模块派活（一次 1~2 文件）+ 每模块立即 commit；断了从上次 commit 续跑；见 methodology §5.14 / troubleshooting §17 |
| 桌面积分不扣 | CLI/API 通道与桌面积分分离（实测观察，非官方承诺）；依赖桌面版登录态，别规模化滥用；见 methodology §5.15 |
| 打包失败（--clean/图标/隐式导入/杀软误报） | 派活给全 PyInstaller 参数；按 troubleshooting §18 排查 |
| 打包后界面错位/字体丢失 | 打包版必须重跑 L 组界面验收（资源/字体未打进包是高频原因） |
| 需求中途变更 | 先更新 PRD/CHECKLIST（用户确认）再派活，不口头加需求；见 methodology §5.18 |

## 八、边界

- **适合**：写代码、改 bug、补测试、审核、重构、提交归档、跑验证、查资料/润色（模式 B）
- **不适合**：真实 GUI 交互验收（真鼠标划词、听声音）、外部账号/支付/危险命令（默认拦截但 auto 权限仍应慎用）、产品决策

## 资源索引

```
scripts/
  dispatch.py       模式 A 派活桥（token 提取 + serve + 派任务 + 读结果 + 模型选择 + 危险命令拦截
                    + CLI 自动探测 + --queue/--list-runs/--stop-all/--auto-review/--smoke）
  poll_tasks.py     模式 B 任务队列轮询（列任务 / 标记已处理 / 撤销标记 / 重置）
  init_project.py   项目初始化向导（git+身份+.gitignore+inbox+复制脚本+模板，一条命令）
  gen_checklist.py  按 PRD.md 自动生成 CHECKLIST.md 草稿（提取功能点）
  sync_copies.py    副本同步（d2w -> do2wo/doubao-workbuddy-collab，防宿主旧快照复活）
  extract_jwt.py    备用：全量 token 扫描
references/
  setup.md          环境设置与认证机制（CLI 入口、token、serve、API 格式、鉴权开关、模型清单）
  methodology.md    完整方法论（准备清单、协议、流程、红线、双向规则、安全边界、管道化、评分锚定、冒烟自检）
  troubleshooting.md 真实踩坑记录（含已走过的死路清单）
assets/templates/
  PRD.template.md         需求文档模板
  CHECKLIST.template.md   验收清单模板（A~Q 组，含界面 L / 打包 M / 安装 N / 手册 O / 测试 P / 交付 Q）
  review_round.template.md 审核报告模板（5 维评分锚定表 + 复审段）
  selftest.example.md     selftest 样例（轻量断言 + pytest 两种形态，派活第五要素配套）
  task_request.template.md 任务单模板（模式 B）
  task_result.template.md  结果单模板（模式 B）
  cron_query.template.md   定时任务 query 模板（A 审核 / B 轮询）
  USER_MANUAL.template.md  产品使用手册模板（一站式交付 §5.3，内容结构）
  DOD.template.md          交付完成单模板（Definition of Done，一站式交付 §5.5）
assets/ui_spec/
  UI_LAYOUT_SPEC.md        默认 UI 布局规范（Wifibond 风格：左导航+右内容+卡片化+令牌）
  USER_MANUAL_PDF_SPEC.md  产品使用手册 PDF 样式规范（封面/目录/正文/表格/页眉页脚 + 生成路径 + 验收清单）
CHANGELOG.md        版本变更记录
```

## 九、冒烟自检（升级 WorkBuddy / 换机后必跑）

**推荐一条命令**（v1.5.3 起）：
```bash
python scripts/dispatch.py --smoke --cwd <测试项目路径>
```
自动完成：环境检查（token/CLI/serve）→ 派最小任务（建 smoke_test.txt + commit）→ 验证产物文件与 commit 真实落盘。退出码 0=PASS，1=FAIL。

**手动三步（等价）**：
1. `python scripts/dispatch.py --status` → 应打印 `token: 有效`、`CLI: <路径>`（serve 未运行也正常，派活时会自动拉起）
2. 派一个最小任务（建一个文件 + commit；建议带 `--auto-review` 验证审核草稿生成）
3. 验收：产物文件与 `git log` 的 commit 都真实存在；`inbox/review_roundN.md` 草稿生成 → 闭环可用
4. 任一失败 → 先查 `references/troubleshooting.md` §14（502/代理）、§15（401/鉴权）、§20（CLI 找不到）
