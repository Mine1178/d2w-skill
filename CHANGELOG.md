# Changelog — D2W 双 AI 协作开发闭环

本文件记录 Skill 的版本变更。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。


## [1.5.22] — 2026-10-18

GUI 规范新增第三条需求：快捷方式图标多尺寸自动生成、苹果风、无白边撑满画布。

### Added

- **快捷方式图标多尺寸·无白边（L14，§4.7）**：Pillow 按同一主图形批量生成 .ico（16/32/48/256）；
  圆角方形四边贴满画布、无白边（禁止小图标悬中间+白边）；同一 ico 用于 exe（PyInstaller --icon）/
  桌面与开始菜单快捷方式（Inno Setup IconFilename）/窗口标题栏 iconbitmap；安装后验证无白边；
  验收清单新增 L14、派活自检新增第 15 条

### Verified

- UI_LAYOUT_SPEC.md §4.7 新增 + 验收 L14 + 自检 15；SKILL.md 界面质量小节同步；纯文档改动

## [1.5.21] — 2026-10-18

GUI 规范新增两条硬性需求：① 生成的软件文字可选中复制；② Logo 苹果风格圆润化。

### Added

- **文本可选中复制（L12，§4.5）**：除按钮外所有文本（正文/说明/结果/列表/日志/弹窗）可鼠标划线选中 + Ctrl+C 复制——
  给出 tkinter 实现（只读 Text 拦截编辑 / 只读 Entry / SelectableLabel），按钮唯一豁免；验收清单新增 L12、派活自检新增第 13 条
- **Logo 苹果风格（L13，§4.6）**：大圆角（≥30%）或圆形基底、简洁扁平单主图形、同色系微妙渐变、无直角无花哨；
  多尺寸 .ico（16/32/48/256）应用到窗口标题栏/任务栏/安装程序；验收清单新增 L13、派活自检新增第 14 条

### Verified

- UI_LAYOUT_SPEC.md §4.5/§4.6 新增规范 + 验收清单 L12/L13 + 自检清单 13/14；SKILL.md 界面质量小节同步；
  纯文档改动（无脚本），README 徽章同步 v1.5.21

## [1.5.20] — 2026-10-15

适配 WorkBuddy 升级：CLI 入口文件改名（codebuddy-headless.js → codebuddy-lite-wb.mjs），修复旧脚本在新版上报「CLI 未找到」。

### Fixed

- **CLI 探测两代兼容**：`dispatch.py` 默认路径、常见安装目录 glob、跨盘符全盘扫描、进程推导四路探测全部改为
  同时识别两代入口名（新版 `codebuddy-lite-wb.mjs` 优先，旧版 `codebuddy-headless.js` 兜底），WorkBuddy 升级/回退均自动找到
- **WB_CLI_PATH 手动指定保留**：仍为最高优先（环境变量显式指定即直接使用，不受两代探测影响）
- 报错提示与 setup / troubleshooting / methodology 文档同步更新为两代描述；README 徽章版本号同步

### Verified

- 本机（WorkBuddy 新版）实测：CLI 目录下仅存在 `codebuddy-lite-wb.mjs`（9.4MB），旧名文件已不存在；
  `find_cli()` 实测解析到新版 mjs 路径；py_compile 通过

## [1.5.19] — 2026-10-13

修复外部验收测试（WorkBuddy 独立复核 v1.5.18）发现的 3 项 BUG：P0 语法兼容 / P1 文档命令语境 / P2 smoke 残留。

### Fixed

- **BUG-1（P0）**：`dispatch.py` 的 `--auto-review` 审核草稿在 f-string 表达式内使用了反斜杠
  （`{f"...\n..." if ...}`，522 行），Python < 3.12 直接 `SyntaxError`，**整个脚本无法运行**——
  与 SKILL.md 声称的 "Python 3.9+" 前置条件矛盾。改用第 501 行已定义却没用上的 `detail_block`
  变量（字符串拼接，无 f-string 内反斜杠）。实测：Python 3.11 / 3.12 / 3.14 三版本编译全部通过，
  3.11 下 `import dispatch` 正常。
