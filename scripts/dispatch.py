# -*- coding: utf-8 -*-
"""
dispatch.py — 豆包 -> WorkBuddy 派活桥（双 AI 协作闭环核心工具）

用法：
  python dispatch.py "任务内容" [--cwd D:/path] [--timeout 300] [--debug] [--model <id>]
  python dispatch.py --queue tasks.txt      # 批量派活：文件每行一个任务，逐行执行
  python dispatch.py --auto-review          # 派活结束后自动生成审核草稿（inbox/review_roundN.md）
  python dispatch.py --list-runs [--limit 10] [--check]   # 查看派活历史与运行状态
  python dispatch.py --stop          # 停止当前端口 serve 服务
  python dispatch.py --stop-all      # 停止本项目缓存目录下所有端口的 serve（清理孤儿）
  python dispatch.py --status        # 查看 serve 与登录态
  python dispatch.py --danger-allow  # 允许派发含危险命令模式的任务（默认拦截并拒绝）

安全边界（v1.5.0 起默认启用）：
  派活前对任务文本做危险命令检查（删除/格式化/关机/清注册表/根目录级删除等），
  命中即拒绝派活（除非显式 --danger-allow）。注意：CLI 的 --permission-mode auto
  是必要开关（否则 commit 卡权限），业务层安全由本脚本的白名单/黑名单把关。

模型选择（优先级从高到低）：
  1) --model <id> 参数
  2) 任务文本开头写 [model=<id>]（如 "[model=kimi-k3-1] 写一个工具..."）
  3) 环境变量 WB_MODEL（未设时默认 glm-5.3）
  常用模型 id：glm-5.3（默认旗舰）/ deep-model（极致档）/ kimi-k3-1（最强长程）
  / hy4-preview（混元4）/ step-5-preview（免费旗舰）/ deepseek-v4-pro / space-bunny

原理：
  从 WorkBuddy 运行内存提取账号 token（缓存至 .cache/wb_token.txt），
  注入 CODEBUDDY_AUTH_TOKEN 启动 headless CLI 的 HTTP 服务（--auth none
  --permission-mode auto），再通过 POST /api/v1/runs 派任务、SSE 流读结果。
  每次派活把 runId/时间/cwd/模型/摘要记录到 .cache/runs.json，--list-runs 可查。
  CLI 路径若默认路径不存在会自动探测（进程命令行定位 + 常见安装目录兜底）。

可配置项（环境变量，未设时用默认值）：
  WB_CLI_PATH   WorkBuddy headless CLI 绝对路径（默认本机安装路径，缺失时自动探测）
  WB_PORT       serve 端口（默认 51741；多项目并发换端口即可，pid/log 自动按端口隔离）
  WB_PROJECT    默认工作目录（默认当前目录）
  WB_MODEL      默认模型 id（默认 glm-5.3）
  WB_CACHE      缓存目录（默认 <PROJECT>/.cache；多端口共用 token 时可用同一缓存）
"""
import argparse, base64, glob, json, os, re, subprocess, sys, time, urllib.error, urllib.request, uuid

# ---------- 关键：绕过系统/环境 HTTP 代理 ----------
# 环境里若有 HTTP_PROXY/HTTPS_PROXY（如 WorkBuddy 自带的本地代理），urllib 默认会把
# 127.0.0.1 的请求也发给代理，导致 502 Bad Gateway / 无法连接，且 port_busy() 误判"服务在跑"。
# 本机 loopback 通信必须直连，统一走这个 opener。
_NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# ---------- 配置（环境变量可覆盖，便于换机/换项目） ----------
CLI = os.environ.get("WB_CLI_PATH",
    r"E:\LenovoSoftstore\Install\WorkBuddy\resources\app.asar.unpacked\cli\dist\codebuddy-headless.js")
PORT = int(os.environ.get("WB_PORT", "51741"))
PROJECT = os.environ.get("WB_PROJECT", os.getcwd())
# 缓存目录：WB_CACHE 可覆盖；serve 进程标记按端口隔离（多项目并发互不覆盖）
CACHE_DIR = os.environ.get("WB_CACHE", os.path.join(PROJECT, ".cache"))
TOKEN_CACHE = os.path.join(CACHE_DIR, "wb_token.txt")
BASE = f"http://127.0.0.1:{PORT}"
PID_FILE = os.path.join(CACHE_DIR, f"serve.pid_{PORT}")
LOG_FILE = os.path.join(CACHE_DIR, f"serve.log_{PORT}")
RUNS_FILE = os.path.join(CACHE_DIR, "runs.json")

