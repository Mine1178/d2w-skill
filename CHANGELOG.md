# Changelog — D2W 双 AI 协作开发闭环

本文件记录 Skill 的版本变更。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。


## [1.5.1] — 2026-10-12

CLI 自动探测跨盘符化（换笔记本/换盘符零配置）。

### Changed

- `scripts/dispatch.py`：新增跨盘符全盘扫描兜底——枚举存在的 C~Z 盘符，
  对每个盘套用常见安装层级（LenovoSoftstore / Program Files / 用户级 Programs / 一二级目录），
  接在默认 glob 之后、进程推导之前
- `references/setup.md` §1.2、`references/methodology.md` §5.23：探测顺序与换机说明同步

### Verified

- py_compile 通过；模拟"默认路径失效"实测：find_cli 跨盘扫描仍命中
  `E:\LenovoSoftstore\Install\WorkBuddy\...`（盘符枚举 C/D/E 正常）
- 换机流程：整包复制 `.user_skills\d2w` → 新机装好 WorkBuddy 并登录 →
  `--status` 自动定位 CLI → 最小派活冒烟（本机无法验证新机，逻辑经路径失效模拟验证）


## [1.5.0] — 2026-10-12

三大方向落地（安全白名单 / 派活-审核管道化 / 初始化向导+技能 git 化）+ P1/P2 全补齐。

### Added（三大方向）

- **命令白名单 / 安全边界（默认启用）**：`dispatch.py` 派活前对任务文本做危险命令拦截
  （删除/格式化/关机/注册表/盘符级删除等正则模式），命中即拒绝派活（exit 2）；
  `--danger-allow` 显式放行安全任务（methodology §5.21、troubleshooting §21）
- **派活→审核管道化**：`dispatch.py --auto-review`——SSE 结束后若出现新 commit，
  自动生成 `inbox/review_roundN.md` 审核草稿（含变更统计 + 全项目 py_compile 结果），
  AI 只填判断，不再从 0 起步（methodology §5.22）
- **初始化向导**：新脚本 `init_project.py`——一条命令完成 建目录/git init/仓库级身份/
  .gitignore/inbox 信箱/复制派活桥/复制模板/（--prd 时生成 CHECKLIST 草稿）（SKILL.md §一）
- **技能自身 git 化**：`d2w/` 目录纳入 git 管理（首次 commit `5eaa1ae`），可 diff/回滚/追溯；
  副本同步脚本 `sync_copies.py`（d2w → do2wo/collab，防宿主旧快照复活）（methodology §5.24）

### Added（P1/P2 补齐）

- **CLI 路径自动探测**：默认路径缺失时按 WB_CLI_PATH → 常见安装目录 glob → 进程推导 依次尝试，
  `--status` 直接显示解析到的 CLI 路径（methodology §5.23、setup §1.2、troubleshooting §20）
- **--stop-all 孤儿清理**：一次清理缓存目录下所有端口 serve（serve.pid_<PORT> 逐个 kill）
- **serve.log 日志轮转**：超 5MB 自动备份 .old，不再无限增长
- **--queue 批量结果汇总**：结束打印成功/失败 + 失败序号清单
- **评分锚定标准**：review_round 模板内置 1/3/5 分锚定表；非 GUI 项目界面维 N/A 并从分母剔除；
  收敛线 = 实际评维数 × 4（methodology §5.25）
- **selftest 样例模板**：新增 `assets/templates/selftest.example.md`（轻量断言 + pytest 两种形态）
- **CHECKLIST 按 PRD 生成**：新脚本 `gen_checklist.py`——提取 PRD 功能点生成 CHECKLIST.md 草稿，
  交互类自动标"人工"（init_project --prd 时自动调用）

### Changed

- `SKILL.md`：§一 初始化改用 init_project.py；派活段加 --auto-review/--danger-allow/--stop-all/
  CLI 自动探测/安全边界；审核段评分口径更新（豁免+收敛线）；资源索引与冒烟自检同步
- `references/methodology.md`：§1.2/1.4 向导化；§3.2/3.5 评分口径同步；新增 §5.21-5.25
- `references/setup.md`：§1.2 自动探测、§3 输出示例、§4.1 日志轮转、§6 WB_CACHE、§7 危险命令拦截
- `references/troubleshooting.md`：新增 §20（CLI 找不到）、§21（危险命令误伤）、§22（孤儿 serve）、§23（副本旧快照）

### Verified