- **BUG-2（P1）**：文档命令语境不一致——`init_project.py` 把脚本部署到**项目根**，但 README /
  SKILL.md 多处示例写 `python scripts/xxx.py`（子目录），照抄必然 "No such file or directory"；
  且 `fallback_self_review.py` 依赖同目录 `import dispatch`，双位置更混乱。统一（方案 A+）：
  - `init_project.py` 部署列表加入 `fallback_self_review.py`（与 dispatch 同根，import 稳定）
  - README / SKILL.md 全部命令统一为：**部署到项目根的脚本（dispatch/poll_tasks/notify_doubao/
    fallback_self_review）在项目根无前缀运行**；**技能内工具（init_project/gen_checklist）保留
    `scripts/` 前缀**并注明"在技能目录内运行"
- **BUG-3（P2）**：`--smoke` 运行产生 `.cache/`（serve.pid/runs.json/wb_token.txt），在无
  `.gitignore` 的项目里留下未跟踪残留。修复：smoke PASS 后检查项目 `.gitignore`，未忽略 `.cache/`
  则幂等追加（含换行处理），并打印提示。实测：无 `.gitignore` 临时项目跑 `--smoke` → PASS +
  自动生成 `.gitignore`（含 `.cache/`），`git status` 不再出现 `.cache/` 未跟踪。

### Verified

- Python 3.11 / 3.12 / 3.14 三版本 `py_compile`：`dispatch.py`、`init_project.py`、
  `fallback_self_review.py`、`poll_tasks.py`、`notify_doubao.py` 全部 PASS
- 3.11 真实加载 `import dispatch` 成功（BUG-1 修复验收）
- 真实 `--smoke --cwd <无.gitignore临时项目>`：全链路 PASS（token→派最小任务→产物+commit 落盘），
  且 `.cache/` 自动追加到 `.gitignore`
- 文档命令抽查：README L50/L57、SKILL.md 环境验证/notify/fallback/smoke 全部为项目根无前缀写法


## [1.5.18] — 2026-10-13

模式 B 兜底自审自查：豆包不响应（任务单放置超 threshold 秒且无结果）时，WorkBuddy 经 CLI 通道自己闭环。

### Added

- **新脚本 `scripts/fallback_self_review.py`**（复用 dispatch.py 的 token 提取 / serve / POST runs / SSE）：
  - `--check`（默认）：列出"已超时未响应"任务；`--run`：对超时任务执行兜底并自动 mark；
    `--all`：列出全部未处理任务
  - 兜底 = **干活 run**（work_model，默认 glm-5.3）+ **独立模型审核 run**：审核首选模型
    （默认 glm-5.3）与干活模型不同则直接用；相同自动切 `kimi-k2.8-preview`；kimi 不响应
    再切 `balanced-model`（WorkBuddy 均衡档）。"不响应"判据 = 派活异常 或 审核结果文件未生成
  - 收敛循环：审核文件按协议写 `STATUS: NO_P0 / HAS_P0`（判定以该行为准）；有 P0 → 派修再审，
    最多 `--max-rounds` 轮（默认 3）
  - 完成自动写 `last_task_processed.txt`（`--no-mark` 关闭）→ 豆包再轮询看到"已处理"直接跳过，无冲突
- 干活 run 后新增**产物自检**：结果单未生成 → fail-work；git 无新 commit → 打印警告（审核重点查）
- `SKILL.md` 模式 B"工作流触发方式"新增兜底说明；资源索引补脚本。

### Verified（真实端到端三次）

- `py_compile` 通过；超时判据（mtime 200s 前 + 无结果 → 识别为待兜底）正确
- 真实 `--run`（临时测试项目，任务=建 fallback_smoke.txt + commit）：
  - 干活 run（glm-5.3）：产物/结果单/两次 commit 全部真实落盘
  - 审核 run（自动切 kimi-k2.8-preview）：写 review_round1.md，末行 `STATUS: NO_P0`，收敛
  - 审核模型独立性生效：审核发现真实 P1/P2（.cache 未忽略等），仍判 NO_P0 收敛
  - 自动 mark → 豆包轮询显示"已处理序号: 1，无新任务"
