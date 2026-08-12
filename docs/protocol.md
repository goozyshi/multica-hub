# Five-Agent Delivery Protocol

版本：`2026-08-12.3`

本文件是五 Agent 协作的设计参考，不是运行时共享 prompt。每个 Agent 的 instructions 必须自包含职责、权限、gate、packet 和失败处理，不得依赖 Agent 在运行时读取本文件。

## 1. 角色与所有权

| Agent       | 核心职责                                                       | 写权限                                    | 调度权限 |
| ----------- | -------------------------------------------------------------- | ----------------------------------------- | -------- |
| Coordinator | Squad leader、唯一用户入口、dispatcher、状态机与人工闸门 owner | issue、状态、分派、允许的 MR/merge 控制面 | 唯一拥有 |
| Planner     | 澄清、spec、切票方案、raw issue triage、只读代码探索           | 仅规划文档与 docs-only MR                 | 无       |
| Builder     | `implement`、`diagnose`、`prototype`、`review-fix`             | 工作分支、Builder MR；按模式受限          | 无       |
| Reviewer    | Standards + Spec 双轴审查                                      | 审查评论/结果                             | 无       |
| Inspector   | 定时或按需巡检                                                 | 由 inspection profile 与人工批准限定      | 无       |

Coordinator 是 Squad leader。父 requirement issue 归 Coordinator 所在 Squad；planning child issue 归 Planner；执行、审查、巡检 child issue 分别归对应 Agent。其他 Agent 完成或阻塞后只 handoff 给 Coordinator，不互相触发。

## 2. 不变量

1. Coordinator 是唯一 dispatcher、唯一用户入口、唯一跨 Agent 状态机 owner。
2. 只有 Coordinator 可以创建正式执行 child issues、assign/reassign Agent、触发 Reviewer、消费 review-fix 预算、请求用户验收、创建 Final MR。
3. Planner 不创建正式执行票，不 assign，不 merge。Planner 只更新当前 planning child issue，并创建或更新一个 docs-only planning MR。
4. Planner 可只读探索源码、测试、历史与现有文档；不得编辑源码、执行项目代码、安装依赖或运行构建/测试。
5. Planner 仅可按需写 `docs/specs/**`、`CONTEXT.md`、`CONTEXT-MAP.md`、`docs/adr/**`。
6. Planner 分支固定为 `agent/<parent-key>-plan`；重规划使用 `agent/<parent-key>-plan-rN`。MR 只能包含允许的规划文档。
7. 用户交互只经过 Coordinator。Planner 发出 Question packet；Coordinator 原样中继问题，并把用户回答原样回传 Planner。
8. 规划批准绑定 exact planning head commit。planning MR head 改变后，旧批准立即失效，必须重新批准。
9. 可执行 spec 使用不可变引用：`spec_ref=repo:path@commit`。不得用浮动分支、MR 最新版本或 issue 正文代替。
10. `AC-ID` 与 `SLICE-ID` 一经发布即稳定。修订可新增或废弃 ID，不得把旧 ID 改义后复用。
11. Coordinator 根据批准的 Ticket plan packet 幂等创建正式 child issues。重试不得重复建票。
12. 每个 repo 的 Builder 工作默认串行，除非明确保证隔离 worktree。

## 3. 规划流程

```text
用户 / raw issue
  -> Coordinator 建立或接管父 requirement issue
  -> Coordinator 幂等建立 planning child issue，assign Planner
  -> Planner: grill-with-docs -> to-spec -> to-tickets
  -> Question packet（如需）-> Coordinator 原样中继 -> 用户回答原样返回
  -> Planner docs-only planning MR
  -> Planning result + Ticket plan packet
  -> Coordinator 展示并请求人工批准 exact planning head
  -> Coordinator 合并 docs-only planning MR，并验证 approved head 可从 source branch 到达
  -> 批准有效时，Coordinator 幂等创建正式 child issues并派发
```

`raw issue triage` 也由 Planner 完成。若需要可执行证据才能安全规划，Planner 在结果中提议一个 `work_type: diagnose` slice；仍由 Coordinator 创建和派发。

## 4. Question packet

