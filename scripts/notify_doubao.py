# -*- coding: utf-8 -*-
"""
notify_doubao.py — 模式 B 通知器（WorkBuddy → 豆包）

解决的问题
----------
模式 B 原本是"半自动"：WorkBuddy 把任务写进 inbox/tasks/ 后，
必须由**人**去豆包窗口说一句"看下任务队列"，豆包才会跑 poll_tasks.py。
根因是 poll_tasks.py 没有任何通知能力（无网络/无 subprocess/无推送）。

本脚本把"通知"这一步补上：
  1. 写任务单   inbox/tasks/NNN_<简述>.md（沿用 poll_tasks.py 的序号约定）
  2. 拼指令     把"去读 NNN、执行、写结果、--mark"拼成一段话
  3. 写剪贴板   指令进剪贴板（用户只需 Ctrl+V）
  4. 叫醒豆包   优先直接把豆包主窗口提到前台；找不到才回落 URL 协议
  5. 可选自动发 --send 时模拟 Ctrl+V + Enter（需先 --calibrate 标定）

实测依据（2026-10-12，本机）
----------------------------
* 豆包**没有** headless CLI / 本地 HTTP 命令通道：
  Doubao.exe 确实监听 127.0.0.1:49853，但 /、/api/*、/v1/*、/mcp 等
  22 个路径全部 404，POST 同样 404 → 不能像 A 方向那样 API 直连。
* `doubao://` 协议已注册（HKCR\\doubao，URL Protocol），
  命令 = DoubaoLinkRouter.exe --single-argument %1，实测 rc=0 且
  telemetry/events.json 记录 selected_target=doubao、doubao_state=foreground。
* 但 URL **带不了内容**：链路最终打开的窗口标题是
    chrome://doubaoapp/active-chat?__saman_link_router_event_id=...&__saman_link_router_handler_product=doubao
  我注入的 ?text=hello / ?query=hello 被 LinkRouter 规范化丢弃。
  → 结论：URL 只能"叫醒"，内容只能走剪贴板 + 按键模拟。

剪贴板被锁时的降级（v1.5.17 新增）
------------------------------
* 实测（2026-10-13，本机）：系统剪贴板会被 **WorkBuddy(Chromium 应用) 的
  Chrome_MessageWindow 稳定锁定**（OpenClipboard 稳定报 error 5 拒绝访问，
  PowerShell Get-Clipboard 同样失败），导致剪贴板方案不可用。
* 此时两条路（都不依赖剪贴板）：
  - `--send` 检测到剪贴板不可用会**自动降级**为键盘逐字输入；
  - `--type` 强制键盘逐字输入（SendInput KEYEVENTF_UNICODE，支持中文）。
* 键盘输入前建议标定输入框坐标，确保光标点进豆包输入框：
  - 把鼠标移入豆包输入框 → `python notify_doubao.py --pick`（读坐标入缓存）
  - 之后 `--send` 自动用缓存坐标；或临时用 `--click-x/--click-y` 覆盖。

用法
----
  python notify_doubao.py --status
      体检：豆包在不在、主窗口 HWND、LinkRouter 在不在、剪贴板可用否
      （剪贴板不可用会额外打印"当前持有者"，指明被谁锁）

  python notify_doubao.py --task "写一个斐波那契函数" [--cwd D:/proj]
      写任务单 + 拼指令 + 进剪贴板 + 叫醒豆包（不自动发送）

  python notify_doubao.py --file inbox/tasks/001_x.md
      已存在任务单时，只为它发通知（不重复写文件）

  python notify_doubao.py --send --task "..."
      自动发送：剪贴板可用→Ctrl+V+Enter；被锁→自动键盘逐字输入

  python notify_doubao.py --type --send --task "..." --click-x 900 --click-y 700
      强制键盘输入 + 显式点击输入框坐标

  python notify_doubao.py --pick
      标定输入框坐标：先把鼠标移入豆包输入框，再跑（默认等 5 秒读坐标入缓存）

  python notify_doubao.py --calibrate
      标定：激活豆包 → 等 3 秒 → 打印当前前台窗口与焦点，用于判断是否可直接粘贴

  python notify_doubao.py --dry-run --task "..."
      只打印将要做的事，不写文件、不动剪贴板、不碰窗口

依赖：pywin32（win32gui / win32clipboard / win32api）。可选 psutil（仅用于校验进程名）。
"""
import argparse
import ctypes
import ctypes.wintypes as w
import os
import re
import subprocess
import sys
import time

