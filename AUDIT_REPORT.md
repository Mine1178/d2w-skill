# D2W Skill 深度审计报告（v1.5.10）

审计时间：2026-10-12
审计方式：本地静态审计（py_compile + 引用一致性检查 + 章节号交叉核对 + L 组连续性检查）

## 审计范围
- scripts/*.py（6 个）
- SKILL.md / references/*.md（3 个）
- assets/templates/*.md（9 个）
- assets/ui_spec/*.md（2 个）
- CHANGELOG.md

## 发现的 BUG（已修复）

### BUG-1：码图路径缺少"复制步骤"说明（P1）

**现象**：SKILL.md / methodology §5.26 / UI_LAYOUT_SPEC §五 三处都写"项目里读 `assets/alipay.jpg` / `assets/wechatpay.jpg`"，但没说这两张图从哪来。派活时 WorkBuddy 不知道要从技能包 `assets/money_code/` 复制码图进项目，会导致代码写好但运行时找不到图。

**根因**：v1.5.6 把码图收编为技能包资产后，v1.5.8 重写弹窗规范时只改了路径引用，没补"复制步骤"这一步。

**修复**：三处都加一句"派活时把技能包 `assets/money_code/{alipay,wechatpay}.jpg` 复制进项目 `assets/`"。

## 已检查无问题项

- scripts/*.py 全部 py_compile 通过（6/6）
- 文档引用的文件路径全部存在（references/、assets/templates/、assets/ui_spec/、scripts/）
- 章节号引用全部对得上（methodology §5.1~5.26、troubleshooting §1~23、setup §9.3/9.4）
- L 组编号 L1~L11 连续无断号
- dispatch.py argparse 参数与 SKILL.md 命令示例一致（--status/--smoke/--stop-all/--list-runs/--queue/--auto-review/--model）
- 无残留占位符/乱码（.gitignore 已在 v1.5.7 修复）

## 建议关注（未修复）

- kimi-k3-1 模型派活后 SSE 未返回文本（runId=ca89899c），serve 日志无处理记录，疑似模型未真正执行。建议下次派活前先 `python dispatch.py --smoke` 验证环境。
- dispatch.py 帮助文本里 `--smoke` 描述与 SKILL.md 一致，但已在 README.md 常用命令表列出（v1.5.11 完成）（README 是面向 GitHub 用户的门面，建议后续补一个"常用命令"小节）。

## 验证方式

- `python -m py_compile scripts/*.py` 全部通过
- `Select-String` 交叉核对文件引用、章节号、L 组编号
- git diff 确认只改了 3 处文档（加复制步骤说明）