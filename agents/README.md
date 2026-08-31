# Multica Agent Designs

基于当前工作流设计 4 个 agent。

## Agents

- [`Planner / Coordinator`](./planner-coordinator.md)：唯一 dispatcher。澄清、PRD、拆 issue、triage、派发。
- [`Builder`](./builder.md)：实现 `ready-for-agent` issue。小步开发，测试优先。
- [`Reviewer`](./reviewer.md)：用 `code-reviewer` 审查实现结果。找 bug、回归、缺测试、风险。
- [`Inspector`](./inspector.md)：通用巡检 agent。按 `inspection_type` 路由 skill；内置极简示例类型 `todo-scan`（只读扫 `TODO`/`FIXME`/`XXX`）。scope 支持 Multica project 级或单 repo。支持 self-service bootstrap：用户口述新巡检需求 → 起草 skill + 绑定到自身 + 注册类型 + 经确认后自建 autopilot（如 `context` 等类型均经此创建）。

## Final Skills

以下记录各 agent 设计中绑定的 Skills。Matt Skills 与 Workspace Skills 分开；部署时以 Multica 实际绑定为准：

- `Planner / Coordinator`: Matt `grilling`, `to-spec`, `to-tickets`, `triage`; Workspace `branch-mr-safety`
- `Builder`: Matt `codebase-design`, `diagnosing-bugs`, `resolving-merge-conflicts`, `tdd`; Workspace `branch-mr-safety`
- `Reviewer`: Matt `tdd`; Workspace `code-reviewer`, `branch-mr-safety`
- `Inspector`: `grill-with-docs`, `handoff`, `writing-great-skills`

## Dispatch Rule

只有 `Planner / Coordinator` 可以创建子 issue、分配 agent、推进跨 agent 状态。

其他 agent 不互相调度：

- `Builder` 完成后标 `ready-for-review`，并把当前 issue 交回 `Planner / Coordinator`。
- `Reviewer` 审查后无 blocking findings 则标 `review-approved`；有 blocking findings 标 `changes-requested`。两种结果都只交回 `Planner / Coordinator`，不直接推进验收或 merge。
- `Inspector` 默认只产出巡检报告/提议；`context` 类型经人类明确确认后可在重新触发时写入 approved context files；只读类型全程只读；危险动作必须人工确认。

同一 repo 的 Builder 实现默认串行。只有确认使用隔离 worktree 时才允许并行。

## Notification Rule

飞书群里用户只需要 @ `Planner / Coordinator`。`Planner / Coordinator` 派发时把原请求人、原群/线程和父请求链接作为内部 notification context 传给 `Builder`。

`Builder` 完成或阻塞后，可以在原群/线程通知原请求人一次。通知只包含实现结果、Builder MR link、build/验证结果、风险或 blocker。`Builder` 不 @ `Reviewer`，不派发其他 agent，不推进 review loop。

`Builder` 交回 `Planner / Coordinator` 是状态 handoff，不是派发。优先 assign 当前 issue 回 `Planner / Coordinator`；如果 Multica 不支持 assign，就在当前 issue 留一条 @Planner 的 ready-for-review/blocker 评论。用户不需要手动说“请 review”。

`Reviewer` 不 reassign issue。完成后留一条面向用户的 @Coordinator review summary。`Planner / Coordinator` 负责 review-fix、Builder MR merge、用户验收和 Final MR。

`Inspector` 完成后写一个 Inspection result packet，再把当前 inspection issue 交回 `Planner / Coordinator`。实现建议必须新建独立 issue，重新通过 ready-for-agent gate。

权限边界：

- 派发权：只有 `Planner / Coordinator`。
- 执行权：`Builder`。
- 完成/阻塞通知权：`Builder` 可通知原请求人/原群。
- 复审触发权：只有 `Planner / Coordinator`。

## Review Loop Budget

只有 `Planner / Coordinator` 能触发 `Reviewer`。一次 `code-reviewer` 输出就是一个 review round，里面的 P0/P1/P2 findings 不按条计数。`Builder` 可以分批修复同一轮 findings，但修完全部必修项后只交回 `Planner` 一次。复审时 `Reviewer` 只验证上一轮 findings 是否解决，以及修复是否引入明显新 P0/P1 回归；不要把修复代码当成全新实现重新全量 review。每个 issue 最多 1 次自动 review-fix cycle，第二次 `changes-requested` 后停止自动化，标 `needs-human-decision`。

## Human Gates

- PRD 确认。
- Final MR 创建授权。
- 用户验收确认。
- Final MR merge 确认。

Builder MR（`work_branch -> source_branch`）是内部集成步骤：Reviewer 通过后由 `Planner / Coordinator` 在策略允许时合并；策略不允许时进入 `ready-for-builder-mr-merge`，等待人工合并。合并并验证 reviewed head 已进入 `source_branch` 后，先获人类授权创建 Final MR；Final MR 合入目标环境后，才进入用户验收。

