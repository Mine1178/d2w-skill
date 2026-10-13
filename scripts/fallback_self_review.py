# -*- coding: utf-8 -*-
"""
fallback_self_review.py — 模式 B 兜底：豆包不响应时，WorkBuddy 经 CLI 通道自审自查

场景：WorkBuddy 把任务写进 inbox/tasks/ 后，若豆包在 threshold 秒内未写结果
      （inbox/results/ 无对应文件）→ 判定"豆包不响应"，本脚本接管闭环：
        run#1 干活   （work_model，默认与 dispatch 一致：WB_MODEL 或 glm-5.3）
        run#2 审核   （review_model，默认 glm-5.3；若与干活模型相同自动切
                       kimi-k2.8-preview；kimi 再不响应切 balanced-model）
      审核发现 P0 → 派修再审（最多 max_rounds 轮）；无 P0 收敛 → 写结果 → --mark NNN。

审核模型选择（v1.5.18 用户拍板）：
  primary（默认 glm-5.3）≠ 干活模型 → 直接用 primary
  primary == 干活模型           → 切 kimi-k2.8-preview（保证独立）
  kimi-k2.8-preview 不响应      → 切 balanced-model（WorkBuddy 均衡档，最后兜底）
  "不响应"判据：派活异常(SystemExit) 或 审核结果文件未生成。

用法：
  python fallback_self_review.py --cwd D:/proj --check       # 列出"已超时未响应"的任务（默认动作）
  python fallback_self_review.py --cwd D:/proj --run         # 对超时未响应任务执行兜底（干活+审核+收敛+自动 mark）
  python fallback_self_review.py --cwd D:/proj --all         # 列出所有未处理任务（含未超时）

参数：
  --threshold 秒数   豆包不响应判据：任务单 mtime 距今超该秒数且无结果（默认 100）
  --work-model       干活模型 id（默认读 WB_MODEL，否则 glm-5.3）
  --review-model     审核首选模型 id（默认 glm-5.3）
  --max-rounds N     审核发现 P0 后的最大派修轮数（默认 3）
  --timeout 秒数     单次 run 超时（默认 180）
  --debug            打印原始 SSE 事件

依赖：同目录 dispatch.py（复用 token 提取 / serve / POST runs / SSE），pywin32 不需要。
"""
import argparse
import glob
import os
import re
import sys
import time

import dispatch as wb


def find_seq(name):
    m = re.match(r"(\d+)_", name)
    return int(m.group(1)) if m else None


def load_done(marker):
    if not os.path.exists(marker):
        return set()
    try:
        raw = open(marker, encoding="utf-8").read().strip()
    except Exception:
        return set()
    done = set()
    for part in re.split(r"[,\s]+", raw):
        if part.isdigit():
            done.add(int(part))
    return done


def scan_tasks(cwd):
    """返回 [(seq, name, path, mtime, has_result, done)]。"""
    tasks_dir = os.path.join(cwd, "inbox", "tasks")
    results_dir = os.path.join(cwd, "inbox", "results")
    marker = os.path.join(cwd, "inbox", "last_task_processed.txt")
    done = load_done(marker)
    out = []
    if os.path.isdir(tasks_dir):
        for name in os.listdir(tasks_dir):
            if not name.lower().endswith(".md"):
                continue
            seq = find_seq(name)
            if seq is None:
                continue
            path = os.path.join(tasks_dir, name)
            out.append((seq, name, path, os.path.getmtime(path),
                        os.path.exists(os.path.join(results_dir, name)),
                        seq in done))
    out.sort()
    return out


def build_work_text(cwd, seq, title, task_path):
    seq3 = "%03d" % int(seq)
    root = cwd.replace("\\", "/").rstrip("/")
    return (
        "请处理 D2W 协作任务 {seq3}（兜底自审，任务来自模式 B 队列）。\n"
        "1) 读任务单：{path}\n"
        "2) 在 {root} 目录按要求执行（写代码/审核/查资料/润色等）\n"
        "3) 结果写到：{root}/inbox/results/{seq3}_*.md（序号必须与任务单一致）\n"
        "4) git commit，提交信息 'D2W fallback task {seq3}'\n"
        "任务标题：{title}"
    ).format(seq3=seq3, path=task_path.replace("\\", "/"), root=root, title=title)


