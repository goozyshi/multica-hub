# Multica 与工作流调研

multica: https://github.com/multica-ai/multica

## 简要定位

Multica 是开源的 managed agents 平台。它不是新的代码模型，而是把 Claude Code、Codex、CodeBuddy、Copilot CLI、Cursor Agent、Gemini、Grok Build CLI、Kimi、OpenCode、OpenClaw、Qwen Code 等本地 CLI agent 接到同一个任务协作层里。

核心形态：`issue board + agent daemon + agent runtime`。

- Multica server 负责工作区、issue、任务队列、评论、状态、WebSocket 进度。
- 本地 daemon 负责轮询任务、启动本机 agent CLI、回写执行结果。
- agent 实际在用户机器上跑。API key、代码目录、工具链不放到 Multica server。

## 关键能力

- **Assign issue**：把 issue 分给 agent，agent 成为正式 assignee，能读描述和评论，能改状态、发评论、交付代码。
- **@mention agent**：在 issue 评论里临时拉 agent 看一眼，不改变 assignee。
- **Chat**：独立对话，不绑定 issue，适合提问、草拟 issue。
- **Autopilot**：用 cron 定时或手工触发 agent。适合周期巡检、报告、清理任务；Webhook/API trigger 虽已进入数据模型，但尚无公开 server endpoint。
- **Skills**：把团队经验沉淀成 `SKILL.md` 知识包，按 agent 注入。
- **Squads**：把多个 agent 和人组成小队，由 leader agent 做任务路由。
- **Git 集成**：关联 PR/MR 后显示 CI 与 mergeability；自托管部署还可连接 Forgejo、Gitea、GitLab。

## 最新功能（截至 2026-07-28）

