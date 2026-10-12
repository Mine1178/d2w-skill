# D2W — 双 AI 协作开发闭环

**D2W = Do-to-WorkBuddy / WorkBuddy-to-Do**：豆包 ⇄ 腾讯 WorkBuddy 双 AI 协作开发框架。
一个 AI 派活/审核，另一个 AI 干活，通过 **git commit + inbox 文件信箱**通信，自动跑通
"派活 → 写代码 → 审核 → 意见 → 修改 → 收敛"循环；双向可用、角色可互换；
不止软件开发，一切"可描述、可落盘、可验证"的任务都能用。

---

## ✨ 特性

- **双模式**：模式 A 豆包 → WorkBuddy（API 直连全自动）；模式 B WorkBuddy → 豆包（文件信箱）
- **分模块派活铁律**：一次 1~2 文件 + 每模块立即 commit，SSE 断连也不丢进度
- **管道化审核**：`--auto-review` 自动生成审核草稿，AI 只填判断
- **5 维评分收敛**：正确性/可维护性/性能/安全/界面，收敛线 = 实际评维数 × 4
- **一站式交付**：开发收敛后自动派活打包 EXE → Inno 安装程序 → PDF 使用手册 → DOD 归档
- **GUI 硬规范**：默认 Wifibond 左导航布局、界面质量 L1~L11 验收（含关于页赞助弹窗 + 文本排版无孤行）
- **模型可切换**：默认 glm-5.3，一句话切 kimi-k3-1 / deep-model / Claude-4.0（`default-1.2`）等
- **跨盘符 CLI 探测**：换机零配置，自动定位 WorkBuddy headless CLI
- **安全边界**：危险命令默认拦截、token 内存提取、serve 仅绑 loopback

## 📁 目录结构

```
d2w/
├── SKILL.md                  # 技能入口（双模式/派活/审核/交付/常见坑）
├── CHANGELOG.md              # 版本记录
├── scripts/
│   ├── dispatch.py           # 模式 A 派活桥（token/serve/派任务/SSE/--smoke/--auto-review）
│   ├── poll_tasks.py         # 模式 B 任务队列轮询
│   ├── init_project.py        # 项目初始化向导
│   ├── gen_checklist.py       # PRD → CHECKLIST 草稿
│   ├── sync_copies.py        # 副本同步防御
│   └── extract_jwt.py        # 备用 token 扫描
├── references/
│   ├── setup.md              # 环境/认证/serve/模型清单
│   ├── methodology.md        # 完整方法论与踩坑
│   └── troubleshooting.md    # 实证踩坑 §1~23
└── assets/
    ├── templates/            # PRD/CHECKLIST/review/task/cron/USER_MANUAL/DOD/selftest
    ├── ui_spec/              # Wifibond 布局规范 + PDF 手册样式
    └── money_code/           # 收款码（赞助用）
```

## 🚀 快速开始

### 前置条件

- Windows 10/11 + Python 3.9+
- [WorkBuddy 桌面版](https://workbuddy.tencent.com/) 运行并登录
- 一个 git 项目目录

### 初始化项目

```bash
python scripts/init_project.py D:\path\新项目 --with-templates
```

自动完成：建目录 + git init + 仓库身份 + .gitignore + inbox/tasks+results + 复制派活脚本 + 模板。

### 派第一个活

```bash
python scripts/dispatch.py "在 <cwd> 目录：写一个 hello.py，打印 'Hello from WorkBuddy'。
要求：1) python -m py_compile hello.py 通过；2) git add + commit，信息 'init hello'。
不要修改其他文件。" --timeout 120
```

### 冒烟自检（升级 WorkBuddy / 换机后必跑）

```bash
python scripts/dispatch.py --smoke --cwd D:\path\test-project
```

## 🎯 工作流

```
派活方(甲方)                干活方(乙方)
     │                          │
     │── 任务文本(四要素) ─────▶│  写代码 + selftest + commit
     │                          │
     │◀──── git log 新 commit ──│
     │                          │
     │── 审核报告(P0/P1/P2) ──▶│  按意见修改
     │                          │
     │◀──── 新 commit ──────────│
     │                          │
     └── 连续两轮 NO_P0 → 收敛 ─┘
```

## 📋 核心命令

| 命令 | 作用 |
|---|---|
| `dispatch.py "任务"` | 派活给 WorkBuddy |
| `dispatch.py --status` | 查 token/CLI/serve 状态 |
| `dispatch.py --smoke` | 一键冒烟自检 |
| `dispatch.py --auto-review` | 派活后自动生成审核草稿 |
| `dispatch.py --queue tasks.txt` | 批量派活 |
| `dispatch.py --list-runs` | 查派活历史 |
| `dispatch.py --stop-all` | 清理孤儿 serve 进程 |
| `poll_tasks.py` | 模式 B 轮询任务队列 |

## ⚠️ 红线

- 派活文本必须明确 cwd / 做什么 / 验收要求 / 禁区
- 大任务分模块派，每模块立即 commit
- 审核方只审不改代码；干活方无权改 PRD/CHECKLIST/审核基线
- token 绝不写进 commit、文档、聊天
- CLI/API 通道积分行为属观察事实，勿规模化滥用

## 📄 License

MIT

---

## ☕ 感谢赞助

如果这个工具帮到了你，可以请作者喝杯咖啡，你的支持会让这个项目持续更新：

<div align="center">
  <img src="assets/money_code/alipay.jpg" alt="支付宝收款码" width="280" />
  <img src="assets/money_code/wechatpay.jpg" alt="微信收款码" width="280" />
</div>

**支付宝 / 微信扫码均可**，感谢每一份支持 ❤️
