# -*- coding: utf-8 -*-
"""
init_project.py — D2W 项目初始化向导（新项目 30 秒起步）

用法：
  python init_project.py <项目目录> [--name 产品名] [--with-templates] [--prd PRD.md]

做什么（一次完成）：
  1. 创建项目目录（不存在则建）
  2. git init + 仓库级身份（workbuddy-agent / agent@local）
  3. 写 .gitignore（.cache/ __pycache__/ _*.out *.log dist/ build/ *.spec）
  4. 建 inbox/tasks、inbox/results 通信信箱
  5. 复制 dispatch.py、poll_tasks.py 到项目根（部署派活桥）
  6. --with-templates：复制 8 个模板到项目根 templates/
  7. --prd <PRD.md>：自动生成 CHECKLIST.md 草稿（调用 gen_checklist.py）

之后你只需：写/确认 PRD.md（契约）→ 确认 CHECKLIST.md → 开始派活。
"""
import argparse, os, shutil, subprocess, sys

# 本脚本位于 <skill>/scripts/ 下
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
TEMPLATES_DIR = os.path.join(SKILL_DIR, "assets", "templates")

GITIGNORE = """.cache/
__pycache__/
*.pyc
_*.out
*.log
dist/
build/
*.spec
.DS_Store
"""

TEMPLATES = [
    "PRD.template.md", "CHECKLIST.template.md", "review_round.template.md",
    "task_request.template.md", "task_result.template.md", "cron_query.template.md",
    "USER_MANUAL.template.md", "DOD.template.md",
]

def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)

def main():
    ap = argparse.ArgumentParser(description="D2W 项目初始化向导")
    ap.add_argument("project", help="项目目录（绝对或相对路径）")
    ap.add_argument("--name", default="", help="产品名（写入 .gitignore 注释与提示，不强制）")
    ap.add_argument("--with-templates", action="store_true", help="复制模板到项目根 templates/")
    ap.add_argument("--prd", default=None, help="PRD.md 路径，自动生成 CHECKLIST.md 草稿")
    args = ap.parse_args()

    proj = os.path.abspath(args.project)
    os.makedirs(proj, exist_ok=True)

    # 1. git init（已有则跳过）
    r = run(["git", "rev-parse", "--is-inside-work-tree"], proj)
    if r.returncode == 0:
        print("[git] 已是 git 仓库，跳过 init")
    else:
        run(["git", "init"], proj)
        print("[git] 已初始化")

    # 2. 仓库级身份（新仓库必做，否则 commit 报错）
    run(["git", "config", "user.name", "workbuddy-agent"], proj)
    run(["git", "config", "user.email", "agent@local"], proj)
    print("[git] 身份已配置: workbuddy-agent <agent@local>")

    # 3. .gitignore
    gi = os.path.join(proj, ".gitignore")
    if not os.path.exists(gi):
        open(gi, "w", encoding="utf-8").write(GITIGNORE)
        print("[git] .gitignore 已写入")
    else:
        print("[git] .gitignore 已存在，跳过")

    # 4. inbox 信箱
    for d in ("inbox", os.path.join("inbox", "tasks"), os.path.join("inbox", "results")):
        os.makedirs(os.path.join(proj, d), exist_ok=True)
    print("[inbox] 通信信箱就绪（inbox/tasks + inbox/results）")

    # 5. 复制派活桥
    for script in ("dispatch.py", "poll_tasks.py", "notify_doubao.py"):
        src = os.path.join(SCRIPT_DIR, script)
        dst = os.path.join(proj, script)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"[deploy] {script} 已复制到项目根")
        else:
            print(f"[deploy] 警告：技能内未找到 {script}（{src}）", file=sys.stderr)

    # 6. 模板
    if args.with_templates:
        tdir = os.path.join(proj, "templates")
        os.makedirs(tdir, exist_ok=True)
        for t in TEMPLATES:
            src = os.path.join(TEMPLATES_DIR, t)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(tdir, t))
        print(f"[templates] 已复制 {len(TEMPLATES)} 个模板到 {tdir}")

    # 7. PRD -> CHECKLIST 草稿
    if args.prd:
        gen = os.path.join(SCRIPT_DIR, "gen_checklist.py")
        if os.path.exists(gen):
            prd_abs = os.path.abspath(args.prd)
            out = os.path.join(proj, "CHECKLIST.md")
            r = run([sys.executable, gen, prd_abs, "--out", out], proj)
            if r.returncode == 0:
                print(f"[checklist] 已由 PRD 生成 CHECKLIST.md 草稿")
            else:
                print(f"[checklist] 生成失败：{(r.stderr or r.stdout)[:500]}", file=sys.stderr)
        else:
            print("[checklist] 警告：未找到 gen_checklist.py，跳过", file=sys.stderr)

    name_hint = f"（{args.name}）" if args.name else ""
    print(f"\n=== 初始化完成{name_hint}：{proj} ===")
    print("下一步：1) 写/确认 PRD.md（需求契约） 2) 确认 CHECKLIST.md（验收清单） 3) 派活：")
    print("  python dispatch.py \"在 <cwd> 目录：<任务>。要求：1) <功能>；2) 附带 selftest；3) py_compile；4) git commit。\" --timeout 300")

if __name__ == "__main__":
    main()
