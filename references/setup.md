# 双 AI 协作闭环 — 环境设置与验证（setup.md）

> 首次使用本 Skill 时按此准备环境；之后大部分步骤被 dispatch.py 自动化，无需重复。

## 1. WorkBuddy 安装与 CLI 入口

### 1.1 桌面版
- 正常安装并登录 WorkBuddy（腾讯桌面 AI）
- 确认进程在运行（token 提取的前提）

### 1.2 headless CLI 入口（派活桥核心）
- 典型路径（以实际探测为准）：
  `E:\LenovoSoftstore\Install\WorkBuddy\resources\app.asar.unpacked\cli\dist\codebuddy-headless.js`
- **自动探测（v1.5.0 起，v1.5.1 跨盘符）**：dispatch.py 在默认路径不存在时按顺序尝试——
  `WB_CLI_PATH` 环境变量 → 常见安装目录 glob（Program Files* / D 盘 / 用户级 Programs）→ **跨盘符全盘扫描**（枚举 C~Z 盘 × 常见安装层级，含 LenovoSoftstore/Program Files/用户 Programs/两级目录）→ 从运行中的 WorkBuddy 进程推导；全部失败才报错提示。
  `python dispatch.py --status` 会直接显示解析到的 CLI 路径。
- 手工探测命令：
  ```powershell
  Get-ChildItem "E:\LenovoSoftstore\Install\WorkBuddy\resources\app.asar.unpacked\cli\dist" -Filter "codebuddy-headless.js"
  ```
- 版本信息在 `resources/app.asar.unpacked/cli/product.json`（如 v2.156.0）
- **注意**：`bin\codebuddy` 是坏入口（require 不存在的 dist/codebuddy），不要用它

## 2. 认证机制（为什么能连上）

| 变量 | 值 | 作用 |
|---|---|---|
| `CODEBUDDY_AUTH_TOKEN` | 从 WorkBuddy 内存提取的 Keycloak JWT | **正确的认证变量** |
| `CODEBUDDY_HOST` | `workbuddy-desktop` | 指定宿主身份 |
| `CODEBUDDY_API_KEY` | 不要用 | 会报 token-type:ApiKey 401 |

- 认证实体文件：`C:\Users\<user>\AppData\Local\CodeBuddyExtension\Data\Public\auth\workbuddy-desktop.info`（accessToken 是 $wbEncrypted 静态加密，**不需要解密**，直接用内存提取的明文 JWT）

## 3. 快速验证环境（一条命令）

```bash
python scripts/dispatch.py --status
```

期望输出：
```
token: 有效
serve: 运行中（或 未运行——派活时会自动拉起）
CLI: <解析到的 codebuddy-headless.js 路径>
默认模型: glm-5.3
```

## 4. serve 服务细节

### 4.1 启动参数（dispatch.py 内置）
```
CODEBUDDY_GATEWAY_AUTH=none \
node <CLI> --serve --port 51741 --auth none --permission-mode auto
```
- `CODEBUDDY_GATEWAY_AUTH=none`：**必须有**（CLI v2.156+ 起 `--auth none` 会被 settings/默认覆盖，
  不设这个环境变量会回落成 password 模式，派活报 401）。优先级：环境变量 > `--auth` > settings > 默认
- `--auth none`：本机绑定，关闭 HTTP 认证（靠 127.0.0.1 兜底）
- `--permission-mode auto`：**必须有**，否则 git commit 等操作卡权限确认
- 启动成功的判据：日志出现 `⚠ Authentication is DISABLED.`（不是 `Auth enabled (mode: password)`）
- **日志轮转（v1.5.0）**：serve.log 超过 5MB 自动备份为 `.old`，不会无限增长

### 4.1.1 环境代理陷阱
若本机设了 `HTTP_PROXY`/`HTTPS_PROXY`，Python `urllib` 默认会把 loopback 请求也发给代理 → 502。
dispatch.py 已对所有 127.0.0.1 请求使用空 `ProxyHandler` 直连。手工排查时也要绕开代理。

### 4.2 健康检查
```
GET http://127.0.0.1:51741/api/v1/health    （需请求头 x-codebuddy-request；auth 关闭时返回 200）
```
判据：**200 = 存活**；401 = 存活但鉴权未关（回到 4.1 检查 `CODEBUDDY_GATEWAY_AUTH`）；
502 = 被环境代理劫持（见 4.1.1）；连接被拒 = 真没起服务

