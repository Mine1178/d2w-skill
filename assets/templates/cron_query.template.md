# 定时任务 query 模板 — 每小时自动审核/轮询

> 用法：按 doubao-cron-scheduler Skill 规范创建 cron 任务（`0 * * * *`），query 用下面模板改写。
> 替换 <cwd> 为项目绝对路径、<任务名> 为定时任务标题（必须与 title 一致）。
> 关键规则：① 心跳留痕（用户靠它确认任务在跑）；② 无论结果如何必须向用户汇报（禁止静默）；③ 审核方只审不改。

## 模板 A：自动审核（豆包审 WorkBuddy 的产出）

本次请求是由「<任务名>」定时任务到时触发的。

0. 心跳留痕：执行 `Add-Content -Path "<cwd>\inbox\audit_heartbeat.txt" -Value (Get-Date -Format "yyyy-MM-dd HH:mm:ss") -Encoding utf8`
1. 执行 `git -C <cwd> rev-parse HEAD` 拿当前 commit hash（无 commit 则直接进入第 6 步汇报）
2. 读 `<cwd>\inbox\last_reviewed_commit.txt` 对比：
   - 相同 → 无新提交，直接进入第 6 步
   - 不同 → 有新提交，继续审核
3. 审核：读产出文件 + 对照 `<cwd>\CHECKLIST.md` 逐条打勾 + 跑验证（py_compile / selftest）
4. 问题分 P0/P1/P2，写 `<cwd>\inbox\review_roundN.md`（N = 现有 review_round*.md 数 + 1）；无 P0 则末行写 STATUS: NO_P0；连续两轮 NO_P0 时明确告知用户可过目
5. 更新基线：当前 commit hash 写入 `<cwd>\inbox\last_reviewed_commit.txt`
6. 强制汇报（2-3 行）：本轮心跳触发时间 / 有无新 commit / P0-P1-P2 数量 或 "无新提交，WorkBuddy 未动，任务正常运行，下次检查 {下一整点}"。禁止静默。
7. 你只审核，不要自己改代码；不要改 PRD.md 和 CHECKLIST.md。

## 模板 B：自动轮询任务队列（WorkBuddy → 豆包）

本次请求是由「<任务名>」定时任务到时触发的。

0. 心跳留痕：追加当前时间到 `<cwd>\inbox\audit_heartbeat.txt`
1. 执行 `python <skill 目录>\scripts\poll_tasks.py --cwd <cwd>` 检查 `<cwd>\inbox\tasks\` 有无新任务（对比 `<cwd>\inbox\last_task_processed.txt`）
2. 无新任务 → 进入第 5 步
3. 有新任务：逐个处理（读任务单 → 执行 → 写结果到 `<cwd>\inbox\results\NNN_*.md` → 更新 last_task_processed.txt）
4. 处理完成向用户汇报处理了哪些任务、结果如何
5. 强制汇报：本轮心跳触发时间 / 有无新任务 / 处理情况。禁止静默。