最新稳定版是 [`v0.4.12`](https://github.com/multica-ai/multica/releases/tag/v0.4.12)，发布于 2026-07-27。

- **PR 状态进入 issue**：GitHub PR 卡片显示 CI 成功/失败/运行中及 ready、conflict、blocked、behind 等 mergeability，减少在 Multica 与 GitHub 间切换。
- **跨 runtime 复制 agent**：`multica agent copy <source-agent-id> --runtime-id <target-runtime-id> --model <model>` 复制 instructions、skills、并发和权限。`custom_env`、`mcp_config`、`runtime_config` 不自动复制，避免 secret 和机器本地配置泄漏。[命令契约](https://github.com/multica-ai/multica/commit/3d4c5c7da2eb11b2238061a3bdc15639e8488275)
- **飞书/Lark 多媒体输入**：入站图片和视频进入 chat attachments，agent 可直接处理截图、照片和视频。
- **交互改进**：图片附件支持平移/缩放；项目选择器支持搜索；名字含空格的 @mention 可正常检索。
- **自托管 Git provider**：`v0.4.10` 起支持 Forgejo、Gitea、GitLab 的 PR/MR、CI、Webhook 和 issue 自动关联。默认关闭，需配置 `MULTICA_VCS_INTEGRATION_ENABLED`、`MULTICA_VCS_SECRET_KEY`、只读 token 与 Webhook。[实现说明](https://github.com/multica-ai/multica/commit/581d9527ba13cb77b61d78146a2ae63ddd26b25d)
- **Agent 运行能力**：`v0.4.11` 加入 Claude Opus 5；`v0.4.7` 加入 Qwen Code runtime；每个 agent 可独立启停 runtime skills。

`main` 当前还包含 Usage 错误/失败分析、统一 issue/chat/comment 草稿与附件生命周期，但不属于 `v0.4.12`，生产环境不按稳定功能依赖。完整证据、使用方式和限制见 [`docs/research/multica-latest-features-2026-07-28.md`](docs/research/multica-latest-features-2026-07-28.md)。

## 适配工作流

推荐用 **Issue-first 工作流**。

本仓库的五 Agent 运行协议以 [`docs/protocol.md`](docs/protocol.md) 和 [`skills/branch-mr-safety/SKILL.md`](skills/branch-mr-safety/SKILL.md) 为准；README 只提供概览，server instructions 才是运行副本。

1. 人类创建小而明确的 issue：背景、目标、验收标准、约束、测试命令。
2. 按任务类型分配给专用 agent：实现、测试、审查、文档、巡检。
3. agent 在本地 runtime 执行，进度和阻塞回写到 issue。
4. 人类只做验收、合并、拆分新问题。
5. 高频重复任务沉淀成 Skills；周期任务迁移到 Autopilot。

## 适合的任务

- 小功能实现：边界清楚、可测试、能单独 review。
- Bug 修复：有复现步骤、错误日志、期望行为。
- 代码审查：PR diff、风险点、缺测试、潜在回归。
- 测试补齐：针对某个模块或 issue 的单元/集成测试。
- PRD 拆解：明确 PRD 按验收标准拆成可独立交付的小 issue。
- 周期巡检：依赖升级、CI 失败归因、lint/test 报告、过期 TODO 清理。
- 工作总结：按 issue、PR、commit 自动生成日报/周报。

## 不太适合

- 需求还没成形的大型探索。
- 一次性跨很多系统的大重构。
- 高权限生产操作。
- 需要强浏览器自动化、复杂 GUI 操作的任务。
- 没有验收标准的“帮我优化一下”。

## 五 Agent 工作流

五个角色严格分权：

- `Coordinator`：Squad leader、飞书唯一入口、唯一 dispatcher。建票、派发、校验 handoff、推进跨 Agent 状态、触发人工闸门。
- `Planner`：澄清需求、生成 spec、拆 vertical-slice tickets。可只读探索代码；只可写规划文档并创建 docs-only planning MR；不能派发、实现或推进 delivery。
- `Builder`：执行 Coordinator 声明的 `work_type: implement | diagnose | prototype | review-fix`。
- `Reviewer`：对固定 refs 做 Standards + Spec 双轴审查。不实现，不直接触发 Builder。
- `Inspector`：管理 Autopilot、执行 `inspection_type` 巡检、维护 context。默认报告/提议；副作用受 profile 与人工批准约束。

所有专员的完成、阻塞、证据和审查结果都交回 `Coordinator`。Agent 之间不直接派发，不形成 @mention 循环。

### 规划链路

复杂任务：

`飞书/issue -> Coordinator -> Planner -> Question relay（可选）-> spec/ticket plan -> docs-only Planning MR -> exact-head approval -> Builder`

简单任务：

`飞书/issue -> Coordinator -> ready-for-agent -> Builder`

- 简单任务使用 `workflow: fast-path`，但仍必须提供不可变 `spec_ref=repo:path@commit`；没有不可变 spec 时进入 planned。
- Planner 使用 decision frontier，不设固定澄清轮数；只处理当前阻塞 spec/ticket 的产品决策。
- 每条验收标准和子票必须追溯到原文档或明确确认的决策。
- Planner 可读源码、测试和文档；不得 checkout 业务分支、修改生产代码、安装依赖、运行项目代码/构建/测试。
- Planner 的唯一写权限是规划文档与 docs-only planning MR。该 MR 不得混入源码、配置或生成物。
- Planner 输出 planning handoff 后交回 Coordinator。Planner 不 assign Builder/Reviewer/Inspector，不设置 delivery 状态。

### 交付链路

`ready-for-agent -> Builder -> Coordinator -> Reviewer -> ready-for-human(acceptance) -> 用户验收 -> Final MR 人工 merge -> done`

- `implement`：按确认 spec 和 test seams 实现。
- `diagnose`：复现、定位、返回证据；不修生产代码。
- `prototype`：用可丢弃原型回答已声明的设计问题；结果是证据，不直接成为生产实现。
- `review-fix`：只修 Coordinator 指定的 blocking finding IDs；最多 1 次自动 cycle。
- Reviewer 固定 `review_base_ref...review_head_ref`，分开输出 `standards_findings` 与 `spec_findings`。两轴都无 blocking finding 才批准。
- Inspector 由 Autopilot 或 Coordinator 触发。每次只执行一个已注册 `inspection_type`；context 维护先提议，人工批准后才写长期资料。

### 状态机

Matt 主状态：

```text
needs-triage
needs-info
ready-for-agent
ready-for-human
wontfix
```

`ready-for-human` 使用 `human_gate: planning-approval | acceptance | merge | decision` 区分人工原因。内部阶段写入 handoff packet，不创建新公开状态：

```text
planning
in-progress
review
changes-requested
acceptance
done
```

回流：

```text
任何阶段 -> needs-info -> 原阶段
review -> changes-requested -> ready-for-agent(review-fix)
diagnose|prototype -> planning
Inspector complete|blocked -> Coordinator
```

### 人工闸门

- 复杂任务：exact planning head 批准。
- 所有实现：用户验收。
- 所有 Final MR：人工 merge。
- 冲突、Spec 歧义或自动 review-fix 预算耗尽：`human_gate: decision`。

Autopilot 创建/修改、context 写入及危险动作另需动作级人工批准。

### 技能映射

- `Coordinator`：`triage`、`branch-mr-safety`；只用于 intake、路由和控制面。
- `Planner`：`batch-grill-me`、`to-spec`、`to-tickets`、`branch-mr-safety`；后者仅用于 docs-only planning MR。
- `Builder`：`codebase-design`、`diagnosing-bugs`、`prototype`、`tdd`、`branch-mr-safety`。
- `Reviewer`：`code-reviewer`（Standards 轴）、`tdd`、`branch-mr-safety`；Spec 轴必须独立读取完整 `spec_ref`。
- `Inspector`：`inspection-autopilot-manager`、`writing-great-skills`；其他 skill 仅按当前 `inspection_type` 加载。

Agent instructions、当前 handoff packet 和人工闸门高于 Skill。Skill 不得扩大权限、改变状态机或取得派发权。

## 建议落地配置

- 建立 5 个 agent：`Coordinator`、`Planner`、`Builder`、`Reviewer`、`Inspector`。
- Coordinator 是 Squad leader；五个 Agent 都是 Squad members。
- 飞书 Bot 只绑定 Coordinator。飞书不直接入口 Planner 或执行 Agent。
- Coordinator、Planner、Reviewer、Inspector 并发固定 `1`；Builder 同一 repo 默认 `1`。
- Backlog 只停车；进入 Todo 且通过 ready-for-agent gate 后才派发。
- Autopilot 默认 `create_issue`；重要巡检定义成功信号。

### Agent Instructions 同步

`docs/protocol.md` 与 `skills/branch-mr-safety/SKILL.md` 是设计参考；Multica server instructions 是运行副本。共享协议不会自动注入任何 runtime。每个 Agent 的 server instructions 必须显式包含或引用 runtime 可读取的完整协议；仅在 repo 中更新文档无效。

统一 Instruction version：`2026-08-12.3`。同步后核对五个 Agent 的 name、Squad role、bound Skills、max concurrency、instructions version，并用无副作用 issue 验证 planned/fast-path 分流、全部 handoff 回 Coordinator、飞书入口和人工闸门。当前 repo 更新不代表 server 已同步。

## 最小试点

- `Coordinator`：接收飞书请求、唯一派发、收敛所有 handoff。
- `Planner`：生成 spec、tickets 和 docs-only planning MR。
- `Builder`：分别验证 `implement`、`diagnose`、`prototype`、`review-fix`。
- `Reviewer`：验证 Standards + Spec 双轴结果。
- `Inspector`：验证 Autopilot 与 context maintenance。

判断标准：减少手工分发、追踪、复制 prompt 和重复审查成本。