### 4.3 派任务（Gateway Protocol 消息）
```
POST /api/v1/runs
{
  "id": "<uuid>", "type": "message", "version": "1.0",
  "source": {"platform": "generic", "sender": {"id": "doubao", "name": "豆包"},
             "conversation": {"id": "<uuid>", "type": "direct"}},
  "text": "<任务内容>", "timeoutMs": 300000
}
→ 202 {data: {runId}}
```

### 4.4 读结果（SSE）
```
GET /api/v1/runs/{runId}/stream
→ 事件 data 行里 content.markdown / text 字段为 agent 的文本输出
```

## 5. token 提取（两种方式）

### 5.1 自动（推荐，dispatch.py 内嵌）
派活时自动执行：扫描 daemon 进程内存 → 找合法 JWT → 缓存 `.cache/wb_token.txt`

### 5.2 手动备用（scripts/extract_jwt.py）
```powershell
# 先拿 PID
powershell "Get-CimInstance Win32_Process | ? { $_.CommandLine -match 'daemon-app-server-entry' } | select ProcessId,Name"
# 再扫描
python scripts/extract_jwt.py <PID> --out wb_tokens.txt
```

## 6. 换机器/换项目适配

通过环境变量覆盖脚本默认值（见 dispatch.py 头注释）：
```powershell
$env:WB_CLI_PATH = "<新机器的 CLI 绝对路径>"   # 不设也会自动探测
$env:WB_PORT = "51741"
$env:WB_PROJECT = "D:\新项目目录"
$env:WB_CACHE = "D:\新项目目录\.cache"          # 多端口共用 token 时指向同一缓存
```

## 7. 安全边界

- serve 只绑定 127.0.0.1，不暴露外网
- token 绝不写进 commit、文档、聊天
- `--permission-mode auto` 是必要的权限开关，但任务文本要可信
- **危险命令拦截（v1.5.0 默认启用）**：任务文本含删除/格式化/关机/注册表/盘符级删除等模式 → dispatch.py 拒绝派活（exit 2）；确属安全任务加 `--danger-allow` 放行（详见 methodology §5.21）

## 8. 模式 B（WorkBuddy → 豆包）的约定

模式 B 不需要任何额外认证：它走的是**文件信箱**，不经过 serve/API。

- 派活方把任务单写到 `<cwd>/inbox/tasks/NNN_*.md`（模板见 assets/templates/task_request.template.md）
- 豆包用 `scripts/poll_tasks.py` 轮询（需要 Python，不需要 token）
- 结果写 `<cwd>/inbox/results/NNN_*.md`，标记 `--mark NNN`
- 需要定时自动处理时，建每小时 cron（query 模板 B 见 assets/templates/cron_query.template.md）

**注意**：模式 B 的通信介质是"项目目录 + 文件"，要求派活方（WorkBuddy）对同一目录有读写权限；把约定告诉 WorkBuddy 时要说清"任务写哪、结果读哪"。

## 9. 模型选择与清单（2026-10-12 实测自本机产品配置）

### 9.1 派活用的是什么模型
- **CLI 默认模型**：`fast-model`（快速档，isDefault=True）
- **团队场景**（WorkBuddy 建 software 团队时）：团队 config（`~/.workbuddy/teams/<团队>/config.json`）里给每个 agent 指定 `model` 字段——QuickTrans 当时的团队指定为 `space-bunny`
- **D2W 默认**：`glm-5.3`（dispatch.py 的 `WB_MODEL` 环境变量，未设时 glm-5.3）

### 9.2 切换模型的三种方式（优先级从高到低）
1. `--model <id>` 参数：`python dispatch.py "任务" --model kimi-k3-1`
2. 任务文本开头 `[model=<id>]`：`python dispatch.py "[model=kimi-k3-1] 写一个工具..."`（脚本自动剥离标记）
3. 环境变量 `WB_MODEL=<id>`：改 D2W 全局默认
> 原理：POST /api/v1/runs 的 body 支持 `model` 字段（源码：`requestOptions.model || options.model || currentModelId || "default"`，请求指定优先）。

### 9.3 模型清单（id / 名称 / 特点，实测自 acc-product-config-v3.json）