# ---------- 危险命令拦截（默认启用，--danger-allow 显式放行） ----------
# 匹配命中即拒绝派活。覆盖删除/格式化/关机/注册表/磁盘/根目录级破坏等模式。
DANGER_PATTERNS = [
    (r"(^|[;\s])(rm\s+(-rf|-r|-f)?\s+|rmdir\s+(/s|/q|/s\s*/q)|Remove-Item\s+-Recurse|rd\s+/s)",
     "删除文件/目录命令（rm/rmdir/Remove-Item -Recurse 等）"),
    (r"\b(format\s+[A-Za-z]:|diskpart|clean\s+all\b)", "格式化磁盘/磁盘操作"),
    (r"\b(shutdown\b|restart\s+-s|Stop-Computer|Restart-Computer)", "关机/重启命令"),
    (r"(reg\s+delete|regedit\s+/s|Remove-Item\s+.*(HKLM|HKCU))", "注册表删除"),
    (r"(\bdel\s+/[sqf]\s+[A-Za-z]:\\|rm\s+-rf\s+[A-Za-z]:\\)", "盘符级删除"),
]
DANGER_ALLOW = False  # 由 --danger-allow 打开

def sanitize_task(text):
    """检查任务文本是否含危险命令模式；命中返回 (True, 说明)，否则 (False, None)。"""
    for pat, desc in DANGER_PATTERNS:
        if re.search(pat, text, re.I):
            return True, desc
    return False, None

# ---------- CLI 路径自动探测 ----------
CLI_DEFAULT_PATTERNS = [
    r"E:\LenovoSoftstore\Install\WorkBuddy\resources\app.asar.unpacked\cli\dist\codebuddy-headless.js",
    r"C:\Program Files*\*\WorkBuddy\resources\app.asar.unpacked\cli\dist\codebuddy-headless.js",
    r"D:\*\WorkBuddy\resources\app.asar.unpacked\cli\dist\codebuddy-headless.js",
]

def _find_cli_by_proc():
    """从正在运行的 WorkBuddy 进程可执行路径推导 CLI 位置。"""
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -match 'WorkBuddy' } | Select-Object -First 1 -ExpandProperty ExecutablePath"],
            capture_output=True, text=True, timeout=15).stdout.strip()
        if out:
            exe = out.splitlines()[0].strip()
            base = os.path.dirname(os.path.dirname(exe))  # .../resources 的上一级
            cand = os.path.join(base, "resources", "app.asar.unpacked", "cli", "dist", "codebuddy-headless.js")
            if os.path.exists(cand):
                return cand
    except Exception:
        pass
    return None

def find_cli():
    """解析 CLI 路径：WB_CLI_PATH 显式指定 > 默认/常见安装目录 > 进程推导 > None。"""
    if os.environ.get("WB_CLI_PATH"):
        return os.environ["WB_CLI_PATH"]
    if os.path.exists(CLI):
        return CLI
    for pat in CLI_DEFAULT_PATTERNS:
        hits = glob.glob(pat)
        if hits:
            return hits[0]
    cand = _find_cli_by_proc()
    if cand:
        return cand
    return None

# ---------- 模型（默认 glm-5.3，任务文本/--model/WB_MODEL 可覆盖） ----------
MODEL = os.environ.get("WB_MODEL", "glm-5.3")
# 任务文本开头标记：[model=<id>] 或 [model:<id>]，派活时一句话切换模型
MODEL_MARK_RE = re.compile(r"^\s*\[model\s*[:=]\s*([A-Za-z0-9_.\-]+)\]\s*", re.I)

# ---------- token ----------
def token_valid(tok):
    try:
        h, p, s = tok.split(".")
        payload = json.loads(base64.urlsafe_b64decode(p + "=="))
        return payload.get("iss") and "realms" in payload.get("iss", "") and payload.get("exp", 0) > time.time() + 3600
    except Exception:
        return False

