---

## name: sentry-resolution-order

description: 处理 Sentry“创建解决单”回调，按当前 Autopilot 配置完成验签、授权、幂等、解决单创建和平台级 Agent/Squad 派发。

# Sentry 解决单

本 Skill 定义通用的回调处理协议，不内置项目、目标 Agent/Squad、优先级、快照时效、父子流程或观测周期。所有业务范围、目标 UUID 和流程开关必须从触发本次运行的 Autopilot 读取。收到 Sentry“创建解决单”回调后，按以下顺序执行；创建、复用、详情复核、派发和后续实现规则见 [解决单创建与派发 Reference](references/resolution-creation-and-dispatch.md)。

## Autopilot 配置

从当前回调 Autopilot 读取本次业务配置，包括作用域、Sentry 组织、项目白名单、优先级映射、目标类型与目标 UUID，以及可选的快照复用、父子流程和影响趋势观测配置。配置缺失、类型错误或无法解析时返回 `needs-info`；不得使用 Skill 内置默认值或自行猜测。

## 回调输入

从已验证的回调读取 `request_id`、点击人、项目、`sentry_issue_id`、fingerprint、Sentry 链接、风险评分和日报证据摘要；如果存在，同时读取 `culprit`、`release`、`environment`、`event_count`、`user_count`、`first_seen`、`last_seen`、`evidence_source`、`snapshot_at`、`inspection_issue_id`、`detail_snapshot`、`detail_fetched_at`、`analysis_summary` 和 `analysis_confidence`。

## `create_issue` 运行单根节点

当前 Autopilot 的 `execution_mode=create_issue` 时，平台已经先创建当前运行 Issue，并将其交给 Autopilot 执行 Agent。将当前运行 Issue 的 UUID 记录为 `runtime_issue_id`，作为本次流程的根父单；不得再创建第二个无 `parent` 的顶层解决单。实际 Sentry 解决单必须作为该运行单的子单，并单独绑定 Autopilot 配置的目标 Agent 或 Squad。

`execution_mode=run_only` 没有平台预创建运行单时，实际 Sentry 解决单才可以直接作为根单。两种模式都必须区分 `runtime_issue_id`、`solution_issue_id` 和 Builder 执行子单 ID。

## 执行流程

1. 读取并解析回调 Autopilot 配置和已验证的飞书回调。
2. 按 Reference 完成签名、项目白名单、输入字段、当前 Issue 状态和幂等校验；失败时返回明确错误，不创建解决单。
3. 按 Reference 和当前 Autopilot 的快照配置判断是否复用详情；必要时重新读取 Issue 详情。完成脱敏、证据归档和带目标 assignee 的解决单创建或复用。
4. 按 Reference 通过平台级 Issue assignee 创建实际 Sentry 解决单：`create_issue` 模式必须同时使用当前 `runtime_issue_id` 作为 `--parent` 和 `target_assignee` 作为 `--assignee-id`；`run_only` 模式使用 `--assignee-id` 直接创建根单。创建后立即回读 `parent_issue_id`、`assignee_type`、`assignee_id`。正常流程禁止先建 Coordinator 单再调用 `issue assign`。
5. 按当前 Autopilot 的父子流程配置判断是否创建 Builder 执行子单；启用且门禁通过时，必须以 `solution_issue_id` 作为 `parent`，创建并指派独立配置的 Agent 或 Squad，回读父子关系和 assignee；未启用时返回解决单结果并跳过子单。
6. 仅当当前 Autopilot 明确启用“影响趋势观测”时，读取并执行 [影响趋势基线 Reference](references/sentry-impact-baseline.md)；未启用时跳过附加观测。

## 完成条件

以下任一条件满足时结束：

- 校验失败：返回字段级错误，且未创建解决单；
- `create_issue` 根流程完成：运行根单与实际解决单的 `parent_issue_id`、平台级目标 assignee 均已回读匹配，并返回用户可见根单链接；
- `run_only` 根流程完成：实际解决单创建或复用、平台级目标 assignee 已回读，并返回解决单链接；
- 父子流程启用：已完成以实际解决单为父单的 Builder 子单创建、父子关系与平台级 assignee 回读；
- 目标绑定或回读失败：保留已创建解决单，返回 `dispatch blocked`，不得报告已派发或已触发执行；
- 子单门禁未通过或未启用：实际解决单保留处理中，明确返回 `child_pending`；
- 当前 Autopilot 已启用影响趋势观测：同时记录基线或明确记录基线写入结果。

## 边界

本 Skill 只创建或复用解决单并派发；不修改代码、不发布、不关闭 Sentry Issue。代码修改或发布必须在解决单中另行取得人工确认。