Planner 不直接询问用户。需要产品决策时，在 planning issue 写：

```md
packet_type: question
packet_version: 2026-08-12.3
parent_issue_key:
planning_issue_key:
planning_head:
question_round:
current_understanding:
assumptions:
questions:

- question_id:
  question_text:
  recommended_answer:
  impact:
  blocking_decisions:
  reply_instruction:
```

规则：

- 使用无固定轮数上限的 decision frontier。每轮只提交当前 frontier 上会阻塞 spec/ticket 的产品决策，并尽量分组。
- 问题必须是无法从 issue、文档、代码或历史发现的产品决策；可发现事实由 Planner 自己查证。
- Coordinator 原样中继 `current_understanding`、`assumptions`、`questions`、`reply_instruction`，不得改写语义、代答或合并问题。
- Coordinator 将用户回答连同 `question_id` 原样写回 planning issue，再交回 Planner。
- 用户回答不完整时，Planner 更新 frontier 并决定是否继续提问；Coordinator 不自行补齐。

## 5. Planning result

Planner 完成规划后输出：

```md
packet_type: planning-result
packet_version: 2026-08-12.3
parent_issue_key:
planning_issue_key:
planning_mr_url:
planning_base_ref:
source_branch:
planning_head:
planning_branch:
spec_ref:
spec_status: ready | needs-info | rejected
source_refs:
assumptions:
unresolved_decisions:
acceptance_criteria:
test_seams:
architecture_decisions:
context_updates:
docs_changed:
docs_only_verified:
risks:
```

要求：

- `planning_head` 是 docs-only MR 的 exact commit SHA。
- planning MR 必须以 `source_branch` 为 target；Coordinator 合并后，`planning_head` 必须仍可从 `source_branch` 到达。
- `spec_ref` 必须解析到该 commit 或其中可达的不可变 commit。
- `acceptance_criteria` 使用稳定 `AC-ID`，例如 `AC-001`。
- `docs_only_verified: true` 前必须确认 diff 只含允许路径。
- 有 blocking `unresolved_decisions` 时使用 `spec_status: needs-info`，不得给出可派发状态。

## 6. Ticket plan packet

Planner 只产出切票计划，不创建正式执行票：

```md
packet_type: ticket-plan
packet_version: 2026-08-12.3
parent_issue_key:
planning_issue_key:
planning_head:
spec_ref:
slices:

- slice_id:
  proposed_title:
  work_type: implement | diagnose | prototype
  workflow: planned | fast-path
  goal:
  scope:
  out_of_scope:
  acceptance_criteria_ids:
  test_seams:
  test_verification_path:
  dependencies:
  repo:
  branch_plan:
  preview_required:
  evidence_completion_criteria:
  prototype_question:
  disposal_rule:
  dependency_graph:
  creation_idempotency_key:
```

规则：

- `SLICE-ID` 稳定，例如 `SLICE-001`。
- 每个 slice 必须映射至少一个 `AC-ID`，诊断/原型票可映射其所解锁的 `AC-ID`。
- `workflow: fast-path` 仅用于单切片、范围清晰、无未决产品决策的简单任务；它跳过 Planner、Planning MR 和 planning approval，但仍必须提供可解析的不可变 `spec_ref`。
- `workflow: planned` 使用 Planning MR、exact-head approval 和 `approved_plan_ref`。
- `fast-path` 不得把可变 issue 正文或聊天消息当作 `spec_ref`。没有 `repo:path@commit` 格式的不可变 spec 时，必须改用 `workflow: planned`。
- Ticket plan 的核心字段是 `workflow`、`spec_ref`、目标/范围、`AC-ID`、依赖、仓库和验证路径；`preview_required`、`prototype_question`、`disposal_rule` 只在对应场景出现。
- `creation_idempotency_key` 至少绑定 `parent_issue_key + planning_head`。
- `review-fix` 不在初始 Ticket plan 中创建；它由 Coordinator 根据 Reviewer findings 在原执行 issue 上派发。
- Planner 不应用 `ready-for-agent`，不 assign，不调用 Builder。

## 7. 规划批准

Coordinator 请求批准时必须展示：