def build_review_text(cwd, seq, title, task_path, round_n):
    seq3 = "%03d" % int(seq)
    root = cwd.replace("\\", "/").rstrip("/")
    return (
        "请审核 D2W 协作任务 {seq3} 的产出（兜底自审，独立模型复审）。\n"
        "1) 读任务单：{path}\n"
        "2) 读结果单：{root}/inbox/results/{seq3}_*.md（有代码文件一并检查）\n"
        "3) 对照任务单验收标准逐条检查：正确性/可维护性/性能/安全（GUI 任务另查布局/遮挡/对齐/DPI）\n"
        "4) 写审核意见到：{root}/inbox/review_round{rn}.md（N 递增，每条含 现象/根因/修改方向，"
        "分级 P0 阻塞/P1 该改/P2 建议）\n"
        "5) 末行写状态行：无 P0 写 STATUS: NO_P0，有 P0 写 STATUS: HAS_P0（判定以该行为准）\n"
        "6) git commit，提交信息 'D2W fallback review round{rn}'\n"
        "任务标题：{title}"
    ).format(seq3=seq3, path=task_path.replace("\\", "/"), root=root, title=title, rn=round_n)


def build_fix_text(cwd, seq, last_round, work_model):
    seq3 = "%03d" % int(seq)
    root = cwd.replace("\\", "/").rstrip("/")
    return (
        "请阅读 {root}/inbox/review_round{rn}.md，按意见修改任务 {seq3} 的产出。\n"
        "改完更新结果单 {root}/inbox/results/{seq3}_*.md，并 git commit，"
        "提交信息 'D2W fallback fix round{rn}'。\n"
        "不要修改任务单与审核意见文件。"
    ).format(root=root, rn=last_round, seq3=seq3)


def review_path(cwd, n):
    return os.path.join(cwd, "inbox", "review_round%d.md" % n)


def next_review_round(cwd):
    n = 1
    for p in glob.glob(os.path.join(cwd, "inbox", "review_round*.md")):
        m = re.search(r"review_round(\d+)\.md$", p)
        if m:
            n = max(n, int(m.group(1)) + 1)
    return n


def review_has_p0(cwd, n):
    """按协议判定：只认 STATUS 行。NO_P0 → False；HAS_P0 → True；
    文件缺失 → None（不响应）；文件在但无 STATUS 行 → True（保守判有 P0，派修会再要求写）。"""
    p = review_path(cwd, n)
    if not os.path.exists(p):
        return None  # 审核未产出文件 = 不响应
    try:
        text = open(p, encoding="utf-8").read()
    except Exception:
        return None
    m = re.search(r"STATUS\s*[:：]\s*(NO_P0|HAS_P0)", text)
    if m:
        return m.group(1) != "NO_P0"
    return True  # 响应了但未按协议写 STATUS → 保守判有 P0


def pick_review_models(work_model, primary):
    """审核模型候选链（去重）：primary ≠ work_model → primary；相等 → 先 kimi 后 balanced。"""
    cands = []
    if primary != work_model:
        cands.append(primary)
    for alt in ("kimi-k2.8-preview", "balanced-model"):
        if alt not in cands and alt != work_model:
            cands.append(alt)
    if not cands:
        cands.append("balanced-model")
    return cands


def run_dispatch(text, cwd, model, timeout, debug):
    """调 dispatch.dispatch 派活；捕获 SystemExit。返回 (ok, info)。"""
    try:
        wb.reconfigure(cwd)
        wb.dispatch(text, cwd, timeout, debug, cli_model=model)
        return True, "run 完成 model=%s" % model
    except SystemExit as e:
        return False, "派活失败(model=%s) rc=%s" % (model, e.code)
    except Exception as e:
        return False, "异常(model=%s) %s %s" % (model, type(e).__name__, e)