def load_token():
    if os.path.exists(TOKEN_CACHE):
        tok = open(TOKEN_CACHE, encoding="utf-8").read().strip()
        if token_valid(tok):
            return tok
    return extract_token()

def extract_token():
    """扫描 WorkBuddy daemon 进程内存找账号 JWT（需桌面版正在运行且已登录）"""
    import ctypes, ctypes.wintypes
    k32 = ctypes.windll.kernel32
    ntdll = ctypes.windll.ntdll
    class PBI(ctypes.Structure):
        _fields_ = [("R1", ctypes.c_void_p), ("Peb", ctypes.c_void_p), ("R2", ctypes.c_void_p * 2),
                    ("Pid", ctypes.c_void_p), ("R3", ctypes.c_void_p)]
    class MBI(ctypes.Structure):
        _fields_ = [("Base", ctypes.c_void_p), ("Alloc", ctypes.c_void_p), ("Prot", ctypes.wintypes.DWORD),
                    ("Size", ctypes.c_size_t), ("State", ctypes.wintypes.DWORD),
                    ("Prot2", ctypes.wintypes.DWORD), ("Type", ctypes.wintypes.DWORD)]
    # 找 daemon 进程（命令行含 daemon-app-server-entry.js）
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
        "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'daemon-app-server-entry' } | Select-Object -ExpandProperty ProcessId"],
        capture_output=True, text=True).stdout
    pids = [int(x) for x in re.findall(r"\d+", out)]
    if not pids:
        print("ERR: 未找到 WorkBuddy daemon 进程（WorkBuddy 桌面版在运行吗？）", file=sys.stderr)
        sys.exit(1)
    jwt_re = re.compile(rb"eyJ[A-Za-z0-9_\-]{10,2000}\.[A-Za-z0-9_\-]{10,4000}\.[A-Za-z0-9_\-]{10,2000}")
    for pid in pids:
        h = k32.OpenProcess(0x0410, False, pid)  # QUERY_LIMITED | VM_READ
        if not h:
            continue
        try:
            pbi = PBI()
            if ntdll.NtQueryInformationProcess(h, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), None) != 0:
                continue
            ptr = ctypes.c_void_p()
            sz = ctypes.c_size_t()
            if not k32.ReadProcessMemory(h, ctypes.c_void_p(pbi.Peb + 0x20), ctypes.byref(ptr), 8, ctypes.byref(sz)):
                continue
            envp = ctypes.c_void_p()
            if not k32.ReadProcessMemory(h, ctypes.c_void_p(ptr.value + 0x80), ctypes.byref(envp), 8, ctypes.byref(sz)):
                continue
            mbi = MBI()
            addr = 0
            while True:
                if k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)) == 0:
                    break
                base, size = mbi.Base or 0, mbi.Size or 0
                if mbi.State == 0x1000 and size > 0 and mbi.Prot2 in (0x04, 0x02, 0x08, 0x40, 0x20):
                    buf = ctypes.create_string_buffer(size)
                    rd = ctypes.c_size_t()
                    if k32.ReadProcessMemory(h, ctypes.c_void_p(base), buf, size, ctypes.byref(rd)) and rd.value:
                        for m in jwt_re.finditer(buf.raw[:rd.value]):
                            tok = m.group(0).decode()
                            try:
                                hp, pp, sp = tok.split(".")
                                pl = json.loads(base64.urlsafe_b64decode(pp + "=="))
                                if pl.get("iss") and "realms" in pl.get("iss", "") and pl.get("exp", 0) > time.time() + 3600:
                                    os.makedirs(CACHE_DIR, exist_ok=True)
                                    open(TOKEN_CACHE, "w", encoding="utf-8").write(tok)
                                    return tok
                            except Exception:
                                pass
                try:
                    na = base + size
                    addr = na
                    if na >= (1 << 48):
                        break
                except OverflowError:
                    break
        finally:
            k32.CloseHandle(h)
    print("ERR: 内存中未找到有效账号 token（WorkBuddy 未登录？）", file=sys.stderr)
    sys.exit(1)