## Canonical State Flow

```text
needs-clarification
-> prd-draft
-> ready-for-slicing
-> needs-triage
-> ready-for-agent
-> in-progress
-> ready-for-review
-> review-approved
-> ready-for-final-mr-approval
-> ready-for-human-merge
-> ready-for-acceptance
-> done
```

Optional policy fallback:

```text
review-approved
-> ready-for-builder-mr-merge
-> ready-for-final-mr-approval
-> ready-for-human-merge
-> ready-for-acceptance
```

Review return:

```text
ready-for-review
-> changes-requested
-> ready-for-agent
```

## Branch And MR Safety

统一使用 [`branch-mr-safety`](../skills/branch-mr-safety/SKILL.md)。分支/MR 是 agent 内部控制面，不是默认用户汇报内容。用户默认只看到实现结果、MR link、验证结果、风险和需要人工决定的 blocker。

`Planner / Coordinator` 在派发前，先读取 child issue 的可见 key，再把目标、验收标准、验证与完整 Delivery Context 写入 child issue：`repo`、`base_branch`、`source_branch`、`source_branch_status`、`issue_key`、`work_branch`、`builder_mr_target`、`final_mr_target`。这是为当前无私有派发载体保留的最小分支安全上下文；公开 issue 不写 agent packet、SHA、commands、raw test output 或 routing 字段。

Builder 完成后只写变更、Builder MR、build/test 结论、风险与 `source_branch`。Planner 从 Git/MR 获取 refs、diff、changed files、检查结果和分支状态。

Planner 派发 Reviewer 时提供 public issue 与 Builder MR link。Reviewer 从 Git/MR 解析 immutable diff、测试和分支状态。

Reviewer 输出公开 Review summary：result、Builder MR、blocking findings、non-blocking follow-ups、test gaps、residual risks。每个 finding 必须有稳定 id；review refs 与 branch state 留在 Git/MR。

Inspector 输出 Inspection result packet：type、scope、result、action required、human approval、approved scope、findings、evidence、actions、follow-up refs、remaining decisions。

`work_branch` 必须使用可见 issue key：`agent/<issue_key>-<short-slug>`，例如 `agent/MIC-338-onelink-month`。不要用 project id、UUID 或内部 task id。

`repo` 可以是 Multica project name、repository name 或 remote URL。若 workspace/issue 上下文只有一个 project/repo，`Planner / Coordinator` 应直接推断 `repo`，不要询问 repo 地址。

新需求默认 `source_branch_status: create_if_missing`。这表示远端 `source_branch` 不存在是预期状态，`Builder` 应从 latest `base_branch` 创建并 push。只有用户指定既有集成/feature/hotfix 分支时，才用 `source_branch_status: must_exist`。

## Build Check

UI 变更由 `Builder` 在标 `ready-for-review` 前跑通项目 build；build 失败 = 交付未完成。交互/视觉验收在 Final MR 合入后的 test 环境进行。

测试有既有 seam 时，Builder 补焦点覆盖，Reviewer 按缺测审查；没有可行 seam 时，Planner 在 issue 记录证据与 fallback 验证，Builder 不新建测试框架，Reviewer 把 test gap 作为风险而非自动 blocking。

## Shared Communication Instruction

```md
Communication:

- Use terse simplified Chinese.
- No filler, pleasantries, hedging, repetition.
- Pattern: [thing] [action] [reason]. [next step].
- Keep code symbols, API names, errors, commands exact.
- Use normal clear Chinese for security warnings, destructive actions, and order-sensitive steps.
```

## Skill Precedence

Agent instructions and issue/MR context override loaded Skill workflows。Skill 只提供方法和模板，不扩大 Agent 权限，不跳过人工闸门，不改变 dispatcher ownership。

- Coordinator 可使用 `to-spec` / `to-tickets` / `triage` 做范围内只读源码探索；禁止 checkout、编辑、安装依赖、运行项目代码/构建/测试、自动 `ready-for-agent`、自动 `/implement`。
- Builder 把 issue 中的验证路径视为已确认；Skill 不得自行触发 review 或 Final MR。
- Reviewer 固定审查 Builder MR 解析出的 immutable commit refs；Skill 不得询问用户修哪些项、实施修复或直接触发 Builder。
- Inspector 只执行当前 `inspection_type` 明确授权的动作。

## Deployment Sync Rule

`agents/*.md` 是设计源，Multica server instructions 是运行副本。每次修改必须：

1. 同步对应 Agent instructions 到 Multica。
2. 在 Multica Agent description 记录同一 `Instruction version`。
3. 核对 Agent name、bound Skills、max concurrency、instructions version。
4. 用一个无副作用 smoke issue 验证状态转换、MR 证据读取和交接。

当前版本：Coordinator `2026-08-13.13`；Builder `2026-08-13.9`；Reviewer `2026-08-13.9`；Inspector `2026-07-27.1`。后续 repo 文件更新仍不代表 server 已自动同步。