- 6 个脚本 py_compile 全过；quick_validate = Skill is valid!
- d2w 技能包 git 化完成（commit 5eaa1ae）
- 实测见本轮记录：init_project 生成测试项目、gen_checklist 从 PRD 生成草稿、危险命令拦截拒绝、
  --status 显示 CLI、--stop-all、副本清理确认（do2wo/collab 已不存在，仅剩 d2w）


## [1.4.0] — 2026-10-12

双 AI 协作闭环增强：**run 状态跟踪 / 批量派活 / 多项目并发 / 5 维评分 / 双审交叉审核 / 模块自测强制**（对应完善建议 1-6）。

### Added

- **dispatch.py --list-runs**：派活自动记录到 `.cache/runs.json`（runId/时间/cwd/模型/摘要，最多 200 条），
  `--list-runs [--limit N] [--check]` 查历史并逐个查 run 活跃状态（active/completed/http_N）
- **dispatch.py --queue tasks.txt**：批量派活，每行一个任务（可带 `[model=xxx]` 标记，`#` 注释），逐个派发执行
- **多项目并发**：serve.pid / serve.log 按端口隔离（serve.pid_<PORT>），支持 `WB_CACHE` 环境变量；
  同 serve 多 cwd 已支持，重度并行换端口即可（methodology §5.19）
- **5 维加权评分**：审核报告内置评分表（正确性/可维护性/性能/安全/界面各 1-5 分），总分 <20/25 = 未达收敛线
- **双审 / 交叉审核**：关键模块必做，复审方 = 另一模型 `[model=xxx]` / WorkBuddy 模式 B / 用户；
  独立双审或抽查 30% 复核，分歧按证据裁定（methodology §3.6）
- **模块自测强制**：派活任务文本第五要素——GUI/核心逻辑模块必须附带 selftest（关键函数+边界+异常各至少 1 条），审核直接跑

### Changed

- `SKILL.md`：派活段新增 --list-runs/--queue/多项目并发说明与第五要素；审核段升级为评分+双审；
  派修模板加"跑 selftest"；收敛建议总分 ≥20
- `references/methodology.md`：§3.1 派活加自测/队列/跟踪，§3.2 加 5 维评分，§3.5 加评分收敛线，
  §3.6 双审交叉审核，§5.19 多项目并发，§5.20 派活队列与 run 跟踪
- `assets/templates/review_round.template.md`：新增 5 维评分表 + 复审段（双审必填）+ 评分收敛说明
- `assets/templates/CHECKLIST.template.md`：汇总区新增 5 维评分 / 复审记录 / selftest 执行结果

### Verified

- `dispatch.py` py_compile 通过；`--help` 正常（--queue/--list-runs/--limit/--check 齐全）
- 实测见本轮记录：--queue 批量派活 + --list-runs --check 状态查询（复测项目 do2wo-test）


## [1.3.4] — 2026-10-12

技能更名：**Do2Wo → D2W**（D2W = Do-to-WorkBuddy / WorkBuddy-to-Do，好记、无同名冲突）。

### Changed

- 技能目录 do2wo → **d2w**（小写，符合命名规范，quick_validate 零警告）
- frontmatter 
ame: d2w；全文 Do2Wo → D2W（SKILL.md / CHANGELOG / references / templates）
- 清理遗留副本 doubao-workbuddy-collab 与旧目录 do2wo：豆包客户端有技能目录自动同步守护（删除后约 45s 自动重建），
  故改为**内容同步一致**——旧入口的 SKILL.md/脚本/模板全部覆盖为 d2w 最新版，任何入口触发都是新版逻辑

### Notes

- GitHub 检索确认：**无 Do2Wo / D2W 同名项目**，命名无冲突（2026-10-12 检索）
- 旧路径 .user_skills\do2wo 已失效，引用请改用 .user_skills\d2w

## [1.3.3] — 2026-10-12

产品使用手册升级为 **PDF 格式 + 精美样式**（参照两份实测手册提炼的规范）。

### Added

- `assets/ui_spec/USER_MANUAL_PDF_SPEC.md`：**产品使用手册 PDF 样式规范**——
  总体设计量化表（A4 纵向、页边距、深蓝 #1F3864 主色/灰 #595959/黑、微软雅黑+Arial 字号层级、行距）；
  封面版式（小标签+深蓝主标题+副标题+蓝色分隔线+版本信息块）；目录版式（圆点线右对齐页码+层级缩进）；
  正文版式（章/节/小节标题规格、操作步骤、蓝底表头表格+表题编号、截图图注、页眉页脚页码、封面无页码）；
  章节结构九章模板；生成技术路径（A：python-docx→Word COM 转 PDF；B：HTML→Edge headless 打印 PDF）；
  派活模板（可直接贴给 WorkBuddy）；成品 PDF 验收清单 8 条。
