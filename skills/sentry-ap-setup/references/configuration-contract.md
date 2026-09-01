# 配置契约 Reference

仅在收集字段、生成 Autopilot 描述或处理发送分支时读取。下游解析规则以
`sentry-daily-top-issues` Skill 为最终事实源，机器引用为 `skill:sentry-daily-top-issues`。

## 机械默认值

以下值由 Skill 直接使用，不重复询问：

```text
source: search_issues
time_window: 24h
filter: is:unresolved level:error
sort: freq
business_name: <scope-title> Sentry 巡检
cron: 0 10 * * *
per_group_top_n: 3
display_top_n: 3
timezone: Asia/Shanghai
layout: global_top_n_markdown_v1
sentry_org: mico
subscriber: current_creator
priority_mapping: high=P1;medium=P2;low=P3
impact_trend_observation: enabled
observation_timeout_days: 7
post_fix_observation_days: 3
dedupe_key: project:issue_id
feishu_app_id: cli_aa1a82ab6d785cc2
feishu_profile: sentry-notify
```

这些是机械参数，不是项目、Repo、群组、解决单目标或权限决策。
`subscriber` 自动使用当前创建人，不作为用户选择项。
业务名称自动使用 `<scope-title> Sentry 巡检`，执行时间默认每天 10:00，均不作为首轮
提问项。风险优先级、影响观察开关和观察时长使用上述默认值，用户后续可直接修改
Autopilot。
`dedupe_key` 不是用户输入项。启用解决单时固定写入 `project:issue_id` 作为运行时模板，
每个 callback 必须将其展开为实际的 `<project>:<issue_id>`；不得使用固定 Issue ID 或按
业务名称自造去重键。
Sentry 环境的默认业务语义是“生产环境”，不直接把 `production` 写入查询字段；实际字段
必须使用每个项目已核验的原始环境名称。

字段完整性分为三类：业务名称、执行时间、Top N、timezone、subscriber、风险优先级、
影响观察参数和 `dedupe_key` 必须由系统默认补全；Sentry project、Multica 项目、通知方式、
Webhook 地址或应用群、解决单开关、允许创建的项目和 Agent/Squad 目标必须由用户确认；
环境、资源 ID、Skill 引用和权限状态必须由系统读取核验。三类字段任一缺失，都不得创建
Autopilot。

## 面向用户的提问

用户问题使用业务语言；以下内部字段只用于答案规范化，不能单独展示给用户。
本流程同时使用两个项目系统，优先确认 Sentry 主错误来源：

- `Sentry project`：实际查询错误的主项目；organization 固定为 `mico`。
- `Multica 项目`：巡检 Autopilot 的归属范围，决定可用 Repo 和 workspace 资源。
  两者不能按名称自动推断对应关系。

以下是用户名称与内部字段的映射：

| 用户看到的名称 | 内部配置含义 |
| --- | --- |
| Multica 项目（巡检归属） | Multica `project_id`，决定 Repo 和 Autopilot 资源范围 |
| Sentry project（错误来源） | `mico` organization 下实际要巡检的 Sentry 项目 |
| 执行时间 | `cron`，默认每天 10:00；用户后续可直接修改 Autopilot |
| Multica 订阅人 | `subscriber`，自动使用当前创建人，接收 Autopilot 运行单或状态通知 |
| 飞书通知目标 | Webhook 地址对应的固定群，或自建应用选择的目标群 |
| Sentry 错误环境 | `environment`，默认生产环境；按每个项目实际名称使用 `Prod`、`prod` 或 `Production` 等精确值 |
| 每组最多展示 | `Top N`，每个 Sentry 项目取多少条错误 |
| 最终展示条数 | `display_top_n`，所有分组汇总后最终展示多少条 |
| 是否提供创建解决单按钮 | `resolution_enabled` |
| 允许创建解决单的项目 | `allowed_projects` |
| 解决单处理目标类型 | `target_assignee_type`，指定单个 Agent 或小队 |
| 解决单处理目标 | `target_assignee`，指定 Agent 或小队的平台唯一 ID |
| 风险等级对应优先级 | `priority_mapping`，默认高风险 P1、中风险 P2、低风险 P3 |
| 修复后影响观察 | `impact_trend_observation`，默认开启 |
| 观察时长 | `observation_timeout_days` 默认 7 天；`post_fix_observation_days` 默认 3 天 |

### 通知方式说明

在第 1 轮先展示这张对比表，再让用户选择：

| 通知方式 | 它是什么 | 适合场景 | 用户需要准备 |
| --- | --- | --- | --- |
| 飞书机器人地址（Webhook） | 只读卡片：查看错误摘要、次数、影响用户、初判、建议和 Sentry 链接；不能从卡片操作或联动 Multica 创建解决单 | 只需要查看巡检结果 | 下一轮提供 HTTPS 机器人地址 |
| 飞书自建应用 | 可交互卡片：配置巡检单链接后，点击“查看巡检单”跳转 Multica；开启解决单后，点击“创建解决单”联动通用解决单流程 | 需要查看 Multica 巡检单或发起解决单 | 下一轮选择应用已加入的目标群 |

