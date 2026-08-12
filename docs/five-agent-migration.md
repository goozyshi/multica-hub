# 五 Agent 迁移方案

版本：`2026-08-12.3`

目标：把现有 `Planner / Coordinator` 拆成独立 `Planner` 与 `Coordinator`，形成 `Coordinator + Planner + Builder + Reviewer + Inspector`。本文件描述 Multica server 迁移、权限与验证；`docs/protocol.md` 与 `skills/branch-mr-safety/SKILL.md` 是设计参考，server instructions 是运行副本。

## 1. 目标拓扑

```text
用户 / 飞书 / issue
        |
        v
Coordinator（Squad leader、唯一入口与 dispatcher）
   | planning
   v
Planner（docs-only）
   |
   v
Coordinator（exact-head approval、幂等建票）
   |----------|------------|
 Builder     Reviewer     Inspector
   \------------ handoff ---/
                |
                v
        Coordinator（验收、Final MR）
```

所有跨 Agent 状态与人工闸门归 Coordinator。Agent 之间不直接调度。

## 2. Server Agents

| Agent | Server 动作 | Instructions 源 | Version | Concurrency |
| --- | --- | --- | --- | --- |
| Coordinator | 将现 `Planner / Coordinator` 重命名或新建；保留用户入口/Bot | server instructions | `2026-08-12.3` | `1` |
| Planner | 新建 | server instructions | `2026-08-12.3` | `1` |
| Builder | 保留并同步四种 work type 契约 | server instructions | `2026-08-12.3` | `1` per repo |
| Reviewer | 保留并同步 Coordinator handoff | server instructions | `2026-08-12.3` | `1` |
| Inspector | 保留并同步 Coordinator handoff/context profile | server instructions | `2026-08-12.3` | `1` |

切换要求：

- 用户入口名称固定为 `Coordinator`。
- 飞书 Bot 只绑定 Coordinator。不要同时把旧入口与新入口暴露给用户。
- Planner 必须是独立 server Agent，不是 Coordinator alias。
- 旧 `Planner / Coordinator` instructions 下线后，不得继续 claim 新任务。
- Agent description 记录对应 `Instruction version`，完整行为必须放在 server instructions。
- 所有 Agent access 设为 workspace 所需范围；敏感配置只放 server env/MCP。

## 3. Squad roster

目标 Squad：

| Member | 类型 | Role |
| --- | --- | --- |
| Coordinator | Agent / leader | 唯一 dispatcher、用户入口、状态机与人工闸门 owner |
| Planner | Agent | triage、澄清、spec、Ticket plan、docs-only planning MR |
| Builder | Agent | `implement | diagnose | prototype | review-fix` |
| Reviewer | Agent | pinned diff 的 Standards + Spec 双轴审查 |
| Inspector | Agent | 按 `inspection_type` 执行巡检 |

Squad instructions 只保留短路由：

```md
Coordinator 是 leader 和唯一 dispatcher。
planning → Planner。
implement | diagnose | prototype | review-fix → Builder。
review → Reviewer。
inspection → Inspector。
父 requirement issue 归 Squad；planning child 归 Planner；专员完成或阻塞只 handoff 给 Coordinator。
成员不得互相派发。Coordinator 完成人工 gate、验收与 Final MR。
```

不要把 Agent 完整 instructions 复制到 Squad instructions。确认 server 注入的 Squad Operating Protocol 与 roster mention 格式可被 Coordinator 收到。

## 4. Skills