# ---- 本机实测得到的常量（如豆包升级改路径，改这里） ----
LINK_ROUTER = r"C:\Users\11782\AppData\Local\DoubaoLinkRouter\bin\2.30.4\DoubaoLinkRouter.exe"
WAKE_URL = "doubao://doubaoapp/active-chat"
TELEMETRY = r"C:\Users\11782\AppData\Local\DoubaoLinkRouter\telemetry\events.json"
MAIN_SUFFIX = "- 豆包"          # 主窗口标题后缀
MAIN_CLASS = "Chrome_WidgetWin_1"
# --pick 标定出的豆包输入框屏幕坐标缓存（跨项目复用）
CACHE_POS = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "doubao_input_pos.txt")

VK_CONTROL = 0x11
VK_V = 0x56
VK_RETURN = 0x0D
KEYEVENTF_KEYUP = 0x0002
# SendInput / 鼠标
INPUT_KEYBOARD = 0x0001
INPUT_MOUSE = 0x0000
KEYEVENTF_UNICODE = 0x0004
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", w.LONG), ("dy", w.LONG), ("mouseData", w.DWORD),
                ("dwFlags", w.DWORD), ("time", w.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", w.WORD), ("wScan", w.WORD), ("dwFlags", w.DWORD),
                ("time", w.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", w.DWORD), ("wParamL", w.WORD), ("wParamH", w.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", w.DWORD), ("u", _INPUTUNION)]


def _user32():
    return ctypes.windll.user32


# ---------------------------------------------------------------- 剪贴板 owner 检测
def clipboard_owner():
    """返回当前持有系统剪贴板的进程信息，供 --status 排查"剪贴板被谁锁"。

    实测（2026-10-13，本机）：系统剪贴板被 WorkBuddy(Chromium 应用) 的
    Chrome_MessageWindow 稳定锁定，导致 win32clipboard / 剪贴板 Ctrl+V 全部不可用。
    """
    try:
        hwnd = _user32().GetClipboardOwner()
        if not hwnd:
            return None
        pid = w.DWORD()
        _user32().GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        title = ctypes.create_unicode_buffer(256)
        _user32().GetWindowTextW(hwnd, title, 256)
        cls = ctypes.create_unicode_buffer(256)
        _user32().GetClassNameW(hwnd, cls, 256)
        nm = _proc_name(pid.value) or ""
        return {"hwnd": hwnd, "pid": pid.value, "name": nm,
                "title": title.value, "class": cls.value}
    except Exception as e:
        return {"error": "%s %s" % (type(e).__name__, e)}


# ---------------------------------------------------------------- 窗口
def _proc_name(pid):
    try:
        import psutil
        return psutil.Process(pid).name()
    except Exception:
        return ""


def find_doubao_windows():
    """返回豆包主窗口列表 [(hwnd, title)]。

    必须排除 LinkRouter 打开的 chrome://doubaoapp/active-chat 浏览器窗口——
    它是"路由落地页"，不是聊天主窗口，往它上面粘贴是无效的。
    """
    try:
        import win32gui
        import win32process
    except ImportError:
        return []
    out = []

    def cb(h, _):
        if not win32gui.IsWindowVisible(h):
            return
        try:
            if win32gui.GetClassName(h) != MAIN_CLASS:
                return
            t = win32gui.GetWindowText(h) or ""
        except Exception:
            return
        if not t.endswith(MAIN_SUFFIX):
            return
        if "chrome://" in t:
            return
        try:
            _, pid = _thread_pid(h)
            nm = _proc_name(pid)
            if nm and nm.lower() != "doubao.exe":
                return
        except Exception:
            pass
        out.append((h, t))

    try:
        win32gui.EnumWindows(cb, None)
    except Exception:
        pass
    return out


def _thread_pid(h):
    import win32process
    return win32process.GetWindowThreadProcessId(h)


