# Sentry 解决单创建与派发 Reference

仅在当前回调需要创建或复用 Sentry 解决单时读取本 Reference。它定义通用安全校验、幂等去重、详情复核、解决单内容和目标派发协议；目标 UUID 和 Sentry 事实必须从已验证 callback 读取，不得从本文示例取得默认值。

## 业务配置传递协议

callback 必须包含 `resolution_autopilot`、`target_assignee_type`、`target_assignee` 和 `resolution_config_version: business_resolution_config_v1`。先确认 `resolution_autopilot` 等于当前解决单 Autopilot ID，再校验飞书签名、目标 UUID 和 callback 结构。解析 Markdown 描述时允许先还原一层 `\_` 字段名转义；不得接受其他隐藏或改写后的配置。

从已验证 callback 读取 `sentry_org`、`project`、`target_assignee_type`、`target_assignee`、优先级、快照和影响趋势观测配置。callback 直接携带的目标必须通过 UUID 格式、workspace 可指派性和飞书签名校验；配置缺失、配置不完整或解析失败时返回 `needs-info` 或 `dispatch blocked`，不得创建解决单。

## 安全与去重

- 仅接受通过飞书回调签名校验、且 callback 的目标类型和目标 UUID 通过校验的请求。
- 以 `project + sentry_issue_id` 为去重键；存在未关闭解决单时不得重复创建，返回已有单据。
- 不得把完整堆栈、IP、用户标识写入单据。
- 新建解决单必须写入可查询元数据：`sentry_dedupe_key`、`sentry_project`、`sentry_issue_id`。
- 历史单据缺少元数据时，可通过描述中的去重键精确匹配并在确认后补齐元数据，避免同一问题重复建单。

创建或复用解决单后，至少记录并返回：

- `runtime_issue_id`：`create_issue` 模式下由 Autopilot 自动生成的当前运行单 UUID；
- `solution_issue_id`、`solution_issue_url`：实际 Sentry 解决单；
- `user_visible_issue_id`、`user_visible_issue_url`：用户从飞书进入的入口；`create_issue` 模式使用运行根单，`run_only` 模式使用实际解决单；
- 当前解决单状态及平台 assignee。

用户可见入口与实际解决单必须同时保留，不能用运行根单 ID 覆盖 `solution_issue_id`。

## `create_issue` 运行单根父单

`execution_mode=create_issue` 时，Autopilot 平台会在 Skill 开始执行前创建当前运行 Issue。该 Issue 是本次流程的根父单，通常由 Autopilot 配置的 Coordinator Agent 执行；它不是需要再次创建的解决单，也不要求通过后置 `issue assign` 改派给目标 Squad。实际解决单的项目必须取来源巡检 Autopilot 的 `project_id`，不能取目标 Agent/Squad 或当前运行根单的项目。

创建实际 Sentry 解决单时，必须把来源巡检 Autopilot 的 `project_id` 作为
`project`、当前运行单 UUID 作为 `parent`，并在同一个创建请求中绑定 callback 提供的目标：

```bash
multica issue create ... \
  --project <source_inspection_project_id> \
  --parent <runtime_issue_id> \
  --assignee-id <target_assignee>
```

创建后必须同时回读：

- 实际解决单 `parent_issue_id == runtime_issue_id`；
- 实际解决单 `project_id == source_inspection_project_id`；
- 实际解决单 `assignee_type == target_assignee_type`；
- 实际解决单 `assignee_id == target_assignee`。

四项任一不匹配时，保留已创建单并返回 `dispatch blocked`；不得创建第二个无
`parent` 的顶层解决单，也不得把运行根单误报为已派发给目标。

`execution_mode=run_only` 没有平台预创建运行单，实际解决单才直接作为根单创建：

```bash
multica issue create ... \
  --project <source_inspection_project_id> \
  --assignee-id <target_assignee>
```

`run_only` 模式同样必须传入 `--project <source_inspection_project_id>`；目标
Agent/Squad 只决定 `--assignee-id`，不能决定 Issue 的项目归属。

如果 `create_issue` 模式无法取得当前 `runtime_issue_id`，停止创建并返回 `dispatch blocked`。

## 详情复核与快照复用

回调中的列表快照和 `detail_snapshot` 是来源巡检阶段的触发上下文。Coordinator 不应无条件重复调用 Sentry MCP：

- `detail_snapshot` 完整、`detail_fetched_at` 在当前解决单 Autopilot 配置的有效时间内、Issue 状态未变化且 `sentry_issue_id` / fingerprint 一致时，直接复用详情证据和 `analysis_summary`；
- 快照缺失、超过有效时间、Issue 状态变化、fingerprint 不一致或 `analysis_confidence` 为低时，才使用自身已配置的 Sentry MCP（`get_sentry_resource`）重新读取 Issue 详情及代表性事件；
- 无论是否复用，都要在建单前校验 Issue 当前状态和去重键；快照不能替代幂等校验；
- 详情读取失败或权限不足：仍可基于已验证快照建单，但明确记录“证据不足，需人工在 Sentry 复核”，不得编造根因或代码位置；
- 写入前对堆栈、标签和事件上下文做脱敏，只保留定位解决问题所需的最小信息。`detail_snapshot` 只允许包含异常类型、代表性堆栈位置、路由/接口、`culprit`、版本、环境、读取时间和简短事实摘要。

创建解决单时，在“列表快照”与“详情证据”小节分别记录来源，并以详情证据优先支撑初步判断；若复用巡检分析，保留 `evidence_source`、`detail_fetched_at`、`analysis_summary` 和 `analysis_confidence`，便于追溯。

