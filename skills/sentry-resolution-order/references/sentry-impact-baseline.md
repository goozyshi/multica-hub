# Sentry 解决单影响趋势参考（可选）

本 Reference 是对现有创建/复用解决单流程的可选扩展。除非调用方、Autopilot 配置或用户明确启用“影响趋势观测”，否则不要读取或执行本文件中的附加步骤；未启用时，既有建单、去重、卡片状态和派发流程必须保持不变。

## Autopilot 配置

- 解决单 Autopilot 设置 `impact_trend_observation: enabled` 时，用户点击创建或复用解决单后建立基线；字段缺失或值不是 `enabled` 时跳过基线。
- `observation_timeout_days` 必须是正整数，用于限制未出现修复信号或人工确认时的最长自动采样周期；必须由当前解决单 Autopilot 提供。出现修复信号后，仍按 `post_fix_observation_days` 完成观察。
- `post_fix_observation_days` 必须由当前解决单 Autopilot 提供，且为正整数。
- 影响趋势启用时，callback 必须携带 `impact_observation_snapshot`；其
  `schema` 为 `sentry_impact_table_v1`，并包含固定列定义和至少一行当前窗口数据。
- 这些字段属于解决单 Autopilot 配置，不属于日报 Autopilot 的 `resolution_enabled`；仅写入 `observation_timeout_days` 不会启用基线。

## 目标与边界

- 记录用户点击创建/复用解决单时的 Issue 影响基线，并在后续固定窗口保留同结构表格，
  对事件数量和影响用户变化进行逐行比较。
- 该数据只能作为“趋势下降/持续回归”等辅助证据，不能单独证明根因已修复、解决单可关闭或 Sentry Issue 可关闭。
- 不因基线写入失败阻塞已经成功的解决单创建或复用；应标记为待补齐并保留原始触发快照。
- 没有用户点击创建或复用解决单时，不创建基线记录。

## 关联键与数据来源

- 唯一关联键：`project:issue_id`，与既有 `sentry_dedupe_key` 完全一致。
- 优先复用已验证卡片快照中的 `project`、`issue_id`、`event_count`、`user_count`、`first_seen`、`last_seen`、`release`、`environment`、`snapshot_at`、`evidence_source` 和 `detail_fetched_at`。
- `impact_observation_snapshot` 是本轮表格数据的唯一结构化来源；必须保留其
  `schema`、`columns`、`rows`、查询窗口和过滤条件，不能只从卡片上的格式化文本恢复。
- 基线必须记录精确的 `window_start`、`window_end`、查询条件和采集时间，不能只记录“当天”。
- 建议增加 `baseline_source: card_snapshot`；若因快照过期而重新查询，改为 `baseline_source: fresh_query` 并同时保留卡片快照时间。

## 基线生命周期

### 新建解决单

1. 通过验签、项目白名单、当前 Issue 状态和幂等校验。
2. 解决单创建成功后，原子地写入一次不可覆盖的基线表格快照。
3. 基线写入失败时记录 `baseline_status: pending`，不得伪造已记录状态；同时保留 callback
   中的原始结构化快照，便于补采。

### 复用解决单

- 已存在基线时禁止覆盖；只更新 `last_reused_at` 或追加一行观测表数据。
- 历史解决单没有基线时，可以补采，但必须标记 `baseline_source: backfilled` 和 `baseline_captured_at`，不能冒充首次创建基线。
- 解决单为 `done` 或 `cancelled` 后重新创建时，开启新的 `baseline_generation`，并保留旧周期关联。

### 并发与幂等

- 多人同时点击时，同一 `project:issue_id` 只允许一个活动基线；使用元数据存在性检查或等价的原子条件写入。
- 基线写入与解决单创建是两个步骤，任何一步重试都不得创建重复解决单或覆盖原基线。

## 存储建议

机器可查询字段写入解决单 metadata，至少包括：

```text
sentry_baseline_event_count
sentry_baseline_user_count
sentry_baseline_table_schema
sentry_baseline_table_columns
sentry_baseline_table_json
sentry_baseline_captured_at
sentry_baseline_window_start
sentry_baseline_window_end
sentry_baseline_filter
sentry_baseline_environment
sentry_baseline_release
sentry_baseline_source
sentry_baseline_generation
sentry_repair_signal_at
sentry_repair_signal_source
sentry_repair_signal_detail
sentry_post_fix_observation_started_at
sentry_post_fix_observation_until
sentry_observation_sample_count
sentry_observation_table_json
sentry_observation_result
sentry_observation_stopped_at
sentry_observation_stop_reason
```

解决单中可增加一个简短可读区块：

```md
## Sentry 影响趋势（辅助证据）

结论：<趋势结论>。该结论不等同于已解决。

| 类型 | 采集时间 | 查询窗口 | 分组 | 项目 / Issue | 环境 | Release | 事件数 | 影响用户 | 相对基线 | 可能修复节点 |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- | --- |
| 创建基线 | <timestamp> | <start> ~ <end> | <group> | <project> / <issue-id> | <env> | <release> | <count> | <count> | — | — |
| 后续观测 | <timestamp> | <start> ~ <end> | <group> | <project> / <issue-id> | <env> | <release> | <count> | <count> | <delta / percentage> | <signal> |
```