def wake(hwnd=None, use_url=False):
    """把豆包叫到前台。返回 (方式, 详情)。"""
    if not use_url:
        hwnds = find_doubao_windows()
        target = hwnd if hwnd else (hwnds[0][0] if hwnds else None)
        if target:
            try:
                import win32gui
                import win32con
                # 最小化时先还原，否则 SetForegroundWindow 无效
                if win32gui.IsIconic(target):
                    win32gui.ShowWindow(target, win32con.SW_RESTORE)
                    time.sleep(0.4)
                win32gui.SetForegroundWindow(target)
                time.sleep(0.3)
                fg = win32gui.GetWindowText(win32gui.GetForegroundWindow())
                return "window", "HWND=%d 已置前；当前前台=%r" % (target, fg)
            except Exception as e:
                return "window", "置前失败：%s %s" % (type(e).__name__, e)
    if not os.path.exists(LINK_ROUTER):
        return "url", "LinkRouter 不存在：%s" % LINK_ROUTER
    try:
        r = subprocess.run([LINK_ROUTER, "--single-argument", WAKE_URL],
                           capture_output=True, timeout=15)
        return "url", "rc=%d（telemetry: %s）" % (r.returncode, TELEMETRY)
    except Exception as e:
        return "url", "调用失败：%s %s" % (type(e).__name__, e)


# ---------------------------------------------------------------- 剪贴板 owner 检测
def _clip_owner_hint():
    """剪贴板不可用时，打印当前持有者，提示用户排查（如 WorkBuddy 等 Chromium 应用）。"""
    owner = clipboard_owner()
    if not owner:
        print("   剪贴板持有者: <none>（未被锁定，可能是瞬时占用）")
    elif "error" in owner:
        print("   剪贴板持有者: 探测失败 %s" % owner["error"])
    else:
        print("   剪贴板持有者: %s (PID=%s, HWND=%s, class=%s) — 它正持有剪贴板"
              % (owner["name"] or "?", owner["pid"], owner["hwnd"], owner["class"]))
        print("   提示：可改用 --type 键盘逐字输入（不依赖剪贴板），或先关闭该应用的剪贴板功能")


# ---------------------------------------------------------------- 剪贴板
def set_clipboard(text):
    import win32clipboard
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()


def get_clipboard():
    import win32clipboard
    win32clipboard.OpenClipboard()
    try:
        return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
    finally:
        win32clipboard.CloseClipboard()


# ---------------------------------------------------------------- 按键
def tap(vk, down_up_delay=0.05):
    import win32api
    win32api.keybd_event(vk, 0, 0, 0)
    time.sleep(down_up_delay)
    win32api.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(down_up_delay)


def paste_and_enter(paste_delay=0.8):
    """模拟 Ctrl+V 粘贴，然后 Enter 发送。"""
    import win32api
    # Ctrl+V
    win32api.keybd_event(VK_CONTROL, 0, 0, 0)
    tap(VK_V)
    win32api.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(paste_delay)
    # Enter
    tap(VK_RETURN)


# ---------------------------------------------------------------- 鼠标 / 键盘逐字输入（剪贴板被锁时的降级）
def click_at(x, y):
    """把鼠标移到 (x, y) 并左键单击（坐标基于屏幕，像素）。用于先把光标点进豆包输入框。"""
    u = _user32()
    u.SetCursorPos(x, y)
    time.sleep(0.15)
    u.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    u.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.1)


def _send_key(char):
    """SendInput 发送一个 Unicode 字符（KEYEVENTF_UNICODE，支持中文/任意字符，不依赖剪贴板）。"""
    u = _user32()
    inputs = (INPUT * 2)()
    inputs[0].type = INPUT_KEYBOARD
    inputs[0].u.ki = KEYBDINPUT(0, ord(char), KEYEVENTF_UNICODE, 0, 0)
    inputs[1].type = INPUT_KEYBOARD
    inputs[1].u.ki = KEYBDINPUT(0, ord(char), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0)
    return u.SendInput(2, ctypes.byref(inputs), ctypes.sizeof(INPUT))