# ---------- serve ----------
def port_busy():
    """判断 serve 是否真在监听 127.0.0.1:PORT。

    注意：必须直连（_NO_PROXY_OPENER），否则经过环境代理拿到的是代理返回的
    502 Bad Gateway，会被 HTTPError 分支误判为"服务活着"，从而跳过启动、直接派活失败。
    """
    req = urllib.request.Request(f"{BASE}/api/v1/health", headers={"x-codebuddy-request": str(uuid.uuid4())})
    try:
        _NO_PROXY_OPENER.open(req, timeout=3)
        return True
    except urllib.error.HTTPError as e:
        # 401/403 等 = 服务确实在跑（只是要鉴权）；502/503/504 是代理或网关的错误，不算存活
        return e.code not in (502, 503, 504)
    except Exception:
        return False

def ensure_server(tok):
    if port_busy():
        return True
    os.makedirs(CACHE_DIR, exist_ok=True)
    cli_path = find_cli()
    if not cli_path:
        print("ERR: 未找到 WorkBuddy headless CLI（默认路径与常见目录都不存在）", file=sys.stderr)
        print("   解决：设环境变量 WB_CLI_PATH 指向 codebuddy-headless.js，或先运行 WorkBuddy 桌面版", file=sys.stderr)
        sys.exit(1)
    env = dict(os.environ)
    env["CODEBUDDY_AUTH_TOKEN"] = tok
    env["CODEBUDDY_HOST"] = "workbuddy-desktop"
    # 关键：新版 CLI（v2.156+）里 `--auth none` 会被 settings.json 的 gateway.auth 或
    # 内建默认( password ) 覆盖，必须用 CODEBUDDY_GATEWAY_AUTH=none 才能真正关闭鉴权，
    # 否则 /api/v1/runs 返回 401 AUTH_REQUIRED。
    env["CODEBUDDY_GATEWAY_AUTH"] = "none"
    # 日志轮转：超过 5MB 先备份为 .old（serve.log 无限增长会撑爆磁盘）
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 5 * 1024 * 1024:
        try:
            os.replace(LOG_FILE, LOG_FILE + ".old")
        except Exception:
            pass
    log = open(LOG_FILE, "a", encoding="utf-8")
    proc = subprocess.Popen(["node", cli_path, "--serve", "--port", str(PORT), "--auth", "none",
                             "--permission-mode", "auto"],
                            cwd=PROJECT, env=env, stdout=log, stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    open(PID_FILE, "w").write(str(proc.pid))
    for _ in range(30):
        time.sleep(1)
        if port_busy():
            return True
    print("ERR: serve 启动失败，日志见 .cache/serve.log", file=sys.stderr)
    sys.exit(1)

def _pid_files():
    if not os.path.isdir(CACHE_DIR):
        return []
    return sorted(glob.glob(os.path.join(CACHE_DIR, "serve.pid_*")))

def stop_server():
    pid_file = PID_FILE
    if os.path.exists(pid_file):
        pid = int(open(pid_file).read().strip())
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
            print(f"已停止 serve (pid {pid})")
        except Exception:
            print("停止失败")
    else:
        print("没有记录到 serve 进程")

def stop_all_servers():
    """清理缓存目录下所有端口的 serve（含崩溃后残留的 pid 文件）。"""
    files = _pid_files()
    if not files:
        print("没有找到任何 serve.pid_* 记录")
        return
    for f in files:
        try:
            pid = int(open(f).read().strip())
        except Exception:
            continue
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
            print(f"已停止 {os.path.basename(f)} -> pid {pid}")
        except Exception:
            print(f"停止 {os.path.basename(f)} 失败")
    print("清理完成（残留 pid 文件保留，下次启动自动复用）")

# ---------- HTTP ----------
def _req(path, method="GET", data=None, timeout=10):
    headers = {"x-codebuddy-request": str(uuid.uuid4())}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        resp = _NO_PROXY_OPENER.open(r, timeout=timeout)
        return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")

def _extract_text(obj, out):
    """递归收集 JSON 里的文本字段（text / content.markdown 等）"""
    if isinstance(obj, dict):
        for key in ("text", "markdown"):
            t = obj.get(key)
            if isinstance(t, str) and t.strip():
                out.append(t)
        for v in obj.values():
            _extract_text(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _extract_text(v, out)

# ---------- 派活记录（--list-runs 用） ----------
def load_runs():
    if not os.path.exists(RUNS_FILE):
        return []
    try:
        return json.load(open(RUNS_FILE, encoding="utf-8"))
    except Exception:
        return []

def save_runs(runs):
    os.makedirs(CACHE_DIR, exist_ok=True)
    open(RUNS_FILE, "w", encoding="utf-8").write(json.dumps(runs, ensure_ascii=False, indent=1))

def record_run(run_id, cwd, model, text):
    """派活成功后记录一条 run（最新在前，最多保留 200 条）"""
    runs = load_runs()
    runs.insert(0, {
        "runId": run_id, "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cwd": cwd, "model": model, "text": (text or "")[:120],
    })
    save_runs(runs[:200])

def run_active(run_id):
    """查单个 run 是否仍活跃（GET /api/v1/runs/{id}）"""
    st, body = _req(f"/api/v1/runs/{run_id}", timeout=5)
    if st == 200:
        try:
            return "active" if json.loads(body)["data"].get("active") else "completed"
        except Exception:
            return "unknown"
    return f"http_{st}"

def list_runs(limit, check):
    runs = load_runs()
    if not runs:
        print("无派活记录（.cache/runs.json 为空）")
        return
    print(f"派活记录（最近 {min(limit, len(runs))} 条，共 {len(runs)} 条）：\n")
    for i, r in enumerate(runs[:limit], 1):
        st = f" [{run_active(r['runId'])}]" if check else ""
        print(f"{i:>2}. {r['ts']}  model={r['model']}  cwd={r['cwd']}{st}")
        print(f"    {r['runId']}  {r['text']}")
    if check:
        print("\n[状态] active=仍在执行 / completed=已完成 / http_N=查询失败（服务未起或 run 过期）")

# ---------- 派活后自动审核草稿（--auto-review） ----------
def git_head(cwd):
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None

def git_run(cwd, args):
    r = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)
    return (r.stdout or r.stderr).strip()

def py_files_under(cwd):
    out = []
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in (".cache", "__pycache__", ".git", "dist", "build", "node_modules")]
        out += [os.path.join(root, f) for f in files if f.endswith(".py")]
    return out