| Agent | 绑定 skills | 说明 |
| --- | --- | --- |
| Coordinator | `branch-mr-safety` | 只用于 branch/MR 控制面安全 |
| Planner | `grill-with-docs`, `to-spec`, `to-tickets`, `triage`, `branch-mr-safety` | instructions 覆盖直接用户采访、正式建票、assign、merge 等 skill 默认行为 |
| Builder | `codebase-design`, `diagnosing-bugs`, `tdd`, `prototype`, `branch-mr-safety` | `prototype` 只用于 Coordinator 明确派发的可丢弃实验 |
| Reviewer | `code-reviewer`, `tdd`, `branch-mr-safety` | 必须固定 refs，并独立执行 Standards 与 Spec 两轴 |
| Inspector | 当前 `inspection_type` 对应 skill；bootstrap 时 `writing-great-skills` | 不跨 profile 混用 |

同步时核对 skill 的 server 实际名称/ID。不存在 `prototype` skill 时，不得用相似 skill 猜测替代；先阻止 `work_type: prototype` 派发，待 skill 与 Builder instructions 就绪。

## 5. Issue ownership 与状态

- 父 requirement issue：assign Squad，由 Coordinator leader claim。
- planning child issue：Coordinator 幂等创建，assign Planner。
- formal execution child issue：Coordinator 在 exact planning head 获批后幂等创建，assign Builder。
- review：Coordinator 触发 Reviewer；Reviewer 完成后交回 Coordinator。
- inspection child issue：Coordinator assign Inspector。
- 任何 Agent 完成/阻塞：只 handoff Coordinator。

主状态沿用 Matt skills 的五个状态角色：

```text
needs-triage
needs-info
ready-for-agent
ready-for-human
wontfix
```

含义：

- `needs-triage`：新需求或 raw issue，尚未完成分诊。
- `needs-info`：等待用户、Reporter 或上游 Agent 补充信息。
- `ready-for-agent`：范围、验收标准和依赖已明确，可以派发 Agent。
- `ready-for-human`：等待人工决策、用户验收或人工 merge。
- `wontfix`：明确不处理的终态。

`ready-for-human` 必须在 comment 或 handoff packet 中记录：

```text
human_gate: planning-approval | acceptance | merge | decision
```

执行阶段只作为内部 handoff 信息，不创建额外公开状态：

```text
planning
in-progress
review
changes-requested
acceptance
done
```

标准链路：

```text
needs-triage
-> planning
-> ready-for-human (human_gate: planning-approval)
-> ready-for-agent
-> in-progress
-> review
-> ready-for-human (human_gate: acceptance | merge)
-> done
```

简单任务可从 `needs-triage` 直接进入 `ready-for-agent`，并使用 `workflow: fast-path`：跳过 Planner、Planning MR 和 planning approval，planning fields 设为 `not-required`，但仍必须提供可解析的不可变 `spec_ref`。没有 `repo:path@commit` 格式的 spec 时，必须改用 `workflow: planned`；不得使用可变 issue 正文或聊天消息替代。`needs-info` 恢复时回到原阶段；原阶段必须记录在 comment 或 packet 中。`wontfix` 不转换为 `done`。

server 自定义状态名称不完全一致时，只映射上述五个主状态；执行阶段写入 comment 或 packet，不再为每个阶段创建独立状态。

## 6. Git 权限

### Coordinator

允许：

- 读取 issue、MR、commit/ref 与 CI 状态；
- 创建/更新 issue，assign Agent，更新状态；
- 策略允许时合并已审查的内部 Builder MR；
- 用户验收后创建 Final MR。

禁止：

- 修改源码或规划文档；
- merge 未审查或 head 不匹配的 Builder MR；
- 自动 merge Final MR；
- force push/merge 或绕过保护规则。

### Planner

允许：

- 只读搜索源码/测试/文档与 git 历史；
- 创建 `agent/<parent-key>-plan`；
- 重规划创建 `agent/<parent-key>-plan-rN`；
- 只写 `docs/specs/**`、`CONTEXT.md`、`CONTEXT-MAP.md`、`docs/adr/**`；
- commit/push planning branch，创建或更新 docs-only planning MR。

禁止：

- 修改源码、测试、配置、依赖、lockfile、CI、脚本、资产或其他 docs；
- 运行项目代码、构建、测试、server 或安装依赖；
- 创建正式执行 issue、assign、merge、Final MR。