状态回写约定：

- `todo`、`in_progress`、`in_review`、`blocked` 映射为“处理中 · 解决单已存在”；
- `done`、`cancelled` 不阻止下一轮创建；
- 回调幂等命中已有未关闭解决单时，不创建新单，只返回原单链接和状态。

## 解决单内容

标题固定为：

`【Sentry解决】<项目> <异常摘要> #<sentry_issue_id>`

异常摘要最多 40 字。内容固定包含以下小节：

- `处理目标`
- `影响与证据`
- `初步判断`
- `解决要求`

内容记录项目、Sentry Issue、优先级、链接、来源、去重键、事件数、影响用户数、发生时间、版本/环境、异常摘要、风险评分、推断原因、证据摘要、详情复核状态和置信度。

解决要求固定为：复核影响、定位根因、给出修复与验证方案、说明风险和回滚建议。

## 平台级目标派发

`target_assignee_type` / `target_assignee` 是平台级 Issue 指派配置，不是描述文本。`target_assignee` 必须是目标 Agent 或 Squad 的 UUID；不得用 `@名称`、昵称或自然语言路由代替。

创建并派发至目标：

- `target_assignee_type` 只能是 `agent` 或 `squad`；
- `agent` 直接指向指定 Agent；
- `squad` 指向指定 Squad，实际执行由该 Squad 的 leader agent 完成；
- 回调 Autopilot 自身的执行者仍是 Coordinator，这与解决单的目标 assignee 分开配置；
- 创建前校验目标 UUID 对应的对象仍存在且可指派；目标无效时阻断建单。

### 实际解决单创建时绑定（硬门槛）

新建实际解决单必须在创建请求中传入目标 assignee。`create_issue` 模式还必须同时传入运行根单：

```bash
multica issue create ... \
  --parent <runtime_issue_id> \
  --assignee-id <target_assignee>
```

`run_only` 模式没有 `runtime_issue_id`，使用以下直接根单命令：

```bash
multica issue create ... --assignee-id <target_assignee>
```

执行前先把 `target_assignee` 解析为 UUID，并检查最终创建命令确实包含 `--assignee-id <target_assignee>`；`create_issue` 模式还必须包含 `--parent <runtime_issue_id>`。创建接口无法携带这些参数时，停止创建并返回 `dispatch blocked`。

Autopilot 平台预创建的 Coordinator 运行根单是流程容器，不属于上述“默认归属 Coordinator 的实际解决单”。不能再创建一个无 `parent` 的 Coordinator 解决单，或先创建实际解决单再依赖后置指派完成正常派发。正常新建分支禁止调用 `multica issue assign`，也禁止用 `@名称`、评论 mention 或 `--no-start` 代替创建时绑定。目标校验失败或目标绑定结果不可确认时，停止创建并返回 `dispatch blocked`。

创建返回后立即回读 Issue，确认平台已记录目标 assignee；未通过回读时保留已创建 Issue，标记 `dispatch blocked`，不得报告“已派发”或“已触发执行”。

### 后置补偿

`issue assign` 只用于历史单据或创建接口异常后的补偿，不是正常新建路径。补偿分支必须有独立人工确认，不能由正常回调自动进入；补偿不得把 `runtime_issue_id` 当作实际解决单，也不得改变运行根单的 Coordinator 归属：

```bash
multica issue assign <solution_issue_id> --to-id <target_assignee>
```

补偿指派失败时保留解决单并返回 `dispatch blocked`，不得改派给其他 Agent 或伪造成功。已有活动解决单若实际 assignee 与配置目标不一致，不得静默改派，除非获得独立的人工确认。

不得把“目标路由：@<名称>”写入描述当作派发。描述中的路由文字最多只能作为补充信息。

## 派发回读与结果

指派后必须回读 Issue：

```bash
multica issue get <solution_issue_id> --output json
```

只有以下条件同时满足，才能报告“已派发”：

- `assignee_type` 等于配置的 `target_assignee_type`；
- `assignee_id` 精确等于配置的 `target_assignee`；
- Issue 仍存在且未被取消。
- `create_issue` 模式下，实际解决单的 `parent_issue_id` 等于 `runtime_issue_id`。

结果必须区分：

- `assigned`：平台 assignee 已回读匹配，但目标 Agent/Squad 尚未证明开始执行；
- `started`：存在目标执行记录，确认 Agent 已开始处理；
- `deferred`：平台明确返回目标当前忙碌、排队或延后；
- `blocked`：指派失败、回读不匹配、目标不存在或权限不足。

`assigned`、`started`、`deferred` 和 `blocked` 不得混写为“已触发执行”。对于 Squad，至少先确认 Issue 的平台 assignee 为该 Squad；leader 何时 claim 或开始执行，单独依据执行记录判断。

## 实际解决单

实际解决单负责 Sentry 事实、去重、证据、基线和整体状态。创建时直接绑定 callback 提供的 `target_assignee`；目标 Agent 或 Squad 接手后，自行决定后续分析、修复、验证和协作方式。

```bash
multica issue create ... \
  --parent <runtime_issue_id> \
  --assignee-id <target_assignee>
```

上例适用于 `create_issue` 模式；`run_only` 模式省略 `--parent`。创建后回读并确认父子关系（如适用）和平台 assignee 与目标一致。

目标 Agent 或 Squad 后续自行处理解决单。Coordinator 不修改代码、不自动合并、发布或关闭 Sentry Issue。
