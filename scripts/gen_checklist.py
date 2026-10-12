# -*- coding: utf-8 -*-
"""
gen_checklist.py — 按 PRD 自动生成 CHECKLIST.md 草稿

用法：
  python gen_checklist.py <PRD.md> [--out CHECKLIST.md]

逻辑：
  1. 读取 PRD.md，提取功能点（##/### 标题与 - 列表项中含功能动词的行）
  2. 读取技能内置 CHECKLIST.template.md，把 B 组"核心功能"替换为提取到的功能点条目
     （其余 A~Q 通用组保留，交付后人工删除不适用的组）
  3. 交互类描述（显示/界面/窗口/按钮/鼠标/弹窗等）标为"人工"，其余"自动"

  生成的是草稿：必须由用户/审核方确认后再派活（契约文件规则不变）。
"""
import argparse, os, re, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
TEMPLATE = os.path.join(SKILL_DIR, "assets", "templates", "CHECKLIST.template.md")

FUNC_VERBS = re.compile(
    r"(支持|可以|提供|翻译|显示|保存|记录|朗读|播放|设置|导出|导入|搜索|查询|生成|转换|"
    r"打开|关闭|添加|删除|编辑|查看|发送|接收|同步|备份|恢复|加密|解密|压缩|解压|检测|监控|"
    r"提醒|通知|计算|统计|汇总|筛选|排序|上传|下载|打印|复制|粘贴|功能)"
)
MANUAL_RE = re.compile(r"(显示|界面|窗口|按钮|鼠标|点击|弹窗|菜单|对话框|托盘|快捷键|滚轮|朗读|发音|声音)")
SKIP_SECTIONS = re.compile(r"(背景|目标|概述|简介|运行环境|安装|说明|注意事项|验收标准|优先级|范围|用户|非目标|名词|术语|附录|参考|风险|里程碑|计划)")

def clean(text):
    t = re.sub(r"[#*`>|\[\]()]", "", text).strip()
    t = re.sub(r"\s+", " ", t)
    return t

def extract_features(prd_text):
    feats = []
    for ln in prd_text.splitlines():
        s = ln.strip()
        m = re.match(r"^(#{2,4})\s+(.+)$", s)
        is_list = re.match(r"^[-*]\s+(.+)$", s)
        if m:
            title = clean(m.group(2))
            if SKIP_SECTIONS.search(title):
                continue
            if FUNC_VERBS.search(title) and 4 <= len(title) <= 40:
                feats.append(title)
        elif is_list:
            item = clean(is_list.group(1))
            # 列表项：含功能动词，且不是纯名词/路径/命令
            if FUNC_VERBS.search(item) and 4 <= len(item) <= 48:
                feats.append(item)
    # 去重保序
    seen, out = set(), []
    for f in feats:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out[:30]

def build_b_section(feats):
    if not feats:
        return "| 编号 | 验收项 | 方式 | 结果 |\n|---|---|---|---|\n| B1 | <待按 PRD 补充核心功能> | 自动 | ☐ |"
    rows = ["| 编号 | 验收项 | 方式 | 结果 |", "|---|---|---|---|"]
    for i, f in enumerate(feats, 1):
        way = "人工" if MANUAL_RE.search(f) else "自动"
        rows.append(f"| B{i} | {f} | {way} | ☐ |")
    return "\n".join(rows)

def main():
    ap = argparse.ArgumentParser(description="按 PRD 生成 CHECKLIST.md 草稿")
    ap.add_argument("prd", help="PRD.md 路径")
    ap.add_argument("--out", default="CHECKLIST.md", help="输出路径（默认 CHECKLIST.md）")
    args = ap.parse_args()

    if not os.path.exists(args.prd):
        print(f"ERR: PRD 不存在: {args.prd}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(TEMPLATE):
        print(f"ERR: 找不到技能模板 {TEMPLATE}", file=sys.stderr)
        sys.exit(1)

    prd = open(args.prd, encoding="utf-8").read()
    tmpl = open(TEMPLATE, encoding="utf-8").read()

    feats = extract_features(prd)
    b_section = build_b_section(feats)

    # 替换模板中 B 组段落（## B. ... 到 ## C. 之前）
    m = re.search(r"(## B\..*?)(?=\n## C\.)", tmpl, re.S)
    if not m:
        print("ERR: 模板中未找到 B 组段落", file=sys.stderr)
        sys.exit(1)
    new_tmpl = tmpl[:m.start()] + "## B. 核心功能（按 PRD 自动生成，请人工核对增删）\n" + b_section + "\n" + tmpl[m.end():]

    # 版本头部占位
    new_tmpl = new_tmpl.replace("# <产品名> 验收清单（CHECKLIST）", "# 验收清单（CHECKLIST）")
    new_tmpl = new_tmpl.replace("版本：v0.1 | 对应 PRD：<v0.1>", "版本：v0.1 | 对应 PRD：<确认后填写>")

    # 尾部提示
    new_tmpl += "\n## 生成说明\n\n- 本文件由 gen_checklist.py 按 PRD 自动生成草稿。\n"
    new_tmpl += "- 请人工核对：①删除不适用的组（无 GUI 删 L 组、无打包删 M/N 组等）；②补产品特有验收项；③确认方式标注。\n"
    new_tmpl += "- 确认后作为契约使用，审核方按此逐条打勾。\n"

    open(args.out, "w", encoding="utf-8").write(new_tmpl)
    print(f"已生成 CHECKLIST.md 草稿（提取功能点 {len(feats)} 条）: {args.out}")

if __name__ == "__main__":
    main()