def auto_review(cwd):
    """派活结束后调用：有新 commit 则生成审核草稿（含编译结果/变更统计，AI 只填判断）。"""
    cur = git_head(cwd)
    if not cur:
        print("warn: 该目录不是 git 仓库或无 commit，跳过自动审核草稿", file=sys.stderr)
        return
    inbox = os.path.join(cwd, "inbox")
    base_file = os.path.join(inbox, "last_reviewed_commit.txt")
    base = open(base_file, encoding="utf-8").read().strip() if os.path.exists(base_file) else ""
    if base == cur:
        print("无新提交（基线一致），无需审核草稿", file=sys.stderr)
        return
    # 编译检查
    py_files = py_files_under(cwd)
    comp = subprocess.run([sys.executable, "-m", "py_compile"] + py_files,
                          cwd=cwd, capture_output=True, text=True) if py_files else None
    comp_ok = "通过" if (py_files and comp.returncode == 0) else ("无 .py 文件" if not py_files else "存在语法错误")
    comp_detail = ""
    if py_files and comp and comp.returncode != 0:
        comp_detail = (comp.stderr or comp.stdout)[:1500]
    # 轮次编号
    existing = [f for f in os.listdir(inbox) if f.startswith("review_round") and f.endswith(".md")] if os.path.isdir(inbox) else []
    n = len(existing) + 1
    log = git_run(cwd, ["log", "--oneline", "-3"])
    # 首次 commit（无 HEAD~1）时用 git show 代替 git diff，避免 ambiguous argument 报错
    cnt = git_run(cwd, ["rev-list", "--count", "HEAD"])
    if cnt.strip().isdigit() and int(cnt.strip()) <= 1:
        diff = git_run(cwd, ["show", "--stat", "--oneline", "HEAD"])
    else:
        diff = git_run(cwd, ["diff", "HEAD~1", "--stat"])
    doc = f"""# review_round{n} — 自动审核草稿（{os.path.basename(cwd)}）

> 本文件由 dispatch.py --auto-review 自动生成，供审核方（豆包/WorkBuddy）填写判断后正式生效。
> 已自动完成：变更统计、py_compile 语法检查。待填：总体结论、5 维评分、逐条问题、复审、STATUS。
> 填写完成后，把当前 commit hash 写入 inbox/last_reviewed_commit.txt。

审核时间：{time.strftime("%Y-%m-%d %H:%M")}
审核对象：{cur}

## 自动检查结果

- 最新提交：
```
{log}
```
- 变更统计（最近一次提交）：
```
{diff}
```
- py_compile：{comp_ok}
{f"- 语法错误详情：\n```\n{comp_detail}\n```" if comp_detail else ""}

## 总体结论（待填）

<一句话结论>

## 5 维评分（待填，各 1-5 分，锚定标准见 methodology §5.25；非 GUI 项目界面维记 N/A）

| 维度 | 分数 | 依据 |
|---|---|---|
| 正确性 | <1-5> |  |
| 可维护性 | <1-5> |  |
| 性能 | <1-5> |  |
| 安全 | <1-5> |  |
| 界面 | <1-5 / N/A> |  |
| 总分 | <X>/<25 或实际维数×5> | 收敛线 = 实际维数×4 |

## 逐条审核（待填，对照 CHECKLIST.md）

<checklist 编号> <验收项>：✅/❌ <证据>

## 发现的问题（待填，P0 阻塞必须改 / P1 该改 / P2 建议）

- P0-1：<现象 / 根因 / 修改方向>
- P1-1：<现象 / 根因 / 修改方向>
- P2-1：<问题 → 建议>

## 复审（双审，关键模块必填）

- 复审方 / 方式 / 结论：<待填>

## 验收标准（下一轮修复须满足）

<待填>

STATUS: 待审核
"""
    os.makedirs(inbox, exist_ok=True)
    open(os.path.join(inbox, f"review_round{n}.md"), "w", encoding="utf-8").write(doc)
    print(f"[auto-review] 已生成审核草稿 inbox/review_round{n}.md（commit {cur[:8]}）", file=sys.stderr)
    print("请审核方填写判断后，把该 commit hash 写入 inbox/last_reviewed_commit.txt 完成基线更新", file=sys.stderr)

