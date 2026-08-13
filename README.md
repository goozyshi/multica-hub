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

## 不同任务类型链路

### 模糊需求

`人类输入 -> Planner 有限澄清 -> PRD 草案 -> 人工确认 -> to-issues 拆解 -> triage -> Multica assign`

- 适用 Matt Skills：`grill-with-docs`、`grilling`、`domain-modeling`、`to-spec`、`to-tickets`、`triage`。
- 关键限制：最多 1-2 轮澄清；未确认前不进入实现。
- 产出：PRD、小 issue、验收标准、依赖关系、`ready-for-agent` / `needs-info` 状态。

### 明确 PRD 拆解

`PRD -> Planner 拆 vertical slice -> 人工确认 issue 粒度 -> Multica 创建 issue -> Builder 逐个实现`

- 适用 Matt Skills：`to-spec`、`to-tickets`。
- 关键限制：每个 issue 必须独立可验证，避免按前端/后端/数据库做横切拆分。
- 产出：可 AFK 执行的小 issue。

### 小功能实现

`ready-for-agent issue -> Builder 执行 -> 测试 -> Reviewer 审查 -> 人工验收/合并`

- 适用 Matt Skills：`tdd`、`codebase-design`。
- 关键限制：Builder 不做长澄清；缺信息就回写 blocker。
- 产出：代码变更、测试结果、风险说明。

### Bug 修复

`bug issue -> Builder 复现 -> diagnosing-bugs 定位 -> 最小修复 -> 回归测试 -> Reviewer 审查`

- 适用 Matt Skills：`diagnosing-bugs`、`tdd`。
- 关键限制：没有复现步骤先进入 `needs-info`，不要直接猜修。
- 产出：复现结论、根因、修复、回归测试。

### 代码审查

`PR/diff -> Planner 派发 Reviewer -> Reviewer 输出结构化结果 -> Planner 决定修复/验收/合并`

- 适用 Matt Skills：`tdd`。
- 关键限制：优先找 bug、回归、缺测试；架构建议只在影响较大时提出。
- 产出：审查意见、必须修复项、可后续处理项。

### 周期巡检

`Autopilot -> create_issue(inspection_type) -> Inspector 执行 -> 回写报告 -> 人工处理异常`

- 执行者：`Inspector`，由 autopilot/Planner 指定 `inspection_type` 路由 skill。内置极简示例类型 `todo-scan`（只读）；其他类型（如 `context` 上下文沉淀、`branch-health` 分支健康）经 Self-Service Bootstrap 创建 skill 后注册。
- scope 支持 Multica project 级（覆盖内含全部 repo）或单 repo。
- 关键限制：Autopilot 失败不自动 retry，重要巡检要设计成功信号；危险动作必须人工确认。
- 产出：巡检报告，或生成后续 issue。

### Context 持续补充

`完成 issue/PR -> Inspector(inspection_type: context) 汇总 -> 提议 CONTEXT.md/ADR/Skill diff -> 人工确认 -> 写入 repo`

- 执行者：`Inspector` 的 `context` 类型。
- 适用 Matt Skills：`grill-with-docs`、`handoff`、`writing-great-skills`。
- 关键限制：只建议更新 context，人类确认后才写入长期文档。
- 产出：领域词汇、架构决策、可复用工作流。

## 完整自动派发工作流

目标：`Planner` 澄清和拆解后，自动把可执行 issue 派发给其他 agent；人类只确认关键闸门。

### Agent 设计

#### Planner / Coordinator

- 职责：需求澄清、PRD、issue 拆解、triage、派发。
- 推荐模型：高推理模型；优先 `Claude Code` 或 `Cursor Agent` 强模型。
- 已应用 Matt Skills：`domain-modeling`、`grill-with-docs`、`grilling`、`to-spec`、`to-tickets`、`triage`。
- 并发：`1`。
- 权限：唯一 dispatcher。只有它可以创建子 issue、分配 agent、推进状态。
- 规则：最多 2 轮澄清；每轮最多 5 个问题；PRD 和 issue 拆解必须人工确认后再派发。

#### Builder

- 职责：实现 `ready-for-agent` issue。
- 推荐模型：中高模型；优先 `Claude Code`、`Codex` 或 `Cursor Agent`。
- 已应用 Matt Skills：`codebase-design`、`diagnosing-bugs`、`implement`、`tdd`。
- 并发：同一 repo `1`。
- 权限：只能实现、测试、回写结果。不能派发其他 agent。
- 规则：不长聊；缺信息就标 blocker，交回 Planner。

#### Reviewer

- 职责：审查 Builder 输出。
- 推荐模型：高推理模型；review 比实现更需要判断力。
- 已应用 Matt Skills：`tdd`。
- 并发：`1`。
- 权限：只能评论风险和结论。不能循环 @Builder。
- 规则：只查 bug、回归、缺测试、架构风险。

#### Inspector

- 职责：通用巡检。按 `inspection_type` 路由 skill 执行不同巡检任务；支持 Self-Service Bootstrap 自建新巡检类型。
- 推荐模型：低中模型即可（bootstrap 起草 skill 时偏中高）。
- 已应用 Matt Skills：`grill-with-docs`、`handoff`、`writing-great-skills`。内置示例类型 `todo-scan` 无外部 skill 依赖。
- scope：支持 Multica project 级（覆盖内含全部 repo）或单 repo。
- 并发：`1`。
- 权限：默认只产出报告/提议。`context` 经人类确认后可写长期文档；只读类型全程只读；危险动作必须人工确认。
- 规则：一次 run 只跑一个 `inspection_type`；未知类型标 `needs-info`；不收集一次性实现细节。