- `SKILL.md` §5.3 产品使用手册：产物形态改为**硬性 PDF**（`<产品名>_使用手册.pdf`），引用 PDF_SPEC，
  验收在成品 PDF 上逐条过；资源索引新增 PDF_SPEC。
- `assets/templates/USER_MANUAL.template.md`：新增交付形态说明（最终产出 PDF、样式按 PDF_SPEC、
  模板管内容结构、PDF_SPEC 管排版样式）。

### Changed

- 手册产物从 `USER_MANUAL.md` 升级为 `<产品名>_使用手册.pdf`（docx 源同留，便于修订）。

### Verified

- 样式提炼自实测手册：①《通信工程勘察报告工具箱使用指南.pdf》（A4，封面蓝线+双语标题+编制单位信息块、
  圆点线目录、蓝底表头）②《地址坐标转换工具使用指南.docx》（深蓝 1F3864 标题体系、中文"一、（一）"序号、
  编号表格"如表 N 所示"）。

## [1.3.2] — 2026-10-12

派活模型可选：默认模型定为 **glm-5.3**，派活时可一句话切换任意模型。

### Added

- `scripts/dispatch.py` 新增模型支持：
  - 默认模型 `glm-5.3`（环境变量 `WB_MODEL` 可改全局默认）
  - `--model <id>` 参数切换模型
  - **任务文本开头 `[model=<id>]` 一句话切换**（如 `"[model=kimi-k3-1] 写一个工具..."`，脚本自动剥离标记）
  - 派活请求 body 携带 `model` 字段（源码确认 `requestOptions.model` 优先于默认）
  - `--status` 额外显示当前默认模型
- `references/setup.md` 新增 **§9 模型选择与清单**：派活模型来源、三种切换方式、15 个常用模型 id 表（含积分倍率）、注意红线
- `SKILL.md` 派活小节新增「模型选择」段落（默认 glm-5.3 + 切换语法 + 常用模型速查表）
- `references/methodology.md` §3.1 派活要素新增第 5 条（可选模型，指向 setup.md §9）

### Changed

- 派活默认模型从"服务端默认/团队指定"改为 **glm-5.3**（可控、可切换）

### Verified

- `python -m py_compile dispatch.py` 通过
- `dispatch.py --help` / `--status` 正常（显示默认模型）
- **三次真实派活实测**（复测项目 `D:\Desktop\SD\do2wo-test`）：
  - 默认模型（glm-5.3）：任务完成，commit `5033f98`（model_test.py）
  - `[model=kimi-k3-1]` 文本标记：标记正确剥离、任务完成，commit `ea37f2e`（model_test2.py）
  - `[model=deepseek-v4-pro]` + `--debug`：SSE 完整事件、任务完成，commit `7f2962c`（model_test3.py）
- 模型生效反查结论（如实记录）：CLI run 不落本地 session 记录（workbuddy.db sessions 表仅记桌面/自动化会话），
  run 详情/SSE 无 model 字段 → 无法本地反查"实际模型"；生效依据 = CLI 源码请求指定优先 + 服务端 202 接受 + 任务正常执行。
  详见 setup.md §9.4。

## [1.3.1] — 2026-10-12

界面布局统一化：默认采用 Wifibond 布局风格（来源 `D:\Desktop\SD\11.Wifibond` 实测 v1.2.8 + Address Tool 家族设计语言）。

### Added

- `assets/ui_spec/UI_LAYOUT_SPEC.md`：**默认 UI 布局规范**（Wifibond 风格）——
  左导航+右内容框架（210/110/42px 常量、窗口尺寸、DPI）、风格选择决策表（多页面工具=默认；
  单窗小工具=居中表单；浮窗=无边框圆角；Web=顶部导航）、设计令牌（16 色 C_* 常量/微软雅黑
  字号层级/8pt 间距体系）、组件规范（页面头/卡片/表格/按钮五级/空状态/弹窗）、响应式与可访问性、
  验收清单（对应 CHECKLIST L1~L9）、新增界面自检 10 条。