### Builder

- `implement`：只在 `agent/<issue-key>-<slug>` 工作分支修改，Builder MR 指向 `source_branch`。
- `diagnose`：不创建生产 MR；临时 instrumentation 必须清理。
- `prototype`：隔离、可丢弃、无生产 merge path；结果回到规划。
- `review-fix`：复用原 work branch 与 Builder MR，只修 assigned finding IDs。

### Reviewer / Inspector

- Reviewer 只读 pinned diff、spec 与证据，只写 review result。
- Inspector 默认只读；写权限必须由当前 profile 与人工批准共同授权。

## 7. Docs-only CI

planning MR 必须有独立 gate。最低检查：

1. diff target 是授权 `base_branch`；
2. changed paths 只匹配：

```text
docs/specs/**
CONTEXT.md
CONTEXT-MAP.md
docs/adr/**
```

3. 禁止 rename/copy 绕过路径规则；
4. 禁止 submodule、symlink 目标或 generated artifact 绕过；
5. Markdown/link/schema 校验按仓库能力执行；
6. 输出 exact planning head SHA；
7. CI 结果绑定该 exact head。

建议 job 名：`planning-docs-only`。Coordinator 请求批准前必须看到该 job 对当前 `planning_head` 成功。

如果 server 迁移时 CI 尚未提供：

- Planner 报 `docs_only_ci: unavailable`；
- Planner 仍提供完整 changed-path diff verification；
- Coordinator 向审批人明确展示缺失 gate；
- 不得把 `unavailable` 表述成 `passed`；
- 是否临时批准由人工明确决定并记录。

## 8. 不可变引用与批准

- Planning branch：`agent/<parent-key>-plan[-rN]`。
- Spec：`spec_ref=repo:path@commit`。
- Planning approval：绑定 exact `planning_head`。
- Review：绑定 exact `review_base_ref...review_head_ref`。
- `AC-ID` 与 `SLICE-ID` 发布后稳定；修订不得改义复用。

planning head 变化时：

1. Coordinator 立即把旧 approval 标为 `invalidated-by-head-change`；
2. 停止创建/派发剩余 formal issues；
3. 展示新 head 与 diff；
4. 取得新 exact-head approval；
5. 新 approval 使用新 idempotency namespace。

### Review dispatch 与自动修复

Coordinator 派发 Reviewer 时必须同时传递：

```text
spec_ref
review_base_ref
review_head_ref
acceptance_criteria
standards_sources
builder_completion_ref
test_evidence
review_round
assigned_finding_ids
```

`workflow: fast-path` 与 `workflow: planned` 使用相同的 `spec_ref` 格式。Reviewer 不接受 issue 正文、聊天消息或浮动 MR 作为 Spec 轴基准。

Reviewer 必须：

- 读取 `spec_ref` 指向的完整原始 spec；
- 只审查固定的 `review_base_ref...review_head_ref`；
- 分别执行 Standards 与 Spec 双轴审查；
- 为 findings 标记所属轴和稳定 finding ID；
- 在输入缺失或 ref/head 失效时返回 `needs-info`，不得批准。

自动修复链路：

```text
Reviewer changes-requested
  -> Coordinator 提取 blocking finding IDs
  -> Builder(work_type: review-fix)
  -> Coordinator 固定新的 review_head_ref
  -> Reviewer follow-up
```

`review-fix` 只能修复 Coordinator 指定的 finding IDs。每个执行 issue 最多一次自动修复循环；第二次仍 `changes-requested` 时进入 `ready-for-human`，记录 `human_gate: decision`。Spec 变化或产品决策不得自动修复，必须回 Planner/用户。

## 9. 幂等键

Planning child：

```text
<parent_issue_key>:planning:<planning_revision>
```

Formal child：