- **收敛循环 P0 分支实测**（任务=原样写 `print('1'+1)`，验收=能运行输出 2）：
  干活 → 审核1（kimi）判 `STATUS: HAS_P0` → 派修（glm-5.3 改 `'1'`→`1`）→ 审核2（kimi 实测
  输出 2 + git diff 核验）判 `STATUS: NO_P0` → 收敛 → 自动 mark。git log 三阶段
  （task→fix→review2）完整
- 极端场景（审核模型链全部不响应，SSE `Error: aborted`）正确降级：fail-review + mark + 人工核查提示，不卡队列
- 说明：PowerShell 端 exit 1 为 stderr 输出包装（dispatch.py 日志打到 stderr），脚本本身收敛退出


## [1.5.17] — 2026-10-13

模式 B 通知器（notify_doubao.py）增加**剪贴板被锁时的键盘输入降级路径**——实测发现系统剪贴板被 WorkBuddy 锁定，纯剪贴板方案在本机不可用。

### Added

- **剪贴板 owner 检测**（`clipboard_owner()` / `_clip_owner_hint()`）：`--status` 在剪贴板不可用时
  打印当前持有者进程（实测 = WorkBuddy.exe PID 13432 的 `Chrome_MessageWindow`），指明"被谁锁"。
- **键盘逐字输入降级**：
  - `--type`：强制用 `SendInput KEYEVENTF_UNICODE` 逐字符键入（支持中文，不依赖剪贴板）
  - `--click-x/--click-y`：--send 前先点击豆包输入框坐标（显式指定）
  - `--pick`：把鼠标移入豆包输入框后运行，读坐标写入 `.cache/doubao_input_pos.txt`，`--send` 自动复用
  - `--send` 自动降级：剪贴板可用→Ctrl+V+Enter；不可用→自动转键盘逐字输入
- `resolve_click()`：点击坐标来源优先级 = `--click-x/--click-y` > 缓存 > 无点击

### Fixed

- 依赖缺失导致 B 方向跑不通：当前 Python 3.14 未装 `pywin32`/`psutil`，已安装
  （pywin32-312 cp314 wheel + psutil），`--status` 全绿。

### Changed

- `notify_doubao.py` docstring 补"剪贴板被锁时的降级"实测依据与 `--pick`/`--type` 用法。

### Verified

- `python -m py_compile notify_doubao.py` 通过
- 单元验证：`sizeof(INPUT)=40`（64 位正确）、SendInput 中文返回 2（down+up 都发出）、`type_unicode_text` 无异常
- `--status`：剪贴板不可用时正确打印持有者 WorkBuddy.exe
- 说明：真实"打入豆包输入框"的端到端受当前会话限制（前台为锁屏界面），
  需豆包窗口在前台时用 `--pick` 标定 + `--send --type` 实测


## [1.5.11] — 2026-10-12

README 过时描述修正（v1.5.9/v1.5.10 同步遗漏）。

### Fixed

- L 组验收范围：L1~L10 → L1~L11（补文本排版 L11）
- Claude-4.0 模型 id 补全：`default-1.2`

## [1.5.10] — 2026-10-12

深度审计修复（静态审计，非 kimi-k3-1 派活——WorkBuddy 未真正执行）。

### Fixed

- 码图路径说明缺失：SKILL.md / methodology §5.26 / UI_LAYOUT_SPEC §五 三处补充
  "派活时把技能包 assets/money_code/ 复制进项目 assets/"，避免 WorkBuddy 运行时找不到码图。

### Added

- AUDIT_REPORT.md：审计报告（BUG 清单 + 已检查无问题项 + 建议关注）

## [1.5.9] — 2026-10-12

新增文本排版规范（避免孤行/换行错误）——代码产出 GUI 软件最高频缺陷。

### Added