- `SKILL.md` 界面质量硬性要求小节：新增「布局统一（默认 Wifibond 风格）」条款——不合适的形态
  换风格前先向用户说明理由，同一软件内全程统一禁止混搭。
- `assets/templates/CHECKLIST.template.md` L 组新增 **L9 遵循统一布局规范**（风格全程一致不混搭、
  令牌走常量无硬编码魔法值）。

### Changed

- SKILL.md 资源索引新增 `assets/ui_spec/UI_LAYOUT_SPEC.md`。

## [1.3.0] — 2026-10-12

一站式交付升级：闭环从"代码收敛"延伸到"用户拿到就能用的成品"。

### Added

- `SKILL.md` 新增 **五、一站式交付** 章节（五步：打包 EXE → 安装程序 → 使用手册 → 交付验收 → 归档交付），
  章节顺延（定时=六、常见坑=七、边界=八、冒烟=九）；description 增加打包/安装/手册/交付触发词。
- `assets/templates/USER_MANUAL.template.md`：产品使用手册模板（简介/运行环境/安装/逐功能操作/快捷键/FAQ/数据隐私）。
- `assets/templates/DOD.template.md`：交付完成单模板（Definition of Done：交付物清单/验收结果/已知缺口/使用说明）。
- `assets/templates/CHECKLIST.template.md` 新增 **M. 打包（EXE）**（M1~M6）、**N. 安装程序**（N1~N4）、
  **O. 使用手册**（O1~O4）、**P. 自动化测试**（P1~P3）、**Q. 交付归档**（Q1~Q2）共 5 组。
- `references/methodology.md` 新增 §5.17（一站式交付五步与产物位置约定）、§5.18（需求中途变更管理：先走契约→用户确认→再派活）。
- `references/troubleshooting.md` 新增 §18（PyInstaller 打包/Inno Setup 踩坑：隐式导入、--add-data、
  sys._MEIPASS 资源路径、打包版界面复检、杀软误报、中文乱码）、§19（需求中途变更）。

### Changed

- SKILL.md 常见坑表格补打包失败、打包版界面错位、需求中途变更三条秒解。

## [1.2.1] — 2026-10-12

界面质量纳入硬验收项（GUI 任务必带）。

### Added

- `SKILL.md` 派活章节新增**界面质量硬性要求**（GUI 类任务必带，可直贴派活文本）：
  布局合理（对齐/间距/尺寸适配/高 DPI 不遮挡）、美化（配色层次/圆角/留白）、按钮整齐划一
  （同尺寸同间距对齐网格/hover 反馈）、字体显示完全无遮挡（不截断不重叠/长文本自适应）；
  验收 = 实际运行 + 截图目检，问题按 P0/P1 报。
- `references/methodology.md` 新增 §5.16 界面质量是硬验收项：
  QuickTrans round5 教训（U-1 DPI 位置、U-2 译文残缺——界面 bug 光看代码发现不了）、
  CHECKLIST L 组逐条打勾、运行目检必跑、问题分级、高频坑（DPI 缩放/中文换行/窗口写死/字体回退）。
- `assets/templates/CHECKLIST.template.md` 新增 **L. 界面质量（GUI 必检）** 组共 8 条（L1~L8）。

## [1.2.0] — 2026-10-12

实施场景实证后的一次策略升级：解决"SSE 中断丢进度"与记录"积分行为观察"。

### Fixed — SSE 中断丢进度（实施项目必读）

- **任务只写了一半被 SSE 断掉、无 commit → 进度全丢**：一次派多个大文件（core 引擎 + ui 框架），
  agent 未到收尾 commit 就断连，已写内容不完整、git log 无新提交。
  **修复**：确立**分模块派活铁律**——一次只派 1～2 个文件（core → ui → 测试 → 集成 逐模块推进）；
  任务文本必须要求**每写完一个模块立即 commit**（提交信息写模块名），禁止攒到结尾一起交；
  断点续跑 = `git log --oneline` 确认已到哪个模块 → 派"从上次 commit 之后继续写下一个模块"。
  详见 methodology §5.14、troubleshooting §17。

### Added

- `references/methodology.md` 新增 §5.14（SSE 中断与分模块派活）、§5.15（CLI/API 通道与桌面积分分离的实测观察 + 风险红线）。
- `references/troubleshooting.md` 新增 §17（SSE 中断/写一半没 commit：症状、根因、分模块解法、断连判据）。
- `SKILL.md`：派活章节新增"分模块派活（大任务铁律）"小节；§六 常见坑表格补 SSE 断连与积分两条秒解。