def type_unicode_text(text, per_char=0.02):
    """逐字符模拟键盘输入 text（任意 Unicode）。目标窗口须先取得键盘焦点。"""
    for ch in text or "":
        _send_key(ch)
        time.sleep(per_char)
    time.sleep(0.1)


def send_via_keyboard(hwnd, text, click=None):
    """降级发送：把豆包窗口置前 → 可选点击输入框坐标 → 逐字符键入 → Enter。

    click: (x, y) 屏幕像素坐标，用于把光标点进豆包输入框（--calibrate 可标定）。
    返回 (模式, 详情)。"""
    import win32gui
    import win32con
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.4)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.4)
        if click:
            click_at(click[0], click[1])
            time.sleep(0.2)
        type_unicode_text(text)
        tap(VK_RETURN)
        return "keyboard", "已逐字键入 %d 字符 + Enter（hwnd=%d, click=%s）" % (
            len(text), hwnd, click)
    except Exception as e:
        return "keyboard", "键盘输入失败：%s %s" % (type(e).__name__, e)


def activate_hwnd(hwnd):
    """激活一个窗口到前台（最小化先还原）。返回是否成功。"""
    import win32gui
    import win32con
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.4)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.4)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- 任务单
def next_seq(tasks_dir):
    seq = 1
    if os.path.isdir(tasks_dir):
        for n in os.listdir(tasks_dir):
            m = re.match(r"(\d+)_", n)
            if m:
                seq = max(seq, int(m.group(1)) + 1)
    return seq