选择后的行为：

- 机器人地址方式通过 `curl` 发送只读卡片，用户可查看错误摘要、指标、初判、建议和
  Sentry 链接；不查询飞书群，也不提供卡片操作或联动 Multica 创建解决单。
- 自建应用方式通过已绑定的 `sentry-notify` profile 以 Bot 身份发送可交互卡片，配置巡检
  单链接后，用户可点击“查看巡检单”跳转 Multica；开启解决单后，点击“创建解决单”
  即可联动通用解决单流程。
  只展示应用已加入且状态正常的群，不展示或询问 App Secret。
- 选择通知方式后，另一种方式的字段、资源查询和候选全部不出现。
- 从 Webhook 切换为飞书自建应用并开启解决单时，视为一次完整分支切换：重新生成发送
  配置和解决单配置，补齐应用群、授权目标与 `dedupe_key`，不得只修改 `channel` 后直接
  保存。

### 入口资源结果

第 1 轮之前应先完整拉取（含全部分页）并独立检查 `mico` Sentry project 和 Multica
project。Sentry 仅按 `scope_hint` 与 project `name`、slug 做本地匹配，不从 Multica
项目或 Repo 推断。两套结果必须在同一张入口候选卡中分区显示：

| 资源类型 | 显示内容 | 用户要确认什么 |
| --- | --- | --- |
| Sentry project（主错误来源） | project 名称、错误来源、可跳转链接、候选状态 | 点击链接查看项目，并先确认本次要使用的候选 |
| Multica 项目（Autopilot 归属） | 项目名称、用途、可跳转链接、候选状态 | 点击链接查看项目，并确认巡检 Autopilot 的归属项目 |

Sentry 精确命中时显示“`mico` 中已找到候选”；近似命中时显示“`mico` 中可能匹配”，
未命中时显示“`mico` 中没有匹配候选”并列出可选 project。两者分开确认，不能把 Multica
项目名称直接当作 Sentry project。匹配优先级和标准化规则见
[资源发现 Reference](resource-discovery.md)。
首条回复必须先呈现 Sentry 主候选，再呈现 Multica 归属候选；即使 Multica 候选已唯一
确认，也不改变 Sentry 优先顺序，不等待用户追问“Sentry project 呢”。
候选进入提问卡片前必须通过 [资源发现 Reference](resource-discovery.md) 的“链接交付
检查”；候选展示必须同时有名称、完整地址和可点击链接，不能把用户输入直接拼接为跳转
地址，也不能只输出候选名称。Sentry 候选只要已从 `mico` 列表验证 slug，就直接生成
Sentry 项目入口，不额外请求项目详情。

### 第 1 轮：基础设置

一次询问：

| 要确认的设置 | 用户需要理解什么 | 回复方式 |
| --- | --- | --- |
| Sentry project（主错误来源） | 确认本次创建 Sentry Autopilot 要巡检的错误项目 | 从 `mico` 候选中选择一个或多个 |
| Multica 项目（巡检归属） | 使用哪个 Multica 项目和代码资源 | 从候选中确认项目 |
| 通知方式 | 选择上方一种飞书发送方式 | 选择“机器人地址”或“自建应用” |

第 1 轮按 Sentry 优先顺序确认主错误来源、Multica 归属和通知方式。业务名称默认使用
“<Multica 项目名称> Sentry 巡检”，执行时间默认每天 10:00，Multica 订阅人自动使用
当前创建人；这些设置不提问，
也不与飞书通知群混淆。第 1 轮结束前不查询飞书群，不询问机器人地址、群组、是否提供
解决单按钮、Repo 或解决单字段。

### 第 2 轮：候选已固定的设置

基础资源和已选分支资源发现完成后，一次询问：

| 设置 | 用户需要理解什么 | 本轮动作 |
| --- | --- | --- |
| Sentry 错误环境 | 默认生产环境；确认分组后按每个已选项目的实际环境名称查询；只有明确要求时才查询全部环境 | 自动核验，不需填写 |
| 巡检分组 | 每个业务分组对应哪个 Sentry 项目和代码仓库 | 逐项选择并确认 |
| 每组最多展示 | 每个 Sentry 项目取多少条错误；默认 3 条 | 使用默认值，无需填写 |
| 通知设置 | 根据上一轮选择，填写机器人地址或选择通知群 | 选定渠道后必须填写或选择 |
| 是否提供创建解决单按钮 | 仅自建应用卡片可跳转 Multica 并发起解决单；选择“开启”或“关闭” | 仅自建应用确认 |

Webhook 固定为只读卡片，不显示或询问创建解决单按钮；自建应用才显示该项，并允许开启
跳转 Multica 和创建解决单动作。`feishu_webhook` 和 `feishu_app` 只出现其中一个分支。
发送配置中的 `msg_type=interactive` 只是飞书卡片封装格式，不表示 Webhook 卡片包含可交互
动作。

