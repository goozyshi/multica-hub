# Sentry 解决单影响基线参考（可选）

仅在 callback 明确携带 `impact_trend_observation: enabled` 时读取。本 Reference
只负责在创建或复用解决单时记录一次不可变基线，不创建观测 schedule，不由每日巡检
扫描活动解决单，也不执行后续自动追加。

## 目标与边界

- 基线记录用户点击创建/复用解决单时的 Issue 影响事实。
- 基线只能作为后续人工复核的比较起点，不能单独证明根因已修复或 Issue 可关闭。
- 没有用户动作形成的解决单不创建基线。
- 基线写入失败不回滚已经成功的解决单创建或复用；必须记录
  `baseline_status: pending` 并保留 callback 快照。

## 数据来源与一致性

- 唯一关联键：`project:issue_id`，与 `sentry_dedupe_key` 完全一致。
- 优先使用已验证 callback 中的 `project`、`issue_id`、`issue_title`、`event_count`、
  `user_count`、`first_seen`、`last_seen`、`release`、`environment`、`time_window`、
  `filter`、`window_start`、`window_end`、`snapshot_at` 和 `evidence_source`。
- 不重新计算或混用其他时间窗口的数据。
- callback 缺少必需字段、窗口不完整或项目与去重键不一致时，返回 `needs-info`，
  不写入伪造基线。

## 创建与复用

### 新建解决单

1. 完成签名、来源 Autopilot、项目白名单、当前 Sentry Issue 状态和幂等校验。
2. 创建解决单成功后写入一次基线 metadata。
3. 同时在解决单正文中写入固定 Markdown 表格，表格至少包含一行“创建基线”。

### 复用解决单

- 已存在基线时禁止覆盖，也不追加新的观测行；只返回原基线和复用结果。
- 历史单据缺少基线时，可以根据已验证 callback 补写一次，并标记
  `baseline_source: backfilled`。
- 已存在活动解决单但目标、项目或去重键不匹配时，不静默改写，返回
  `needs-info` 或 `dispatch blocked`。

## 必须保存的 metadata

```text
sentry_baseline_event_count
sentry_baseline_user_count
sentry_baseline_captured_at
sentry_baseline_window_start
sentry_baseline_window_end
sentry_baseline_time_window
sentry_baseline_filter
sentry_baseline_environment
sentry_baseline_release
sentry_baseline_source
sentry_baseline_generation
sentry_baseline_status
sentry_baseline_table_schema
sentry_baseline_table_columns
sentry_baseline_table_json
```

如果使用结构化表格，`sentry_baseline_table_schema` 固定为
`sentry_impact_table_v1`，`sentry_baseline_table_json` 保存完整 JSON 对象或数组，
不得只保存截图或文案摘要。未知计数保持为空，不得填充为零。

## 正文格式

```md
## Sentry 影响基线

| 类型 | 采集时间 | 查询窗口 | 项目 / Issue | 环境 | Release | 事件数 | 影响用户 | 来源 |
| --- | --- | --- | --- | --- | --- | ---: | ---: | --- |
| 创建基线 | <timestamp> | <start> ~ <end> | <project> / <issue-id> | <env> | <release> | <count> | <count> | <source> |
```

表格必须使用真实字段渲染；缺失值留空并注明证据不足，不得把空值写成 0。

## 安全与兼容性

- 只保存项目、Issue、窗口、计数、版本、环境和脱敏摘要；禁止写入完整堆栈、IP、
  用户标识、Webhook 或凭据。
- 基线写入不改变解决单状态、目标 assignee 或既有幂等规则。
- 本 Reference 不提供“修复后趋势”或自动关闭流程；如果未来需要，应另行设计
  明确的人工/发布触发器和观测周期。
