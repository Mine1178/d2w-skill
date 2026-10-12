# -*- coding: utf-8 -*-
"""
sync_copies.py — 同步 d2w 技能到宿主注册的旧副本（do2wo / doubao-workbuddy-collab）

背景：豆包宿主会把已注册技能目录"维持存在"（硬删后约 45-90 秒自动重建，
      且重建内容是旧快照）。为保证任意入口触发都是最新逻辑，用本脚本把 d2w
      全量镜像到副本，并还原各自 frontmatter name。

用法：
  python sync_copies.py            # 全量同步（d2w -> do2wo + doubao-workbuddy-collab）
  python sync_copies.py --check    # 只检查差异，不写入

前置：d2w 为唯一权威版本；修改技能后跑一次本脚本即可三入口一致。
"""
import argparse, os, re, shutil, sys, time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
USER_SKILLS = os.path.dirname(SKILL_DIR)  # workspace/.user_skills

SRC = SKILL_DIR
COPIES = {
    "do2wo": "Do2Wo",
    "doubao-workbuddy-collab": "doubao-workbuddy-collab",
}
EXCLUDE = {".git"}

def files_under(base):
    out = {}
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in EXCLUDE and d != "__pycache__"]
        for f in files:
            p = os.path.join(root, f)
            rel = os.path.relpath(p, base)
            out[rel] = os.path.getsize(p)
    return out

def read_first(src_md):
    try:
        return open(src_md, encoding="utf-8").read().split("\n", 2)[1]
    except Exception:
        return ""

def sync(apply):
    results = []
    src_files = files_under(SRC)
    for name, front in COPIES.items():
        dst = os.path.join(USER_SKILLS, name)
        if not os.path.isdir(dst):
            results.append(f"{name}: 目标目录不存在，跳过")
            continue
        dst_files = files_under(dst)
        diff = []
        for rel in sorted(set(src_files) | set(dst_files)):
            if rel not in src_files:
                diff.append(f"  仅副本有: {rel}")
            elif rel not in dst_files:
                diff.append(f"  仅源有: {rel}")
            elif src_files[rel] != dst_files[rel]:
                diff.append(f"  大小不同: {rel}")
        if diff:
            if apply:
                bak = dst + ".bak_" + time.strftime("%Y%m%d_%H%M%S")
                shutil.move(dst, bak)
                shutil.copytree(SRC, dst, ignore=shutil.ignore_patterns(".git", "__pycache__"))
                try:
                    shutil.rmtree(bak)
                except Exception:
                    pass
                # 还原 frontmatter name
                md = os.path.join(dst, "SKILL.md")
                txt = open(md, encoding="utf-8").read()
                txt = re.sub(r"^name:.*$", f"name: {front}", txt, count=1, flags=re.M)
                open(md, "w", encoding="utf-8", newline="").write(txt)
                results.append(f"{name}: 已同步（frontmatter -> {front}）")
            else:
                results.append(f"{name}: 有差异（--check 模式，未写入）\n" + "\n".join(diff[:8]))
        else:
            results.append(f"{name}: 无差异（与 d2w 一致）")
    return results

def main():
    ap = argparse.ArgumentParser(description="同步 d2w 到宿主注册副本")
    ap.add_argument("--check", action="store_true", help="只检查差异不写入")
    args = ap.parse_args()
    for r in sync(apply=not args.check):
        print(r)

if __name__ == "__main__":
    main()