### Planner 自动派发机制

`Planner` 完成澄清和拆解后，用 Multica CLI/API/UI 创建并分配子 issue。

推荐派发方式：

1. `Planner` 创建 parent PRD issue。
2. 人类确认 PRD。
3. `Planner` 拆 vertical slice 子 issue。
4. 人类确认 issue 粒度、依赖、验收标准。
5. `Planner` 按依赖顺序创建子 issue。
6. `Planner` 补齐 implementation packet，通过 ready-for-agent gate 后再把无阻塞 issue assign 给 `Builder`。
7. `Builder` 完成后回写 Builder completion packet，并把状态改为 `ready-for-review`。
8. `Planner` 验证 packet 后，用固定 commit refs 派发 `Reviewer`。
9. `Reviewer` 输出 Review result packet；通过后标 `review-approved` 并交回 `Planner`。
10. `Planner` 合并 Builder MR（策略不允许时等待人工），验证 reviewed head 已进入 `source_branch`。
11. 进入 `ready-for-acceptance`，人类验收实现结果。
12. 验收通过后，`Planner` 创建 Final MR 并标 `ready-for-human-merge`。
13. 人类 merge Final MR；验证后标 `done`。
14. `Inspector`（`context` 类型）周期汇总可沉淀内容，并以 Inspection result packet 交回 `Planner`。

### 状态机

```text
needs-clarification
-> prd-draft
-> ready-for-slicing
-> needs-triage
-> ready-for-agent
-> in-progress
-> ready-for-review
-> review-approved
-> ready-for-acceptance
-> ready-for-human-merge
-> done
```

回流：

```text
in-progress -> blocked-needs-info -> needs-clarification
ready-for-review -> changes-requested -> ready-for-agent
review-approved -> ready-for-builder-mr-merge -> ready-for-acceptance  # 仅策略禁止自动合并 Builder MR 时
```

### 人工闸门

保留 4 个必须人工确认点：

- PRD 确认：目标、范围、验收标准无歧义。
- issue 拆解确认：粒度、依赖、AFK/HITL 标记正确。
- 用户验收确认：预览/行为是否满足需求。
- Final MR merge 确认：代码是否进入目标分支。

其他步骤可由 `Planner` 自动推进。

### 防失控规则

- 只有 `Planner` 能派发。`Builder`、`Reviewer`、`Inspector` 不能互相调度。
- 禁止 agent 间循环 @mention。
- 最多 1 轮自动 review-fix；第二轮仍失败就交给人类。
- 执行 agent 最多问 1 个 blocker；继续缺信息就回 `needs-info`。
- Autopilot 默认 `create_issue`，不直接 run-only 执行重要任务。
- 所有 agent instructions 使用短版 caveman：中文、短句、无废话、保留技术名词。
- 分支/MR 操作统一使用 `branch-mr-safety`：`base_branch -> source_branch -> work_branch`；Builder 只创建 `work_branch -> source_branch` 的 MR，最终 `source_branch -> test/main` MR 由 Planner 或人类确认后处理。
- Agent instructions 和 handoff packet 高于通用 Skill 工作流。Skill 不得扩大权限、跳过人工闸门、自动派发其他 Agent，或改变状态机。
- Planner 可只读探索相关源码和测试，用于确认当前行为、模块边界、依赖、已有实现与 test seams；禁止 checkout、编辑、安装依赖、运行项目代码/构建/测试。
- `review_fix_count`、`previous_review_ref`、review commit refs 必须持久化到 issue；不能只保存在单次会话。

## 建议落地配置

- 第一阶段建立 4 个 agent：`Planner`、`Builder`、`Reviewer`、`Inspector`。
- 每个 issue 控制在 0.5-2 天内可完成。
- Backlog 只停车，不触发 agent；进入 Todo 后再分配。
- `Planner` 并发固定为 1，避免多个规划流互相覆盖。
- `Builder` 同一 repo 并发固定为 1；只有隔离 worktree 且 MR 目标无交叉时才提高。
- Autopilot 默认使用 `create_issue` 模式，让结果留在 board 上。
- 重要 Autopilot 自己设计成功信号，因为失败不会自动 retry。
- 第三方 Skills 先审计再导入，避免指令投毒或 secret 泄露。

### Agent Instructions 同步

`agents/*.md` 是设计源，Multica server instructions 是运行副本。repo 文件修改后必须手工同步，并在 Multica Agent description 记录相同 `Instruction version`。同步后核对 Agent name、bound Skills、max concurrency、version，再用无副作用 issue 验证 packet 与状态转换。当前版本：Coordinator `2026-07-27.2`；Builder / Reviewer / Inspector `2026-07-27.1`。Matt Skills 已按 2026-07-28 CLI 查询结果同步到草稿；业务自定义、项目专属和第三方 Skills 不跟随记录。

## 最小试点

先跑完整但低并发的四条线：

- `Planner`：从模糊需求生成 PRD 和小 issue。
- `Builder`：实现 `ready-for-agent` issue。
- `Reviewer`：审查 `ready-for-review` issue。
- `Inspector`：`context` 类型每周生成 context-update issue；其他巡检类型经 bootstrap 自建。

判断标准：是否减少手工分发、追踪、复制 prompt、重复审查成本。如果只是把聊天窗口搬到看板，收益不足。