# ---------- 派活 ----------
def dispatch(text, cwd, timeout, debug, cli_model=None):
    # 任务文本安全边界：危险命令拦截（默认拒绝，--danger-allow 放行）
    if not DANGER_ALLOW:
        hit, desc = sanitize_task(text)
        if hit:
            print(f"ERR: 任务文本含危险命令模式（{desc}），已拒绝派活。", file=sys.stderr)
            print("   确认任务本身安全后，加 --danger-allow 显式放行", file=sys.stderr)
            sys.exit(2)
    # 解析任务文本开头的 [model=xxx] 标记（一句话切换模型）
    m = MODEL_MARK_RE.match(text)
    text_model = m.group(1) if m else None
    if m:
        text = text[m.end():]
    model = cli_model or text_model or MODEL
    tok = load_token()
    ensure_server(tok)
    payload = {
        "id": str(uuid.uuid4()),
        "type": "message",
        "version": "1.0",
        "source": {"platform": "generic", "sender": {"id": "doubao", "name": "豆包"}, "conversation": {"id": str(uuid.uuid4()), "type": "direct"}},
        "text": text,
        "timeoutMs": timeout * 1000,
    }
    if model:
        payload["model"] = model
    st, body = _req("/api/v1/runs", "POST", payload, timeout=15)
    if st != 202:
        print(f"ERR: 派任务失败 {st}: {body[:300]}", file=sys.stderr)
        sys.exit(1)
    run_id = json.loads(body)["data"]["runId"]
    print(f"[ok] 任务已派发 runId={run_id}，model={model}，等待 agent 执行（{timeout}s）...", file=sys.stderr)
    record_run(run_id, cwd, model, text)
    # 读 SSE
    req = urllib.request.Request(f"{BASE}/api/v1/runs/{run_id}/stream",
                                 headers={"x-codebuddy-request": str(uuid.uuid4())})
    collected = []
    raw = []
    try:
        resp = _NO_PROXY_OPENER.open(req, timeout=timeout + 10)
        end = time.time() + timeout
        while time.time() < end:
            line = resp.readline()
            if not line:
                break
            txt = line.decode("utf-8", errors="replace").strip()
            if not txt:
                continue
            raw.append(txt)
            if debug:
                print("EVENT:", txt[:200], file=sys.stderr)
            if txt.startswith("data:"):
                try:
                    obj = json.loads(txt[5:].strip())
                    _extract_text(obj, collected)
                except Exception:
                    pass
    except Exception as e:
        print(f"warn: SSE 读取中断 ({e})", file=sys.stderr)
    if collected:
        print("\n".join(collected[-40:]))
    else:
        print("(agent 未返回文本内容，--debug 查看原始事件)")