- UI_LAYOUT_SPEC §4.4 文本排版：wraplength 必设并随宽度刷新、避免孤行孤字、
  正文 justify=LEFT、label 与控件同基线、不截断不省略号、错误/提示语义色、
  代码块等宽不自动换行
- CHECKLIST L11 验收项：多行文本排版逐条打勾
- SKILL.md 界面质量硬性要求新增"文本排版无孤行"一条
- UI_LAYOUT_SPEC §八派活必带清单第 12 条

### Changed

- L 组从 L1~L10 扩展到 L1~L11

## [1.5.8] — 2026-10-12

关于页赞助弹窗规格细化（1060×880 可缩放 + 480px 双码图 + 一键放大全屏）。

### Changed

- 弹窗尺寸：420×380 不可缩放 → **1060×880，minsize 720×560，resizable**，屏幕居中不跟随按钮
- 按钮样式量化：bg=#f1f5f9, relief=SOLID, bd=1, padx=16 pady=6, hover #e2e8f0
- 码图：480×480 LANCZOS thumbnail，白底 bd=2，两列等宽 grid，下方「📱 支付宝扫码」/「💬 微信扫码」标签
- 新增「⤢ 放大 / 🗗 还原」按钮：`dlg.state("zoomed")` 全屏，闭包存 normal_geom
- 码图路径函数 `_resource_path()` 明确（PyInstaller `_MEIPASS` 兼容），打包 `--add-data "assets;assets"`
- CHECKLIST L10 验收标准同步更新；SKILL.md / UI_LAYOUT_SPEC §五 / methodology §5.26 三处联动


## [1.5.7] — 2026-10-12

开源准备：新增 README.md（含末尾「☕ 感谢赞助」板块，并列支付宝/微信码图）+ 修复 .gitignore 乱码注释。

## [1.5.6] — 2026-10-12

收款码图收编为技能包正式资产。

### Added

- `assets/money_code/alipay.jpg` / `wechatpay.jpg`：两张收款码随技能包分发，
  派活时直接复制进项目 `assets/`，不再依赖外部绝对路径。

### Changed