- planning MR URL；
- planning MR target `source_branch`；
- exact `planning_head`；
- `spec_ref`；
- assumptions 与 unresolved decisions；
- Ticket plan、依赖图、`AC-ID`/`SLICE-ID` 映射；
- 将创建的正式 issue 数量与 work types。

批准记录：

```md
approval_type: planning
approved_plan_ref:
approved_spec_ref:
approved_ticket_plan_ref:
approved_by:
approved_at:
```

在创建正式票前，Coordinator 必须重新读取 planning MR head。若与 `approved_plan_ref` 不同：

1. 标记旧批准 `invalidated-by-head-change`；
2. 停止建票与派发；
3. 展示新 diff；
4. 请求针对新 exact head 的批准。

## 8. 幂等建票与派发

Coordinator 为每个正式 child issue 使用 workflow-specific key：

```text
planned:
  <parent_issue_key>:<approved_plan_ref>:<SLICE-ID>

fast-path:
  <parent_issue_key>:fast-path:<spec_ref>:<SLICE-ID>
```

创建前先在现有 child issues 中查找该 key：

- 已存在：复用并校验内容，不重复创建；
- 不存在：创建 issue，记录 `SLICE-ID`、`spec_ref`、workflow anchor 与 key；
- 内容冲突：停止该 slice，标 `ready-for-human`，并记录 `human_gate: decision`；不得覆盖历史。

只有通过 ready-for-agent gate 的 slice 才能派发。依赖未完成的票保持未派发。Coordinator 显式声明 Builder `work_type`：

- `implement`：按已批准 spec 实现；
- `diagnose`：可执行调查，只返回证据，不修复；
- `prototype`：回答设计问题的可丢弃实验，不进入生产 MR；
- `review-fix`：仅修复 Coordinator 指定的 Reviewer blocking finding IDs。

## 9. Review dispatch 与自动修复

Coordinator 派发 Reviewer 时必须提供完整且固定的输入：

```md
packet_type: review-dispatch
packet_version: 2026-08-12.3
issue_key:
work_type: implement | review-fix
spec_ref: repo:path@commit
review_base_ref:
review_head_ref:
acceptance_criteria:
standards_sources:
builder_completion_ref:
test_evidence:
review_round:
assigned_finding_ids:
```

规则：

- `spec_ref` 必须解析到完整原始 spec，不得只传摘要或 acceptance criteria。
- `workflow: fast-path` 使用与 planned 相同的 `spec_ref` 格式；不得用 issue 正文、聊天消息或浮动 MR 代替。
- Reviewer 只审查固定的 `review_base_ref...review_head_ref`，不得使用浮动 MR head。
- Reviewer 必须分别执行 Standards axis 与 Spec axis，并在结果中标明每个 finding 所属轴。
- 输入缺失、ref 不可解析或 head 已变化时，返回 `review_result: needs-info`，不得批准。
- Reviewer 只返回审查结果，不修改代码，不直接触发 Builder。

Review 结果至少包含：

```md
review_result: approved | changes-requested | needs-info
standards_result:
spec_result:
finding_ids:
blocking_finding_ids:
review_base_ref:
review_head_ref:
```

自动修复只由 Coordinator 驱动：

```text
Reviewer changes-requested
  -> Coordinator 提取 blocking_finding_ids
  -> Builder(work_type: review-fix)
  -> Coordinator 固定新的 review_head_ref
  -> Reviewer follow-up
```

- `review-fix` 必须携带原 `spec_ref`、原 Builder MR/工作分支和 `assigned_finding_ids`。
- Builder 只能修复指定 finding IDs，不得借机扩大范围或修改 spec。
- 每个执行 issue 最多一次自动 `review-fix` cycle。
- 第二次仍为 `changes-requested`，进入 `ready-for-human`，并记录 `human_gate: decision`。
- Spec 有歧义、需要产品决策或需要改动验收标准时，停止自动修复，回到 Planner/用户决策。

## 10. 执行与审查

```text
ready-for-agent
  -> Builder
  -> in-progress / review
  -> Coordinator
  -> Reviewer（implement/review-fix）
  -> approved / changes-requested / needs-info
  -> Coordinator
```

