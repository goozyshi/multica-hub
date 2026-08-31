---
name: sentry-daily-top-issues
description: 通过 Sentry MCP 列表查询生成按 Autopilot 分组配置汇总的 Error Issue 简报，使用可读的 Markdown 卡片布局，并提供可控的一键解决单动作。用于日报、周报或其他 Top N 巡检。
---

# Sentry Top Issue 简报

## Autopilot 配置解析

Autopilot 描述采用 Markdown 分组格式。固定系统字段位于“基本信息”，业务参数位于“查询配置”“项目分组”“展示配置”“动作配置”“发送配置”；执行逻辑位于 Skill。解析每个配置区块中形如 `- key: value` 的键值，以及“项目分组”表格中的三列 `分组`、`项目`、`Top N`。表格的分隔线行不是数据。`Top N`、`display_top_n`、时间窗口和项目名称必须来自当前 Autopilot；Skill 不提供业务数量或名称默认值。读取 Markdown 描述中的 `inspection_url_template` 时，按原始 HTTPS 基础 URL 前缀解析，发送时拼接当前巡检 Issue ID；历史配置可兼容一个 `<Issue-ID>` 占位符，也可还原编辑器产生的同值 `[URL](URL)` 包装，但不得接受隐藏或改写后的目标。

执行前严格校验：拒绝未知区块或未知字段；拒绝缺失必填项、重复项目、空分组、非正整数、非法枚举和无效 IANA 时区。`display_top_n` 是最终展示数量；各组 `Top N` 只用于组内候选数，二者不可混用。`resolution_enabled: true` 时必须有有效 `resolution_autopilot` 和 `dedupe_key`。发送配置的通道校验见 [飞书卡片与发送 Reference](references/feishu-card-delivery.md)。模板配置阶段不要求预先存在具体巡检 Issue ID；发送前必须取得当前巡检 Issue ID，并按 Reference 将其传入 validator 完成最终 URL 解析。校验失败时输出字段级错误，结果为 `needs-info`，不得发起 Sentry 查询或发送消息。

触发器、订阅者、Autopilot agent、执行模式和项目范围由 Multica Autopilot 字段管理，不复制到人工配置区；修改周报频率只调整 schedule trigger，不修改 Skill。

## 查询与排序

仅通过 Sentry MCP 的 `search_issues` 查询项目分组表中每个项目。将 `source`、`time_window`、`filter`、`environment`、`sort` 和对应 `Top N` 原样应用。不得改用 `search_events`、智能搜索或补造事件数。查询失败时报告对应分组和错误，不能把缺失数据当成零。

每组按事件数降序取 `Top N`，并把全部分组结果写入巡检 Issue。然后从所有组的候选项按事件数、影响用户数、最近活跃度取 `display_top_n` 条全局结果；卡片只展示这些结果，不再同时展示各组列表，避免重复。

## 初步研判

列表查询完成后，先按所有分组结果选出最终 `display_top_n` 条，再仅对这些条目调用 Sentry MCP `get_sentry_resource` 读取 Issue 详情及代表性事件；不得为全部候选逐条读取详情。详情调用失败不影响排序，但必须标记“证据不足”。

每条 Issue 优先使用详情中的异常信息、代表性堆栈位置、路由/接口、`culprit`、`release`、环境、状态、事件数、影响用户数和最近活跃时间，生成一句“可能原因”和一句“建议处理”；详情不可用时回退到列表字段并明确标记“证据不足”。两句均为初步研判，不得写成已确认根因。

- 有明确异常类型、模块、路由或 HTTP 状态时，才可据此归类；例如网络/请求失败可建议核查接口可用性、状态码、超时和网络路径。
- 标题或定位不足以支撑判断时，写“证据不足，需查看 Sentry 事件详情”，并建议进入 Sentry 核对首个异常、最近发布与上下文。
- 不得编造根因、代码位置、影响范围、修复已完成状态或需要外部检索才能成立的结论。

涉及 Web 前端/后端/客户端归因时，读取 [Sentry 错误归因 Reference](references/ownership-attribution.md)；仅在需要归因的分支读取，普通列表排序不加载该 Reference。

## 详情快照与传递

详情读取成功后，为每条最终候选生成脱敏 `detail_snapshot`，至少包含异常类型、代表性堆栈位置、路由/接口、`culprit`、版本、环境、详情读取时间 `detail_fetched_at`、证据来源 `evidence_source: sentry_detail` 和简短事实摘要。完整堆栈、IP、用户标识和原始标签不得进入快照。

需要生成飞书动作时，读取 [飞书卡片与发送 Reference](references/feishu-card-delivery.md)，按其中的载荷规则携带列表快照、`detail_snapshot`、`detail_fetched_at`、`evidence_source`、`analysis_summary`、`analysis_confidence` 和 `inspection_issue_id`。快照用于解决 Agent 复用，不能替代其幂等和状态校验。

## 解决单状态与页面定位

输出状态前，以 `project:issue_id` 查询 `resolution_autopilot` 已创建的解决单状态，优先使用解决单元数据 `sentry_dedupe_key`；历史单据无元数据时，使用描述中的去重键精确匹配并回填。未关闭状态包括 `todo`、`in_progress`、`in_review`、`blocked`；`done`、`cancelled` 视为可再次创建。查询失败时不阻塞巡检结果，标记“状态待校验”，由回调 Autopilot 做最终幂等判断。飞书按钮状态和动作见 [飞书卡片与发送 Reference](references/feishu-card-delivery.md)。

- 页面定位优先取详情中的路由/页面字段；没有详情时取列表 `culprit` 中可读的页面路径。无定位信息时省略该字段，不填造路径。

## 飞书输出与发送

需要生成或发送飞书消息时，读取 [飞书卡片与发送 Reference](references/feishu-card-delivery.md)。该 Reference 定义通道配置校验、首次创建的告警颜色与视觉层级、`global_top_n_markdown_v1` Card 2.0 结构、按钮状态、回调载荷、发送前一致性校验和发送命令。未通过 Reference 中的校验时，保留巡检结果并按规定返回 `needs-info` 或 `blocked`，不得发送消息。

卡片状态更新同样读取该 Reference：基于已发送 Card JSON 只替换对应按钮，使用 `--previous-card` 校验非按钮结构和视觉样式未变化；校验失败不得调用 Lark 更新接口。

## 解决单动作与幂等

解决单动作的触发载荷、快照字段、按钮行为和字段级校验见 [飞书卡片与发送 Reference](references/feishu-card-delivery.md)。快照只是触发上下文，不能替代解决单 Autopilot 的幂等和状态校验。

同一 `project:issue_id` 已有未关闭解决单时返回原单，不重复创建；前一轮未建单但后续进入当前 Autopilot 配置的项目分组 `Top N` 候选范围时可创建；已关闭旧单不阻止新一轮建单。卡片成功发送不表示解决单已创建。

## 结果

按通用结果包结束。`result: executed` 表示配置校验、所有分组查询和飞书消息发送均成功；校验、查询或发送失败均为 `blocked`。