- SKILL.md / methodology §5.26 / UI_LAYOUT_SPEC §五：路径引用从
  `D:\Desktop\SD\15.DW2_skill\Money_code\` 改为 `assets/money_code/`（技能包内相对路径）。

## [1.5.5] — 2026-10-12

修正收款码源文件路径（用户移动了码图位置）。

### Changed

- 收款码源文件路径：`D:\Desktop\SD\13.Rename\Money_code` → `D:\Desktop\SD\15.DW2_skill\Money_code`
  （alipay.jpg / wechatpay.jpg 同步迁移）。SKILL.md / methodology §5.26 / UI_LAYOUT_SPEC §五 三处引用同步更新。

## [1.5.4] — 2026-10-12

GUI 项目硬约束：关于页赞助按钮（作者署名与答谢固定位）。

### Added

- **关于页「☕ 赞助作者」按钮**（GUI 项目必带）：关于页底部 secondary 浅底深字按钮，
  与五级按钮同规格不违和；点击弹模态窗，标题"请作者喝杯咖啡"，正文
  "如果你喜欢这个工具，可以请作者喝杯咖啡，感谢赞助"，下方左右并列支付宝+微信收款码，
  窗口大小刚好包络两张码图（约 420×380，不可缩放）。
- 码图源文件 D:\Desktop\SD\15.DW2_skill\Money_code\{alipay,wechatpay}.jpg 必须复制进项目 ssets/，
  代码用相对路径读取（禁止硬编码绝对路径）；PyInstaller 走 --add-data "assets;assets" + sys._MEIPASS。
- CHECKLIST 新增 **L10**（关于页赞助按钮）；UI_LAYOUT_SPEC §五组件表/§七验收/§八自检三处同步；
  methodology 新增 **§5.26**（规格 + 审核硬项）。

### Notes

- 非 GUI 项目（CLI/后台工具）不适用此条；审核时按 L10 人工打勾。
- 审核硬项：按钮风格违和 / 码图裁剪拉伸 / 窗口过大留白 / 硬编码绝对路径 / 码图没打进包——任一 P1。

## [1.5.3] — 2026-10-12

三项增强（模型清单对齐新版 WorkBuddy 配置 / selftest 样例去项目特例化 / --smoke 一条命令冒烟）。

### Added

- **`dispatch.py --smoke`**：一条命令跑冒烟自检——环境检查（token/CLI/serve）→ 派最小任务（建
  smoke_test.txt + commit）→ 验证产物文件与 commit 真实落盘。升级 WorkBuddy / 换机后不用再手跑三步。
  退出码 0=PASS / 1=FAIL；smoke 产物留在项目里可保留或 `git reset --hard` 清理。
- **模型清单新增**（对齐 2026-10 WorkBuddy 配置 `acc-product-config-v3.json`）：
  `default-1.2` Claude-4.0-Sonnet、`default-1.1` Claude-3.7-Sonnet、`glm-4.6`、
  `hunyuan-2.0-instruct`、`deepseek-v4-flash`、`wb-lite`。
- **credits 倍率字段说明**：新配置 `models[].credits_multiplier` 已为空，setup §9.3 改为"历史 credits"
  列并标注仅供档位参考，不再硬填当前倍率。

### Changed

- `assets/templates/selftest.example.md`：示例函数从 QuickTrans 特例 `translate_word` 泛化为通用
  `slugify`（标题→URL slug），任何项目照搬结构即可；补"覆盖度检查：三类用例缺一即 P1"。
- `SKILL.md` §九 冒烟自检：首选 `--smoke` 一条命令，手动三步保留为等价方案；派活命令列表与资源索引同步。

### Verified

- 6 个脚本 `python -m py_compile` 全过；`dispatch.py --help` 显示 `--smoke` 参数注册成功。


## [1.5.2] — 2026-10-12

系统性一致性审计修复（通读全部 20 个技能文件，消除多版本迭代遗留的前后不一致）。

### Fixed

- **CHANGELOG [1.3.4] 条目文本损坏**：`frontmatter name: d2w` 被断行成 `frontmatter \n ame: d2w`，已修复
- **review_round.template.md 头部残留旧评分口径**：仍写"收敛时总分须 ≥20"，与 v1.5.0 锚定规范冲突——
  统一为"收敛线 = 实际评维数 × 4；非 GUI 界面维记 N/A 并从分母剔除"
- **USER_MANUAL_PDF_SPEC.md 产物名不一致**：规范内写 `USER_MANUAL.pdf`，SKILL.md/模板写
  `<产品名>_使用手册.pdf` —— 已统一为 `<cwd>/dist/<产品名>_使用手册.pdf`
- **USER_MANUAL_PDF_SPEC.md 派活模板路径错误**：样式规范路径写成 `<cwd>/inbox/USER_MANUAL_PDF_SPEC.md`，
  实际规范位于技能包 `assets/ui_spec/` —— 已改为 `<技能目录>/assets/ui_spec/...` 并提示先复制到项目根
- **SKILL.md CLI 探测描述过时**：只写"进程定位 + 常见安装目录"，与 v1.5.1 跨盘符全盘扫描（C~Z）实现不符——
  已同步探测顺序（WB_CLI_PATH → 常见安装目录 → 跨盘符扫描 → 进程定位），常见坑表同步
- **SKILL.md token 无效指引不够精确**：原指向 setup §5（提取方式），改为 troubleshooting §4（401/token 排查）+ setup §5
- **DOD.template.md 组名口径**："A~Q 组" → "适用组 A~Q"（模板可按 PRD 裁剪删组，不留死组引用）

### Cleaned

- 删除技能目录内运行产物 `.cache/wb_token.txt`（token 缓存属运行期文件，已 gitignore，派活时自动重新提取）

### Verified

- 全部 6 个脚本 `python -m py_compile` 通过；`quick_validate.py` 校验通过
- 修复后 git commit 落盘


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
- frontmatter `name: d2w`；全文 Do2Wo → D2W（SKILL.md / CHANGELOG / references / templates）
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