```text
planned:
<parent_issue_key>:<approved_plan_ref>:<SLICE-ID>

fast-path:
<parent_issue_key>:fast-path:<spec_ref>:<SLICE-ID>
```

每次 server task 重试前先查 key。匹配则复用；冲突或重复则停在 `ready-for-human`，并记录 `human_gate: decision`，不再创建一张“替代票”。

## 10. 同步顺序

顺序敏感。避免新 Coordinator 派发给尚未兼容的成员。

1. 备份五个 server Agent 与 Squad 当前 JSON 配置：name、runtime、model、instructions、description、skills、access、concurrency、env/MCP 引用。
2. 暂停旧入口的自动任务或新 issue claim；保留已有任务，不中途换 owner。
3. 创建 Planner server Agent，写入 server instructions，绑定 skills。
4. 创建或更新 Coordinator，写入 server instructions；先不开放用户流量。
5. 更新 Squad roster，设 Coordinator 为 leader，加入 Planner。
6. 同步 Squad 短 instructions。
7. 同步 Builder 对 `prototype`、Coordinator handoff 和四 work types 的支持；未完成前设置 `prototype` dispatch kill switch。
8. 核对 Reviewer/Inspector 的 handoff target 是 Coordinator，不再是旧 `Planner / Coordinator` 身份。
9. 上线 `planning-docs-only` CI。
10. 执行下方 smoke。
11. smoke 全部通过后，把飞书 Bot/Chat/issue 默认入口切到 Coordinator。
12. 禁用旧 `Planner / Coordinator` server Agent 的新 claim；确认无活动任务后再归档。不要删除历史 issue/comment 身份。

切流策略：切换完成后的新请求全部走五 Agent 流程；切换时已在途的请求默认继续旧流程和原 owner。只有人工明确决定并完成状态/ref 映射后，才迁移单个在途请求。

仓库文件更新不会自动同步 server。每次同步后执行：

```bash
multica agent get <agent-id> --output json
multica squad list
```

逐项核对：

- Agent name/runtime/model/access/concurrency；
- description 中的 version；
- instructions 内容/hash；
- bound skill IDs；
- Squad leader、roster、roles、instructions；
- Bot 只绑定 Coordinator。

## 11. Smoke tests

使用独立测试项目或无副作用 issue。不要在生产仓库制造代码变更。

### Smoke A：Squad 与入口

- 用户从 Chat/飞书只 @Coordinator。
- Coordinator 建/接管父 requirement，并 assign Squad。
- leader 收到 Squad Operating Protocol、roster 与 Squad instructions。
- Planner 不作为用户 Bot 入口。

通过标准：父票归 Squad，Coordinator 是唯一响应与分派者。

### Smoke B：Planning child 与 Question relay

- Coordinator 创建一个 planning child，重复触发两次。
- 只存在一张相同 idempotency key 的 planning child。
- Planner 发 Question packet。
- Coordinator 向用户展示文本与顺序完全相同。
- 用户回答后，Coordinator 原样回传 Planner。

通过标准：无重复票；Coordinator 不代答、不改写；Planner 不直接联系用户。

### Smoke C：Docs-only planning MR

- Planner 从测试 requirement 创建 planning branch/MR。
- MR 只改允许路径。
- `planning-docs-only` 对 exact head 成功。
- `spec_ref` 可按 `repo:path@commit` 解析。
- Planner 未创建 formal issue、未 assign、未 merge。

负例：

- 在 planning branch 加一个源码文件改动。
- CI 必须失败；Planner/Coordinator 不得请求批准。

### Smoke D：Exact-head approval

- 用户批准 head A。
- 在 planning MR 增加一个文档 commit，head 变 B。
- Coordinator 在建票前重新读取 head。

通过标准：A 的 approval 失效；B 未重新批准前不建票、不派发。

### Smoke E：AC/SLICE 与幂等建票

- spec 含至少两个 `AC-ID`，Ticket plan 含两个有依赖的 `SLICE-ID`。
- Coordinator 对相同 packet 重试创建。

