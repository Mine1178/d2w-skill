# -*- coding: utf-8 -*-
"""
poll_tasks.py — 反向协作工具：轮询任务队列（WorkBuddy → 豆包 方向）

场景：WorkBuddy（或用户）把任务写成 inbox/tasks/NNN_*.md，
      豆包用本工具发现新任务，处理完写结果到 inbox/results/NNN_*.md。

用法：
  python poll_tasks.py                 # 列出未处理任务（默认）
  python poll_tasks.py --cwd D:/proj   # 指定项目目录
  python poll_tasks.py --mark NNN      # 把序号 NNN 标记为已处理（可多次，支持乱序）
  python poll_tasks.py --reset         # 清空已处理记录（重跑场景）
  python poll_tasks.py --all           # 列出所有任务（含已处理）

协议（与 SKILL.md 反向协作章节一致）：
  inbox/tasks/NNN_<简述>.md       任务单（来源方写，NNN 三位序号递增）
  inbox/results/NNN_<同简述>.md   结果单（处理方写，NNN 必须一致）
  inbox/last_task_processed.txt   已处理序号集合（处理方维护，逗号分隔，兼容旧的单数字）

修复记录（2026-10-10）：
  旧实现用"单个最大序号"当游标，--mark 4 会把未处理的 1/2/3 静默吞掉。
  现改为"已处理序号集合"，--mark 只追加该序号，乱序处理也不丢任务；
  读取旧格式（纯数字）时自动兼容。
"""
import argparse, os, re, sys

def find_seq(name):
    m = re.match(r"(\d+)_", name)
    return int(m.group(1)) if m else None

def load_done(marker):
    """读取已处理序号集合。兼容旧格式：单个整数 -> 视为 {0..N} 全部已处理之外，
    仍按"集合"语义返回 {N} ——但对旧文件里只有 N 的情况，追加语义等价。"""
    if not os.path.exists(marker):
        return set(), True
    try:
        raw = open(marker, encoding="utf-8").read().strip()
    except Exception:
        return set(), True
    if not raw:
        return set(), True
    done = set()
    legacy = True
    for part in re.split(r"[,\s]+", raw):
        part = part.strip()
        if not part:
            continue
        if part.isdigit():
            done.add(int(part))
        else:
            # 含非数字（旧脏值）→ 忽略该项
            pass
    return done, legacy

def save_done(marker, done):
    os.makedirs(os.path.dirname(marker), exist_ok=True)
    open(marker, "w", encoding="utf-8").write(",".join(str(x) for x in sorted(done)))

def fmt_done(done):
    return ", ".join(str(x) for x in sorted(done)) if done else "（无）"

def main():
    ap = argparse.ArgumentParser(description="轮询 WorkBuddy -> 豆包 任务队列")
    ap.add_argument("--cwd", default=os.getcwd(), help="项目目录（默认当前目录）")
    ap.add_argument("--mark", type=int, action="append", help="把序号 NNN 标记为已处理（可重复传多次）")
    ap.add_argument("--unmark", type=int, action="append", help="取消序号 NNN 的已处理标记")
    ap.add_argument("--reset", action="store_true", help="清空已处理记录")
    ap.add_argument("--all", action="store_true", help="列出所有任务（含已处理）")
    args = ap.parse_args()

    tasks_dir = os.path.join(args.cwd, "inbox", "tasks")
    results_dir = os.path.join(args.cwd, "inbox", "results")
    marker = os.path.join(args.cwd, "inbox", "last_task_processed.txt")

    if not os.path.isdir(tasks_dir):
        print(f"ERR: 任务目录不存在: {tasks_dir}", file=sys.stderr)
        print("先建目录并放入任务单（模板见 assets/templates/task_request.template.md）", file=sys.stderr)
        sys.exit(1)

    done, _ = load_done(marker)

    # 收集任务
    tasks = []
    for name in os.listdir(tasks_dir):
        if not name.lower().endswith(".md"):
            continue
        seq = find_seq(name)
        if seq is None:
            continue
        path = os.path.join(tasks_dir, name)
        mtime = os.path.getmtime(path)
        has_result = os.path.exists(os.path.join(results_dir, name))
        tasks.append((seq, name, mtime, has_result))
    tasks.sort()

    if args.reset:
        if os.path.exists(marker):
            os.remove(marker)
        print("已清空已处理记录")
        return

    if args.mark is not None or args.unmark is not None:
        all_seqs = {s for s, _, _, _ in tasks}
        changed = []
        for n in (args.mark or []):
            if n not in all_seqs:
                print(f"WARN: 没有序号 {n} 的任务单（仍记录到已处理集合）", file=sys.stderr)
            done.add(n)
            changed.append(f"+{n}")
        for n in (args.unmark or []):
            done.discard(n)
            changed.append(f"-{n}")
        save_done(marker, done)
        print(f"已处理集合更新: {' '.join(changed)} -> {fmt_done(done)}")
        return

    # 列出任务
    pending = [t for t in tasks if t[0] not in done]
    print(f"已处理序号: {fmt_done(done)}")
    print(f"任务总数: {len(tasks)}，未处理: {len(pending)}\n")
    if not pending:
        print("无新任务。")
        return
    print("=== 未处理任务 ===")
    for seq, name, _, has_result in pending:
        status = "已有结果" if has_result else "待处理"
        print(f"  {seq:>3}  {name}  [{status}]")
    if not args.all:
        print("\n提示：处理完把结果写为 inbox/results/<同序号>_*.md，并用 --mark 标记。")
        return
    print("\n=== 全部任务 ===")
    for seq, name, _, has_result in tasks:
        flag = "已处理" if seq in done else "未处理"
        print(f"  {seq:>3}  {name}  [{flag}]")

if __name__ == "__main__":
    main()