- `diagnose` 证据回 Coordinator，再由 Coordinator 交 Planner 重规划或更新父 requirement。
- `prototype` 结果回 Coordinator。原型不能直接提升为生产实现；若要实施，须回到批准过的 spec/ticket 流程。
- Reviewer 只审查 pinned `review_base_ref...review_head_ref` 与不可变 `spec_ref`。
- Reviewer 不触发 Builder。Builder 不触发 Reviewer。
- 每个执行 issue 最多一次自动 `review-fix` cycle。第二次 `changes-requested` 后 Coordinator 标 `ready-for-human`，并记录 `human_gate: decision`。
- follow-up review 校验全部 assigned finding IDs、明显新 P0/P1 Standards 回归与 Spec 回归。

## 11. 用户验收与 Final MR

Reviewer 批准且 approved `review_head_ref` 已进入 `source_branch` 后，Coordinator：

1. 标记 `ready-for-human`，并记录 `human_gate: acceptance`；
2. 向用户提供实现摘要、Builder MR、preview、验证证据和风险；
3. 等待明确验收；
4. 验收通过后创建 `source_branch -> final_mr_target` 的 Final MR；
5. Final MR merge 保持人工闸门；
6. 验证 merge 后关闭 child issue；全部 child 完成且父 AC 覆盖后关闭父 requirement。

未经用户验收不得创建 Final MR。Coordinator 不得绕过仓库保护规则或 force merge。

## 12. Canonical states

优先沿用 Matt skills 的状态词汇，不为每个 gate 创建新的公开状态：

```text
needs-triage
needs-info
ready-for-agent
ready-for-human
wontfix
```

五个状态含义：

- `needs-triage`：新需求或 raw issue，尚未完成分诊。
- `needs-info`：缺少用户、Reporter 或上游 Agent 必须提供的信息。
- `ready-for-agent`：范围、验收标准和依赖已明确，可以派发 Agent。
- `ready-for-human`：需要人工决策、用户验收或人工 merge。
- `wontfix`：明确不处理的终态。

执行阶段只在 issue comment 或 handoff packet 中记录，不扩展成新的公开状态：

```text
planning
in-progress
review
changes-requested
acceptance
done
```

`ready-for-human` 必须同时记录 `human_gate`：

```text
human_gate: planning-approval | acceptance | merge | decision
```

推荐主链路：

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

简单双任务可以跳过 `planning` 和 planning approval，直接从 `needs-triage` 进入 `ready-for-agent`。

返回路径：

```text
任何阶段 -> needs-info -> 原阶段
review -> changes-requested -> ready-for-agent
diagnose/prototype -> planning
```

`needs-info` 恢复时必须在 comment 或 packet 中保留原阶段。`wontfix` 不转换为 `done`。只有 Coordinator 改变跨 Agent 状态。

## 13. 引用与 ID 规则

- `spec_ref`：`repo:path@commit`，例如 `dashboard:docs/specs/MIC-123.md@abc123...`。
- 分支链：
  - `workflow: planned`：`base_branch -> source_branch -> planning_branch | work_branch`。
  - `workflow: fast-path`：`base_branch -> source_branch -> work_branch`，planning fields 均为 `not-required`。
- `planning_head`、`review_base_ref`、`review_head_ref`：完整 commit SHA。
- `AC-ID`：spec 内稳定验收标准标识。删除时标 deprecated，不重新编号复用。
- `SLICE-ID`：Ticket plan 内稳定垂直切片标识。重规划保留未变 slice 的 ID。
- packet/ref 必须可从 issue/MR 永久解析；聊天消息不能作为唯一事实源。

## 14. 权限摘要

- Coordinator：issue/MR 控制面、assign、状态、允许的内部 merge、Final MR 创建；不得实现代码。
- Planner：只读代码与 git；仅 planning branch 上允许文档；仅 docs-only MR；不得正式建票、assign、merge。
- Builder：只在 dispatch packet 允许的 repo/branch/mode 内执行。
- Reviewer：只读代码、diff、spec 与测试证据；只写 review result。
- Inspector：权限由当前 inspection profile 明确限定；默认只读。