通过标准：每个 `SLICE-ID` 只有一张 formal issue；下游依赖未完成时不派发；issue 保留 immutable `spec_ref` 与 approved head。

### Smoke F：四种 Builder work type

- `implement`：产生 Builder MR 与 completion packet。
- `diagnose`：只返回证据，无生产 fix/MR。
- `prototype`：隔离、可丢弃、无生产 merge path，结果回规划。
- `review-fix`：复用原 Builder MR，只含 assigned finding IDs。

通过标准：Builder 不直接触发 Reviewer；所有 handoff 回 Coordinator。

### Smoke G：Review-fix budget

- Reviewer dispatch packet 包含完整 `spec_ref`、固定 `review_base_ref...review_head_ref`、验收标准和测试证据。
- Reviewer 分别返回 Standards 与 Spec 两轴结果，并为 blocking findings 生成 finding IDs。
- Reviewer 第一次返回 `changes-requested`。
- Coordinator 设置 `review_fix_count: 1`，以 `work_type: review-fix` 派发 exact IDs。
- Builder 只修复 assigned finding IDs，完成后由 Coordinator 派发 follow-up Reviewer。
- Reviewer 第二次仍返回 `changes-requested`。

通过标准：Reviewer 能读取完整 spec 和 pinned diff；两轴结果可追溯；issue 进入 `ready-for-human` 并记录 `human_gate: decision`；不出现第二次自动 review-fix。

### Smoke H：验收与 Final MR

- Reviewer approved head 进入 `source_branch`。
- Coordinator 请求用户验收。
- 验收前尝试创建 Final MR。

通过标准：验收前 issue 保持 `ready-for-human` 且记录 `human_gate: acceptance`；验收后只创建一个 Final MR；Final MR 不自动 merge；冲突不 force。

### Smoke I：Inspector handoff

- Coordinator 派发一个只读 inspection。
- Inspector 返回 report。

通过标准：Inspector 不派发 Builder；实现建议回 Coordinator，并重新进入 planning gate。

### Smoke J：Fast-path

- Coordinator 为单切片、范围清晰且无未决产品决策的 issue 设置 `workflow: fast-path`。
- `spec_ref` 可解析为 `repo:path@commit`；planning fields 均为 `not-required`。
- 不创建 planning child、Planner task 或 Planning MR。
- Builder、Reviewer、review-fix、用户验收和 Final MR 仍按标准链路执行。
- 删除或改写不可变 spec 后，fast-path 被阻止并转为 `workflow: planned`。

通过标准：fast-path 只减少规划步骤，不减少 Spec 轴审查、review-fix 限制、用户验收或人工 merge。

## 12. 回滚

若 smoke 失败：

1. 停止新任务入口；
2. 不删除已创建 issue、MR、comment 或 Agent 历史身份；
3. 恢复备份的 Bot 绑定、Squad leader/roster 和 server instructions；
4. 将迁移期间创建但未派发的 issue 标记为 migration-paused；
5. 记录失败的 exact Agent config/version 与 smoke case；
6. 修复后从失败 smoke 重新开始，不复用旧 exact-head approval。

不要让旧、新 dispatcher 同时接收流量。不要通过手工改票绕过幂等键或审批失效规则。

## 13. 上线完成标准

- 五个 server Agent 存在且配置可审计。
- Coordinator 是 Squad leader、唯一 Bot/用户入口、唯一 dispatcher。
- Planner 使用独立身份和 docs-only Git 权限。
- Squad roster 与 skills 已同步。
- Builder 支持四种 work type，或 `prototype` 明确保持禁用。
- `planning-docs-only` CI 对 exact head 生效。
- Question relay、exact-head approval、幂等建票、handoff、review-fix budget、验收与 Final MR smoke 全部通过。
- 旧 `Planner / Coordinator` 不再 claim 新任务。