def slug(text, limit=24):
    s = re.sub(r"[\\/:*?\"<>|\s]+", "_", (text or "").strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return (s[:limit] or "task")


def build_instruction(cwd, seq, title, task_path):
    """拼给豆包的一句话指令。要点：让豆包自己读文件、自己跑 poll_tasks.py。

    序号必须三位补零（002 而非 2）——任务单文件名是 NNN_*.md，
    结果单与 --mark 都要与它对齐，否则 poll_tasks.py 的序号集合对不上。
    """
    seq3 = "%03d" % int(seq)
    root = cwd.replace("\\", "/").rstrip("/")
    return (
        "请处理 D2W 协作任务 {seq3}。\n"
        "1) 读任务单：{path}\n"
        "2) 按要求执行（写代码/审核/查资料/润色等）\n"
        "3) 结果写到：{root}/inbox/results/{seq3}_*.md（序号必须与任务单一致）\n"
        "4) 标记完成：python {root}/scripts/poll_tasks.py --mark {seq3}\n"
        "任务标题：{title}"
    ).format(seq3=seq3, path=task_path.replace("\\", "/"), root=root, title=title)


def write_task(cwd, title, body=""):
    tasks = os.path.join(cwd, "inbox", "tasks")
    os.makedirs(tasks, exist_ok=True)
    os.makedirs(os.path.join(cwd, "inbox", "results"), exist_ok=True)
    seq = next_seq(tasks)
    name = "%03d_%s.md" % (seq, slug(title))
    path = os.path.join(tasks, name)
    content = "# 任务 %03d：%s\n\n%s\n" % (seq, title, body or "（详见任务标题）")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return seq, path


# ---------------------------------------------------------------- 主流程
def cmd_status(args):
    print("== notify_doubao 体检 ==")
    hwnds = find_doubao_windows()
    print("豆包主窗口   : %d 个" % len(hwnds))
    for h, t in hwnds:
        print("   HWND=%-10d %s" % (h, t))
    if not hwnds:
        print("   （未找到——豆包可能未运行，或窗口标题不带 \" - 豆包\" 后缀）")
    print("LinkRouter   : %s" % ("存在" if os.path.exists(LINK_ROUTER) else "缺失"))
    print("telemetry    : %s" % ("存在" if os.path.exists(TELEMETRY) else "缺失"))
    try:
        import win32clipboard
        set_clipboard("__d2w_probe__")
        ok = get_clipboard() == "__d2w_probe__"
        print("剪贴板       : %s（会覆盖当前剪贴板内容）" % ("可用" if ok else "异常"))
        if not ok:
            _clip_owner_hint()
    except Exception as e:
        print("剪贴板       : 不可用 %s %s" % (type(e).__name__, e))
        _clip_owner_hint()
    for m in ("win32gui", "win32api", "psutil"):
        try:
            __import__(m)
            print("模块 %-10s: OK" % m)
        except Exception:
            print("模块 %-10s: 缺失（psutil 缺失仅影响进程名校验）" % m)
    return 0


def cmd_calibrate(args):
    """标定焦点：激活豆包后，看前台窗口是谁、焦点能否直接粘贴。"""
    print("== 标定 ==")
    mode, detail = wake(use_url=False)
    print("激活方式     : %s" % mode)
    print("详情         : %s" % detail)
    time.sleep(3)
    try:
        import win32gui
        fg = win32gui.GetForegroundWindow()
        print("3 秒后前台   : HWND=%d %r / class=%s"
              % (fg, win32gui.GetWindowText(fg), win32gui.GetClassName(fg)))
    except Exception as e:
        print("读前台失败   : %s" % e)
    print()
    print("请现在手动在豆包输入框点一下，然后回这里按 Ctrl+V 试粘贴。")
    print("若粘贴成功 → 说明焦点默认不在输入框，--send 前需先加点击坐标；")
    print("若粘贴成功且无需点击 → 可直接用 --send。")
    return 0


def read_pos_cache():
    """读取缓存里的豆包输入框坐标 (x, y)。不存在或损坏返回 None。"""
    if not os.path.exists(CACHE_POS):
        return None
    try:
        with open(CACHE_POS, encoding="utf-8") as f:
            parts = f.read().strip().split(",")
        x, y = int(parts[0]), int(parts[1])
        return (x, y)
    except Exception:
        return None


def cmd_pick(wait=5):
    """标定：请用户把鼠标移到豆包输入框，脚本读取当前位置并写入缓存。

    用法：先把豆包前置、光标放到输入框里，再跑本命令；脚本会等待 wait 秒后读取。
    """
    print("== 标定输入框坐标 ==")
    print("请在 %d 秒内，把鼠标指针移到【豆包输入框】内（无需点击，放下即读）。" % wait)
    time.sleep(wait)
    try:
        pt = w.POINT()
        _user32().GetCursorPos(ctypes.byref(pt))
        x, y = pt.x, pt.y
    except Exception as e:
        print("读取鼠标位置失败：%s %s" % (type(e).__name__, e))
        return 1
    os.makedirs(os.path.dirname(CACHE_POS), exist_ok=True)
    with open(CACHE_POS, "w", encoding="utf-8") as f:
        f.write("%d,%d" % (x, y))
    print("已标定输入框坐标: (%d, %d) → %s" % (x, y, CACHE_POS))
    print("之后 --send 会自动用它点击输入框；也可用 --click-x/--click-y 临时覆盖。")
    return 0


def resolve_click(args):
    """--send 的输入框坐标来源：显式参数 > 缓存。返回 (x,y) 或 None。"""
    if args.click_x is not None and args.click_y is not None:
        return (args.click_x, args.click_y)
    return read_pos_cache()


def main(argv=None):
    ap = argparse.ArgumentParser(description="模式 B 通知器（WorkBuddy → 豆包）")
    ap.add_argument("--cwd", default=os.getcwd(), help="项目根目录（含 inbox/）")
    ap.add_argument("--task", help="任务标题（会写进 inbox/tasks/）")
    ap.add_argument("--body", default="", help="任务正文")
    ap.add_argument("--file", help="已存在的任务单路径（只为它发通知）")
    ap.add_argument("--send", action="store_true", help="自动发送（剪贴板可用→Ctrl+V+Enter；否则自动降级为键盘逐字输入）")
    ap.add_argument("--type", action="store_true", help="强制用键盘逐字输入（跳过剪贴板，剪贴板被锁时用）")
    ap.add_argument("--click-x", type=int, help="豆包输入框屏幕坐标 X（临时覆盖缓存，配合 --type/--send）")
    ap.add_argument("--click-y", type=int, help="豆包输入框屏幕坐标 Y")
    ap.add_argument("--pick", type=int, nargs="?", const=5, help="标定输入框坐标：把鼠标移入豆包输入框后运行（默认等 5 秒）")
    ap.add_argument("--no-clipboard", action="store_true", help="不写剪贴板")
    ap.add_argument("--no-wake", action="store_true", help="不叫醒豆包")
    ap.add_argument("--url", action="store_true", help="强制用 URL 协议叫醒（而非置前主窗口）")
    ap.add_argument("--status", action="store_true", help="体检")
    ap.add_argument("--calibrate", action="store_true", help="标定焦点")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不执行")
    args = ap.parse_args(argv)

    if args.status:
        return cmd_status(args)
    if args.calibrate:
        if args.dry_run:
            print("[dry-run] 将激活豆包主窗口并等待 3 秒")
            return 0
        return cmd_calibrate(args)
    if args.pick is not None:
        if args.dry_run:
            print("[dry-run] 将等待 %d 秒读取鼠标位置并写入缓存" % args.pick)
            return 0
        return cmd_pick(args.pick)

    cwd = os.path.abspath(args.cwd)

    # 1) 任务单
    if args.file:
        path = os.path.abspath(args.file)
        if not os.path.exists(path):
            print("错误：任务单不存在 %s" % path)
            return 2
        m = re.match(r"(\d+)_", os.path.basename(path))
        seq = int(m.group(1)) if m else 0
        title = os.path.splitext(os.path.basename(path))[0]
        wrote = False
    elif args.task:
        seq, path = write_task(cwd, args.task, args.body)
        title = args.task
        wrote = True
    else:
        print("错误：需要 --task 或 --file（或用 --status / --calibrate）")
        return 2

    # 2) 指令
    instr = build_instruction(cwd, seq, title, path.replace("\\", "/"))

    print("任务单       : %s%s" % (path, "（新建）" if wrote else "（已存在）"))
    print("指令预览     :")
    for line in instr.splitlines():
        print("   " + line)

    if args.dry_run:
        print("\n[dry-run] 未写文件 / 未动剪贴板 / 未碰窗口")
        return 0

    # 3) 剪贴板（--type 走键盘，不写剪贴板）
    clip_ok = False
    if not args.no_clipboard and not args.type:
        try:
            set_clipboard(instr)
            clip_ok = True
            print("剪贴板       : 已写入 %d 字符" % len(instr))
        except Exception as e:
            print("剪贴板       : 写入失败 %s %s" % (type(e).__name__, e))
            _clip_owner_hint()
            if not args.send:
                print("   提示：可加 --type 用键盘逐字输入（不依赖剪贴板）")
            clip_ok = False

    # 4) 叫醒
    if not args.no_wake:
        mode, detail = wake(use_url=args.url)
        print("叫醒豆包     : %s — %s" % (mode, detail))

    # 5) 自动发送
    if args.send:
        if args.type or not clip_ok:
            # 键盘逐字路径（--type 强制，或剪贴板不可用时自动降级）
            hwnds = find_doubao_windows()
            if not hwnds:
                print("自动发送     : 跳过——找不到豆包主窗口（豆包未运行？）")
                return 1
            click = resolve_click(args)
            if click:
                print("自动发送     : 将点击输入框坐标 %s 后键盘逐字输入" % (click,))
            mode, detail = send_via_keyboard(hwnds[0][0], instr, click=click)
            print("自动发送     : %s — %s" % (mode, detail))
            if mode == "keyboard" and "失败" in detail:
                return 1
            print("   ⚠ 请目视确认豆包是否真的收到；若没收到，先跑 --pick 标定输入框坐标")
        else:
            time.sleep(1.0)
            try:
                paste_and_enter()
                print("自动发送     : 已模拟 Ctrl+V + Enter")
                print("   ⚠ 请目视确认豆包是否真的收到；若没收到，先跑 --calibrate 标定焦点")
            except Exception as e:
                print("自动发送     : 失败 %s %s" % (type(e).__name__, e))
                return 1
    else:
        if args.type:
            print("下一步       : 需要加 --send 才会键盘输入（或手动在豆包输入框操作）")
        else:
            print("下一步       : 在豆包窗口按 Ctrl+V 粘贴后回车（或加 --send 自动发送，剪贴板被锁时自动用键盘输入）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