表格每次追加一行，不覆盖创建基线；`sentry_baseline_table_json` 保存不可变基线，
`sentry_observation_table_json` 保存按时间追加的结构化行。解决单正文可展示基线和
全部已采样行，若平台正文有长度限制，则正文展示基线与最新窗口，完整行仍必须保留在
独立观测记录中，不能丢弃或改写。

## 后续观测规则

- 只观测已经存在活动解决单且具备基线的 `project:issue_id`；没有用户动作形成的解决单不产生基线，也不生成“解决后趋势”。
- 使用与基线相同的项目、时间窗口、filter、environment、Sentry 分组和计数口径。当前日报为 `24h` 时，观测也必须是同口径滚动窗口；每次采样追加一行与基线相同列结构的数据。
- 至少记录 `observed_at`、`window_start`、`window_end`、`event_count`、`user_count`、`release`、`sentry_status` 和 `resolution_issue_id`。
- 修复发布信息（如 `fix_release` / `fix_release_at`）是可选的修复节点信号；缺失时仍可记录观测，但不得声称已发布或已修复。
- 按 `project:issue_id` 对齐行后，事件数下降可计算为 `(baseline - current) / baseline`，
  影响用户同样保留绝对差值和变化比例；基线为 0 时不计算比例。
- 后续窗口未返回某 Issue 时标记“本窗口未返回”，不得直接当作 0；只有 Sentry 明确
  返回 0 才写入 0。
- 查询窗口、过滤条件、Issue fingerprint、release 或分组发生变化时标记“数据不可比”，不得直接计算下降率。

## 修复节点记录（不新增状态机）

- 修复节点只是每日观测表中的附加证据，不新增解决单状态，也不触发状态转换。
- 用户明确说“已修复”“已上线”“已验证”或描述一次修复尝试时，记录 `repair_signal_at`、`repair_signal_source: user_report` 和脱敏的 `repair_signal_detail`。
- CI/发布事件、Sentry 新 release、MR 合并或其他观测渠道感知到可能的修复节点时，同样追加一行，来源填 `ci_release`、`sentry_release`、`mr_merged` 或 `other`；无法确认的信号也只记录，不升级为确定结论。
- 同一天存在多个信号时逐行追加或合并为简短文本；不得覆盖原始基线，也不得因为信号出现自动关闭解决单或 Sentry Issue。
- 观测继续按固定窗口记录事件数、影响用户数、release、Sentry 状态和 `top5_present`；是否真的修复仍由用户/人工验收决定。

修复节点字段建议：

```text
repair_signal_at
repair_signal_source
repair_signal_detail
```

上述字段为空时照常写入每日观测；没有用户创建或复用解决单时，不建立基线，也不写入解决后观测。

## 观测停止与解决单状态（不新增状态机）

- `todo`、`in_progress`、`blocked`、`in_review` 都表示解决单仍在处理中，继续按相同口径每日观测。`in_review` 只表示代码评审，不是修复节点。
- 出现明确修复信号后，记录 `repair_signal_*`，并设置 `post_fix_observation_started_at` 与 `post_fix_observation_until`。观测周期使用当前解决单 Autopilot 的 `post_fix_observation_days`；此期间解决单不能提前标记为 `done`。
- 只有后续观测窗口完成，且用户/人工确认修复，才将解决单标记为 `done`，写入 `observation_result`、`observation_stopped_at` 和 `observation_stop_reason: verified_done`，随后停止观测。
- 窗口内仍有异常或趋势不可比时，不得标记为 `done`；保持处理中或由人工重新打开/建立后续解决单。观测结果是证据，不自动驱动状态转换。
- `cancelled` 立即停止观测，写入 `observation_stop_reason: cancelled`；取消不代表已修复。后续重新处理时建立新的 `baseline_generation`。
- 超过当前解决单 Autopilot 配置的 `observation_timeout_days` 仍没有修复信号或人工确认时，可停止自动采样并写入 `observation_stop_reason: timeout_manual_confirmation`；结果标记为待确认/未知，不得标记为已修复。
- 若历史流程在观测窗口完成前已写入 `done`，将 `done_at` 视为候选人工信号，继续完成观测；若仍有异常，标记状态语义冲突并交由人工决定是否重新打开，不自动回写状态。

## 安全与兼容性

- 只保存计数、时间、项目、Issue、版本、环境和脱敏摘要；禁止写入完整堆栈、IP、用户标识、原始敏感标签、App Secret 或 Webhook。
- 基线/观测属于附加数据；卡片按钮三态、解决单去重、Coordinator → `target_assignee` 派发和既有 Autopilot 状态同步不变。Coordinator → Builder 不属于本 Reference 的流程。
- 趋势查询失败只影响趋势字段，不能回滚已经成功的建单或复用；应显示“证据不足”并保留触发快照。
- 本 Reference 不改变现有 `SKILL.md` 的配置驱动流程。若启用独立的定时观测，还需单独补充观测触发器和验收标准。
