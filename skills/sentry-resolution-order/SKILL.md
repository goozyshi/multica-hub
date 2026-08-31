---
name: sentry-resolution-order
description: 处理飞书 Sentry 卡片的创建解决单请求，校验并去重后按 Autopilot 指定的 Agent 或 Squad 建单。用于跨项目复用的 Sentry 解决单派发。
---

# Sentry 解决单

## 输入

从回调 Autopilot 读取 `scope_project`、`sentry_org`、`allowed_projects`、`target_assignee_type`、`target_assignee`、`priority_mapping`。从已验证的飞书回调读取 `request_id`、点击人、项目、`sentry_issue_id`、fingerprint、Sentry 链接、风险评分和日报证据摘要；如果存在，同时读取 `culprit`、`release`、`environment`、`event_count`、`user_count`、`first_seen`、`last_seen`、`evidence_source`、`snapshot_at`、`inspection_issue_id`、`detail_snapshot`、`detail_fetched_at`、`analysis_summary` 和 `analysis_confidence`。

## 安全与去重

仅接受通过飞书回调签名校验、且项目位于 `allowed_projects` 的请求。以 `project + sentry_issue_id` 为去重键；存在未关闭解决单时不得重复创建，返回已有单据。不得把完整堆栈、IP、用户标识写入单据。

创建或复用解决单后，返回 `solution_issue_id`、`solution_issue_url` 和当前状态，供巡检卡片下次渲染。新建解决单必须写入可查询元数据：`sentry_dedupe_key`、`sentry_project`、`sentry_issue_id`；历史单据缺少元数据时，可通过描述中的去重键精确匹配并在确认后补齐元数据，避免同一问题重复建单。

## 详情复核与快照复用

回调中的列表快照和 `detail_snapshot` 是巡检阶段的触发上下文。Coordinator 不应无条件重复调用 Sentry MCP：

- `detail_snapshot` 完整、`detail_fetched_at` 在有效时间内（默认 15 分钟）、Issue 状态未变化且 `sentry_issue_id` / fingerprint 一致时，直接复用详情证据和 `analysis_summary`；
- 快照缺失、超过有效时间、Issue 状态变化、fingerprint 不一致或 `analysis_confidence` 为低时，才使用自身已配置的 Sentry MCP（`get_sentry_resource`）重新读取 Issue 详情及代表性事件；
- 无论是否复用，都要在建单前校验 Issue 当前状态和去重键；快照不能替代幂等校验；
- 详情读取失败或权限不足：仍可基于已验证快照建单，但明确记录“证据不足，需人工在 Sentry 复核”，不得编造根因或代码位置；
- 写入前对堆栈、标签和事件上下文做脱敏，只保留定位解决问题所需的最小信息。`detail_snapshot` 只允许包含异常类型、代表性堆栈位置、路由/接口、`culprit`、版本、环境、读取时间和简短事实摘要。

创建解决单时，在“列表快照”与“详情证据”小节分别记录来源，并以详情证据优先支撑初步判断；若复用巡检分析，保留 `evidence_source`、`detail_fetched_at`、`analysis_summary` 和 `analysis_confidence`，便于追溯。

状态回写约定：`todo`、`in_progress`、`in_review`、`blocked` 映射为“处理中 · 解决单已存在”；`done`、`cancelled` 不阻止下一轮创建。回调幂等命中已有未关闭解决单时，不创建新单，只返回原单链接和状态。

## 建单与派发

创建并派发至 `target_assignee_type` / `target_assignee`。`target_assignee_type` 只能是 `agent` 或 `squad`；`agent` 直接指向指定 Agent，`squad` 指向指定 Squad，实际执行由该 Squad 的 leader agent 完成。回调 Autopilot 自身的执行者仍是 Coordinator，这与解决单的目标 assignee 分开配置。

标题固定为：

`【Sentry解决】<项目> <异常摘要> #<sentry_issue_id>`

异常摘要最多 40 字。内容固定包含以下小节：`处理目标`、`影响与证据`、`初步判断`、`解决要求`。其中记录项目、Sentry Issue、优先级、链接、来源、去重键、事件数、影响用户数、发生时间、版本/环境、异常摘要、风险评分、推断原因、证据摘要、详情复核状态和置信度。解决要求固定为：复核影响、定位根因、给出修复与验证方案、说明风险和回滚建议。

## 后续实现派发（默认关闭）

创建或复用解决单并派发至 `target_assignee_type` / `target_assignee` 后，Coordinator 默认结束本次流程，不创建实现子单、不执行仓库/分支校验，也不直接派发 Builder。后续实现、评审、合并和验收由目标 Agent 或 Squad 自行负责：Agent 直接处理，Squad 由 leader 决定是否拆分并派给 Builder。

只有 Autopilot 明确配置 `post_resolution_flow: coordinator_validated_builder`，并同时提供独立且可解析的 `implementation_target_type` / `implementation_target` 时，才允许启用额外的实现子流程。此时仍须完成需求、repo、分支、Delivery Context 和 testability 校验，以 `<project>:<sentry_issue_id>:implementation` 去重，并按显式目标派发；不得从 `target_assignee` 推断 Builder，也不得在 Skill 中写死业务小队。

未配置、配置为 `target_assignee_owned` 或 `enabled: false` 时，明确跳过该额外流程。无论是否启用，Coordinator 都不修改代码、不自动合并、发布或关闭 Sentry Issue。

## 影响趋势观测（显式启用）

当调用方、Autopilot 配置或用户明确启用“影响趋势观测”时，读取 `references/sentry-impact-baseline.md`。该 Reference 仅增加基线、后续观测和停止规则，不改变默认建单、去重、卡片状态或 Coordinator → `target_assignee` 派发流程；未显式启用时不要执行附加观测。

## 边界

本 Skill 只创建或复用解决单并派发；不修改代码、不发布、不关闭 Sentry Issue。代码修改或发布必须在解决单中另行取得人工确认。创建或复用结果可用于更新飞书卡片状态。