### Changed

- 派活模板建议：大任务按模块拆解下发，验收按模块进行（不再"一次全写完再审"）。

### Verified

- 积分对照实测（2026-10-12）：派完整任务（写 hello_wb.py + commit `eb9a685`），WorkBuddy 桌面积分明细无消耗记录——记录为观察事实，非官方承诺。
- 全部文档变更后 `quick_validate.py` 校验通过（`doubao-workbuddy-collab` 目录）。

## [1.1.0] — 2026-10-10

复测（`D:\Desktop\SD\do2wo-test` 模式 A/B 全链路）后做的一次完整审计与修复。

### Fixed — 阻断性缺陷（不修则整套跑不起来）

- **派活 502 Bad Gateway**：环境里若设了 `HTTP_PROXY`/`HTTPS_PROXY`（如 WorkBuddy 自带本地代理），
  Python `urllib` 默认把连 `127.0.0.1:51741` 的请求也交给代理 → 502。
  更坑的是旧 `port_busy()` 把任何 `HTTPError` 都当"服务活着"，502 被误判为存活 → 跳过启动、直接派活失败。
  **修复**：所有 loopback 请求改用空 `ProxyHandler` 直连；`port_busy()` 把 502/503/504 视为不存活。
  详见 troubleshooting §14。

- **派活 401 AUTH_REQUIRED**：CLI v2.156+ 起 `--auth none` 会被 settings 的 gateway 配置 /
  内建默认（`password`）覆盖，服务端仍走 password 模式 → 派活 401。
  **修复**：启动 serve 时注入 `CODEBUDDY_GATEWAY_AUTH=none`（优先级最高）。
  判据：启动日志出现 `⚠ Authentication is DISABLED.`。
  详见 troubleshooting §15、setup §4.1。

### Fixed — 队列游标语义

- **`--mark` 乱序处理静默吞任务**：旧实现用"单个最大序号"当游标，任务 1/2/3/4/5 都在时直接
  `--mark 4`，再 poll 时 1/2/3 凭空消失。
  **修复**：改为"已处理序号集合"（`last_task_processed.txt` 存 `1,3,4` 逗号分隔），
  `--mark N` 只追加 N、不牵连其它序号；新增 `--unmark N`；脏值自动忽略。
  **向后兼容**：旧文件里是单个纯数字（如 `4`）时按集合 `{4}` 读。
  详见 troubleshooting §16。

### Added

- `scripts/poll_tasks.py --unmark N`：撤销指定序号的已处理标记；`--mark` 支持一次传多次。
- `references/methodology.md` 新增 §5.10（代理劫持 loopback）、§5.11（新版 CLI `--auth none` 失效）、
  §5.12（队列游标语义）、§5.13（升级/换机后的冒烟自检清单）。
- `references/troubleshooting.md` 新增 §14/§15/§16 三条实证踩坑。
- `SKILL.md` §六 常见坑表格补三条新症状的秒解。
- `.gitignore`：排除 `.cache/`、`__pycache__/`、`*.log` 等运行期产物，保持技能包干净。

### Changed

- `references/setup.md` §4.1 启动参数更新为含 `CODEBUDDY_GATEWAY_AUTH=none`，并补充
  健康检查的判据表（200 存活 / 401 鉴权未关 / 502 被代理劫持 / 连接被拒 真没起）。
- 审核流程第 0 步（`git log --oneline -3` 验证 commit 真实存在）保留并已写入 SKILL.md。

### Verified

- 冷启动全链路冒烟（无 `.cache`、自动提取 token、自动拉起 serve）：
  派活 → agent 建文件 + commit + 汇报 hash，产物与 commit 均真实落盘。
- `poll_tasks.py` 回归：乱序 `--mark`、`--unmark`、批量 `--mark`、旧格式兼容、脏值容错 全过。
- 三脚本 `py_compile` 全过；`quick_validate.py` 校验通过（`doubao-workbuddy-collab` 目录）。

## [1.0.0] — 2026-10-10

- 首个版本：SKILL.md（双向模式入口）+ 3 scripts（dispatch / poll_tasks / extract_jwt）
  + 3 references（setup / methodology / troubleshooting）+ 6 templates。
- 模式 A（豆包 → WorkBuddy，dispatch.py API 直连）与模式 B（WorkBuddy → 豆包，文件信箱）双闭环。