def handle_one(cwd, seq, title, task_path, args):
    root = cwd.replace("\\", "/").rstrip("/")
    work_model = args.work_model or wb.MODEL
    review_cands = pick_review_models(work_model, args.review_model)
    rn = next_review_round(cwd)
    print("== 任务 %03d：%s ==" % (seq, title))
    print("干活模型   : %s" % work_model)
    print("审核模型链 : %s" % " → ".join(review_cands))

    # 第 1 轮：干活
    ok, info = run_dispatch(build_work_text(cwd, seq, title, task_path),
                            cwd, work_model, args.timeout, args.debug)
    print("干活 run   : %s" % info)
    if not ok:
        print("   → 干活失败，本轮任务标记为已处理（避免卡队列），需人工核查。")
        return "fail-work", None

    # 审核轮（含模型回退）
    has_p0 = None
    review_model_used = None
    for r in range(args.max_rounds):
        if r > 0:
            # 派修
            ok, info = run_dispatch(build_fix_text(cwd, seq, rn, work_model),
                                    cwd, work_model, args.timeout, args.debug)
            print("派修 run   : %s" % info)
            if not ok:
                return "fail-fix", rn
            rn = next_review_round(cwd)
        # 审核（候选模型逐个试，直到审核文件生成）
        for m in review_cands:
            ok, info = run_dispatch(build_review_text(cwd, seq, title, task_path, rn),
                                    cwd, m, args.timeout, args.debug)
            print("审核 run   : %s" % info)
            has_p0 = review_has_p0(cwd, rn)
            if has_p0 is not None:
                review_model_used = m
                break
        if has_p0 is None:
            print("   → 审核模型链全部不响应（无审核文件产出），标记已处理，需人工核查。")
            return "fail-review", rn
        print("审核结果   : %s（%s）" % ("有 P0，继续派修" if has_p0 else "NO_P0，收敛",
                                     review_model_used))
        if not has_p0:
            return "converged", rn
    return "max-rounds", rn


def main():
    ap = argparse.ArgumentParser(description="模式 B 兜底：豆包不响应时 WorkBuddy 自审自查（CLI 通道）")
    ap.add_argument("--cwd", default=os.getcwd(), help="项目根目录（含 inbox/）")
    ap.add_argument("--threshold", type=int, default=100,
                    help="豆包不响应判据：任务单 mtime 距今超该秒数且无结果（默认 100）")
    ap.add_argument("--work-model", default=None, help="干活模型 id（默认 WB_MODEL 或 glm-5.3）")
    ap.add_argument("--review-model", default="glm-5.3", help="审核首选模型 id（默认 glm-5.3）")
    ap.add_argument("--max-rounds", type=int, default=3, help="发现 P0 后最大派修轮数（默认 3）")
    ap.add_argument("--timeout", type=int, default=180, help="单次 run 超时秒数（默认 180）")
    ap.add_argument("--debug", action="store_true", help="打印原始 SSE 事件")
    ap.add_argument("--run", action="store_true", help="执行兜底（默认只列出超时未响应任务）")
    ap.add_argument("--check", action="store_true", help="列出超时未响应任务（默认动作）")
    ap.add_argument("--all", action="store_true", help="列出所有未处理任务（含未超时）")
    ap.add_argument("--no-mark", action="store_true",
                    help="--run 处理后不写 last_task_processed.txt（默认自动标记，防豆包重复处理）")
    args = ap.parse_args()

    cwd = os.path.abspath(args.cwd)
    tasks = scan_tasks(cwd)
    now = time.time()
    wb.DANGER_ALLOW = True  # 兜底任务按任务单执行，危险与否由模式 B 甲方（WorkBuddy）负责

    overdue = []
    for seq, name, path, mtime, has_result, done in tasks:
        if done:
            continue
        if has_result:
            print("任务 %03d：已有结果（豆包或他人已处理，跳过）" % seq)
            continue
        if now - mtime > args.threshold:
            overdue.append((seq, name, path))
    print("超时未响应（>%ds）: %d 个" % (args.threshold, len(overdue)))

    if args.all:
        print("\n=== 全部未处理任务 ===")
        for seq, name, path, mtime, has_result, done in tasks:
            if not done:
                print("  %03d  %s  [%s]" % (seq, name, "已有结果" if has_result else "待处理"))
        return 0

    if not args.run:
        print("\n=== 待兜底任务（加 --run 执行）===")
        for seq, name, path in overdue:
            print("  %03d  %s" % (seq, name))
        if not overdue:
            print("  无。任务单未超时或已有结果。")
        return 0

    # --run：逐个兜底（默认自动 mark，防豆包重复处理；--no-mark 关闭）
    results_summary = []
    marker = os.path.join(cwd, "inbox", "last_task_processed.txt")
    for seq, name, path in overdue:
        title = os.path.splitext(name)[0]
        status, rn = handle_one(cwd, seq, title, path, args)
        results_summary.append((seq, status))
        if not args.no_mark:
            done = load_done(marker)
            done.add(seq)
            os.makedirs(os.path.dirname(marker), exist_ok=True)
            open(marker, "w", encoding="utf-8").write(
                ",".join(str(x) for x in sorted(done)))
            print("已标记 %03d → %s" % (seq, ", ".join(str(x) for x in sorted(done))))
    print("\n=== 兜底汇总 ===")
    for seq, status in results_summary:
        print("  %03d  %s" % (seq, status))
    return 0


if __name__ == "__main__":
    sys.exit(main())