> **credits 倍率说明**：v2026-10 WorkBuddy 更新后，配置文件 `models[].credits_multiplier` 字段已为空，
> 不再从服务端配置暴露倍率。下表"历史 credits"列为 2026-10-12 审计时实测值，仅供档位参考；
> 当前实际倍率以 WorkBuddy 桌面显示为准。CLI/API 通道与桌面积分分离属观察事实（§9.4）。

| 模型 id | 名称 | 历史 credits | 特点 |
|---|---|---|---|
| `fast-model` | 快速 | x0.21 | 官方默认档，简单任务快答 |
| `balanced-model` | 均衡 | x0.65 | 日常任务 |
| `deep-model` | 极致 | x1.20 | 深度与准确性优先，复杂分析 |
| `glm-5.3` | GLM-5.3 | x0.79 | **D2W 默认旗舰**：复杂软件工程/长程 Agent，1M 上下文 |
| `glm-5.3-flash` | GLM-5.3-Flash | x0.06 | 多模态视觉 |
| `glm-5.2` | GLM-5.2 | x0.79 | 1M 上下文长程 |
| `glm-4.6` | GLM-4.6 | — | GLM 4.6 通用档（2026-10 新增） |
| `kimi-k3-1` | Kimi-K3 | x1.62 | 最强长程自主/前端，1M（最贵档） |
| `kimi-k2.8-preview` | Kimi-K2.8 | x0.77 | 长程自主 |
| `hy4-preview` | Hy4 preview | x0.29 | 腾讯混元4 思考，960K |
| `hy3` / `hy3-x` | Hy3 | x0.00/x0.05 | 混元思考 |
| `hunyuan-2.0-instruct` | Hunyuan-2.0 | — | 腾讯混元 2.0 指令模型（2026-10 新增） |
| `step-5-preview` | Step-5 | x0.00 | 阶跃旗舰基模，1M（免费档） |
| `deepseek-v4-pro` | DS-V4-Pro | x0.51 | DeepSeek 旗舰，1M |
| `deepseek-v4.1-flash` | DS-V4.1 | x0.11 | 1M 多模态 |
| `deepseek-v4-flash` | DS-V4-Flash | — | DeepSeek V4 轻量快速档（2026-10 新增） |
| `minimax-m3` | MiniMax-M3 | x0.25 | 代码/智能体 |
| `space-bunny` | Space-Bunny | x0.08 | 速度+编码强、匿名模型，1M/128K |
| `default-1.2` | Claude-4.0-Sonnet | — | Anthropic Claude 4.0（2026-10 新增，复杂推理） |
| `default-1.1` | Claude-3.7-Sonnet | — | Anthropic Claude 3.7 |
| `wb-lite` | wb-lite | — | WorkBuddy 轻量档（2026-10 新增，快速任务） |

> 完整模型列表（含 kimi-k2.7/k2.6/k2.5、minimax-m2.5/m2.7、glm-5v-turbo、glm-4.6v、
> hunyuan-3b/7b-dense、custom-local:* 本地模型等）直接读配置文件：
> `~/.workbuddy/cache/acc-product-config-v3.json` 的 `models` 数组。WorkBuddy 升级后以配置为准。

### 9.4 注意
- `credits` 倍率是**服务端积分计量**（x0.08~x1.62），与桌面 UI 显示的积分余额分离；CLI 通道暂不扣桌面积分属**观察事实、非官方承诺**，别规模化滥用（methodology §5.15）
- 模型清单会随 WorkBuddy 版本更新：配置源 `~/.workbuddy/cache/acc-product-config-v3.json`（`models` 数组）
- 换模型后最小冒烟：派一个"建文件+commit"任务，确认正常收敛
- **模型生效的验证方式（2026-10-12 实测）**：CLI 派活（POST /api/v1/runs）**不写本地 session 记录**——
  `workbuddy.db` 的 `sessions` 表只记桌面会话/定时自动化（model 列存在，但 CLI run 无对应行），
  run 详情接口只有 `{runId, active}`，SSE 事件无 model 字段。因此**无法从本地日志反查"实际用了哪个模型"**；
  模型生效依据 = ① CLI 源码 `requestOptions.model || options.model || currentModelId || "default"`（请求指定优先）
  ② body 带 model 时服务端 202 接受且任务正常执行（3 次实测：glm-5.3 / kimi-k3-1 / deepseek-v4-pro 全跑通）。
  派活时 dispatch.py 会打印 `model=<id>`（那是"请求指定的模型"），需要强证据时直接看 WorkBuddy 桌面会话。