### 生产环境值

第 2 轮确认 Sentry project 后，读取本 Skill 的
`references/sentry-environment.md`。该 Reference 是环境读取、MCP 能力探测、精确大小写
保留、默认环境 fallback 和失败状态的唯一规则源；本文件不重复实现细节。

### 第 3 轮：解决单设置

仅当通知方式为自建应用且第 2 轮选择开启解决单按钮时，一次询问：

| 要确认的设置 | 用户需要理解什么 | 回复方式 |
| --- | --- | --- |
| 允许创建解决单的项目 | 哪些 Sentry 项目允许发起解决单 | 从已验证项目中选择 |
| 解决单处理目标类型 | 指定单个 Agent 或小队 | 选择 Agent（单个 Agent）或 Squad（小队） |

`允许创建解决单的项目` 只能从已验证的 `mico` Sentry 项目中选择。Sentry 项目与代码
仓库必须独立选择并逐项确认，不能按名称相似度自动映射。风险等级优先级默认高风险
P1、中风险 P2、低风险 P3；修复后影响观察默认开启，最多观察 7 天，修复后继续观察 3
天。以上默认值不在本轮提问，用户后续可直接修改 Autopilot。

### 第 4 轮：选择解决单处理目标

第 3 轮答案确定后再询问：

| 前置选择 | 追加设置 |
| --- | --- |
| 处理目标类型已确定 | 从已读取的 Agent 或 Squad 候选中选择名称和用途；系统自动写入平台唯一 ID |

因此不得要求用户输入或记忆目标 UUID。观察开关和观察时长使用默认值，不再追加条件问题。

目标权限和项目白名单没有默认值。目标直接写入巡检配置，并在生成 Card callback 时原样
传给解决单 Autopilot；不把目标写成解决单 Autopilot 的默认配置。

## 询问卡片格式

用户问题使用中文分段标题和 Markdown 表格。项目分组使用以下可读表头：

```text
| 业务分组 | Sentry 项目（错误来源） | 代码仓库 | 每组最多展示 |
| --- | --- | --- | --- |
```

候选、映射和待确认值必须落在对应表格。表格无法渲染时，使用每行一个字段的结构化
格式；不用连续编号列表、裸字段清单或未对齐的伪表格。

## Autopilot 描述分区

巡检 Autopilot 的 `description` 必须包含固定系统字段和以下规范分区。该段只用于生成
机器配置，不直接展示给用户。字段使用
`- key: value`，项目分组只使用三列表格；未知区块和字段会被日报 Skill 拒绝。

```text
## 基本信息
- business_name: <业务名称>
- scope_project: <Multica project scope>
- inspection_type: sentry-daily-top-issues
- profile_mode: skill-backed
- profile_ref: skill:sentry-daily-top-issues

## 巡检配置
- sentry_org: mico
- source: search_issues
- time_window: 24h
- filter: is:unresolved level:error
- environment: <environment>
- sort: freq

### 项目分组
| 分组 | 项目 | Top N |
| --- | --- | --- |
| <group> | <verified-sentry-project> | <positive-integer> |

- display_top_n: 3
- layout: global_top_n_markdown_v1
- timezone: Asia/Shanghai

## 解决单配置（business_resolution_config_v1）
- resolution_enabled: <true-or-false>
- resolution_autopilot: <generic-autopilot-id>
- allowed_projects: <verified-projects>
- dedupe_key: project:issue_id
- target_assignee_type: <agent-or-squad>
- target_assignee: <uuid>
- priority_mapping: <confirmed-mapping>
- impact_trend_observation: <enabled-or-disabled>
- observation_timeout_days: <positive-integer>
- post_fix_observation_days: <positive-integer>

## 发送配置
- channel: <feishu_webhook-or-feishu_app>
- transport: <curl-or-lark_cli>
- msg_type: interactive
- max_cards_per_run: 1
- profile: sentry-notify
- as: bot
- chat_id: <normal-oc-id>
- webhook_url: <confirmed-https-url>
```

`environment` 占位符替换为已核验的实际名称，例如 `Prod`；“生产环境”只表示用户侧
默认语义。多个 project 的实际名称可以不同，查询时按 project 使用各自的原始值，不把
`prod`、`Prod`、`Production` 拼成一个值或仅按大小写合并。

按实际分支省略不适用字段：Webhook 不写 `profile`、`as`、`chat_id`；App 不写
`webhook_url`。`resolution_enabled=false` 时不绑定 `resolution_autopilot`，不写业务目标
或观测字段或 `dedupe_key`。`resolution_enabled=true` 时必须写入
`dedupe_key: project:issue_id`，它由系统默认生成，不进入用户提问。Webhook URL 不能出现在
方案或日志中。

解决单 callback 的完整字段、Card JSON、按钮状态和发送流程，按需读取日报 Skill 的
`feishu-card-delivery` Reference，以及解决单 Skill 的 `resolution-creation-and-dispatch`
Reference。本 Reference 不复制跨 Skill 实现细节。