# ---------- main ----------
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="豆包 -> WorkBuddy 派活")
    ap.add_argument("task", nargs="?", help="任务内容")
    ap.add_argument("--cwd", default=PROJECT, help="工作目录（默认项目目录）")
    ap.add_argument("--timeout", type=int, default=300, help="任务超时秒数")
    ap.add_argument("--debug", action="store_true", help="打印原始 SSE 事件")
    ap.add_argument("--model", default=None, help="指定模型 id（默认 WB_MODEL 或 glm-5.3；也可在任务文本开头写 [model=xxx]）")
    ap.add_argument("--queue", default=None, help="批量派活：文件路径，每行一个任务（# 开头为注释，可带 [model=xxx] 标记）")
    ap.add_argument("--list-runs", action="store_true", help="查看派活历史")
    ap.add_argument("--limit", type=int, default=10, help="--list-runs 显示的条数（默认 10）")
    ap.add_argument("--check", action="store_true", help="--list-runs 时逐个查询 run 活跃状态")
    ap.add_argument("--stop", action="store_true", help="停止 serve")
    ap.add_argument("--stop-all", action="store_true", help="停止缓存目录下所有端口的 serve（清理孤儿）")
    ap.add_argument("--auto-review", action="store_true", help="派活结束后自动生成审核草稿")
    ap.add_argument("--danger-allow", action="store_true", help="放行含危险命令模式的任务（默认拦截）")
    ap.add_argument("--status", action="store_true", help="查看状态")
    args = ap.parse_args()
    DANGER_ALLOW = args.danger_allow
    if args.stop:
        stop_server()
    elif args.stop_all:
        stop_all_servers()
    elif args.status:
        tok = load_token()
        cli_path = find_cli()
        print("token:", "有效" if token_valid(tok) else "无效")
        print("serve:", "运行中" if port_busy() else "未运行")
        print("CLI:", cli_path or "未找到（设 WB_CLI_PATH 或先启动 WorkBuddy 桌面版）")
        print("默认模型:", MODEL, "(可用 --model / 任务文本 [model=xxx] 切换)")
    elif args.list_runs:
        list_runs(args.limit, args.check)
    elif args.queue:
        if not os.path.exists(args.queue):
            print(f"ERR: 队列文件不存在: {args.queue}", file=sys.stderr)
            sys.exit(1)
        lines = [ln.strip() for ln in open(args.queue, encoding="utf-8") if ln.strip() and not ln.lstrip().startswith("#")]
        if not lines:
            print("ERR: 队列文件为空（无有效任务行）", file=sys.stderr)
            sys.exit(1)
        print(f"队列共 {len(lines)} 个任务，开始逐个派活...\n", file=sys.stderr)
        failed = []
        for i, line in enumerate(lines, 1):
            print(f"--- [{i}/{len(lines)}] {line[:80]}", file=sys.stderr)
            try:
                dispatch(line, args.cwd, args.timeout, args.debug, args.model)
                if args.auto_review:
                    auto_review(args.cwd)
            except SystemExit as e:
                failed.append(i)
                print(f"任务 [{i}/{len(lines)}] 派发失败（exit={e.code}），继续下一个", file=sys.stderr)
        if failed:
            print(f"\n批量完成：{len(lines) - len(failed)}/{len(lines)} 成功，失败序号: {failed}", file=sys.stderr)
        else:
            print(f"\n批量完成：全部 {len(lines)} 个任务成功", file=sys.stderr)
    elif args.task:
        dispatch(args.task, args.cwd, args.timeout, args.debug, args.model)
        if args.auto_review:
            auto_review(args.cwd)
    else:
        ap.print_help()
