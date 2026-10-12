# -*- coding: utf-8 -*-
"""
extract_jwt.py — 备用工具：全量扫描 WorkBuddy daemon 进程内存中的所有 JWT
用途：当 dispatch.py 内嵌提取失败、或需要人工查看 token 情况时使用。
用法：python extract_jwt.py <PID1> [PID2 ...] [--out 输出文件]
获取 PID：powershell "Get-CimInstance Win32_Process | ? { $_.CommandLine -match 'daemon-app-server-entry' } | select ProcessId,Name"
"""
import ctypes, ctypes.wintypes, re, sys, base64, json, os

kernel32 = ctypes.windll.kernel32
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.wintypes.DWORD),
        ("Protect", ctypes.wintypes.DWORD),
        ("Type", ctypes.wintypes.DWORD),
    ]

MEM_COMMIT = 0x1000
RW_PROTECTS = (0x04, 0x02, 0x08, 0x40, 0x20)

def extract_full(pid, max_mb=1500, out=None):
    h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        print(f'PID {pid}: OpenProcess failed')
        return
    mbi = MEMORY_BASIC_INFORMATION()
    addr = ctypes.c_void_p(0)
    total = 0
    jwt_re = re.compile(rb'eyJ[A-Za-z0-9_\-]{10,2000}\.[A-Za-z0-9_\-]{10,4000}\.[A-Za-z0-9_\-]{10,2000}')
    found = set()
    while True:
        if total > max_mb * 1024 * 1024:
            break
        r = kernel32.VirtualQueryEx(h, addr, ctypes.byref(mbi), ctypes.sizeof(mbi))
        if r == 0:
            break
        base = mbi.BaseAddress or 0
        size = mbi.RegionSize or 0
        if mbi.State == MEM_COMMIT and size > 0 and mbi.Protect in RW_PROTECTS:
            buf = ctypes.create_string_buffer(size)
            read = ctypes.c_size_t()
            if kernel32.ReadProcessMemory(h, ctypes.c_void_p(base), buf, size, ctypes.byref(read)) and read.value > 0:
                data = buf.raw[:read.value]
                total += len(data)
                for m in jwt_re.finditer(data):
                    tok = m.group(0)
                    payload = {}
                    try:
                        parts = tok.split(b'.')
                        payload = json.loads(base64.urlsafe_b64decode(parts[1] + b'=='))
                    except Exception:
                        pass
                    if tok not in found and len(tok) > 100:
                        found.add(tok)
                        iss = payload.get('iss', '?')
                        exp = payload.get('exp', '?')
                        print(f'[{len(found)}] len={len(tok)} iss={iss} exp={exp}')
                        if out:
                            with open(out, 'a', encoding='utf-8') as f:
                                f.write(tok.decode('utf-8') + '\n')
        try:
            na = base + size
            addr = ctypes.c_void_p(na)
            if na >= (1 << 48):
                break
        except OverflowError:
            break
    print(f'  PID {pid}: scanned {total/1024/1024:.0f}MB, unique tokens: {len(found)}')
    kernel32.CloseHandle(h)

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out = None
    if '--out' in sys.argv:
        out = sys.argv[sys.argv.index('--out') + 1]
    for pid in args:
        extract_full(int(pid), out=out)
