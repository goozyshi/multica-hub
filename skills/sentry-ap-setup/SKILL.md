---
name: sentry-ap-setup
description: 引导用户配置业务 Sentry 巡检 Autopilot 与解决单 Autopilot，发现 workspace 中可复用的项目、Repo 和飞书群，生成方案并在确认后创建或复用远端配置。用户要求创建、配置或接入 Sentry 巡检自动化时使用。
disable-model-invocation: true
---

# Sentry Autopilot 配置引导

## 目标

把一次业务配置转换为两个可验证的 Multica Autopilot。业务差异只进入 Autopilot 描述和触发器配置，不创建新的业务 Skill：

1. 巡检 Autopilot：复用现有 `sentry-daily-top-issues` Skill，固定使用 `inspection_type: sentry-daily-top-issues`。
2. 解决单 Autopilot：复用现有 `sentry-resolution-order` Skill；优先复用兼容的解决单 Autopilot，没有兼容实例时新建引用同一 Skill 的解决单 Autopilot。

本 Skill 负责配置编排和资源确认，不执行 Sentry 查询结果分析、不发送测试消息、不创建业务解决单。用户确认后才允许远端写操作。

## 入口参数与范围

支持：

```text
/sentry-ap-setup <scope_hint>
```

例如 `/sentry-ap-setup soulstar`、`/sentry-ap-setup omigo`。`scope_hint` 用于缩小 workspace 资源发现范围，不是新的 Multica workspace，也不是 Sentry project 名称。

先读取 `multica project list --output json`，再按项目 `title`、`description`、slug 或已登记 Repo 名称进行大小写不敏感匹配：

- 只有一个匹配：将其 `project_id` 作为本次 scope，只展示该项目的 Repo 和相关 Autopilot。
- 没有匹配：返回 `needs-info`，列出可选项目名称，要求用户重新指定。
- 多个匹配：返回 `needs-info`，列出候选及 ID，要求用户选择。
- 没有 `scope_hint`：仅当 workspace 只有一个明确项目时自动使用；否则先询问 scope。

`scope_hint` 不得用于猜测 Sentry project、Repo、群组或目标 Agent。后续创建的巡检 Autopilot 仍必须使用用户确认的 Multica `project_id`。

## 默认值

以下是机械参数，不反复询问：

```text
source: search_issues
time_window: 24h
filter: is:unresolved level:error
sort: freq
每组 Top N: 3
display_top_n: 3
timezone: Asia/Shanghai
layout: global_top_n_markdown_v1
feishu_app_id: cli_aa1a82ab6d785cc2
feishu_profile: sentry-notify
sentry_org: mico
```

业务字段必须由用户确认并写入 Autopilot：业务名称、Multica project scope、Sentry project 与 Repo 的独立选择及映射、通知渠道、巡检频率、订阅者、解决单目标和是否启用解决单动作。`sentry_org` 固定为 `mico`，不向用户询问。Skill 只提供通用流程，不承载其他业务值。

## Phase 1：发现与收集

### 1. 读取 Multica workspace 资源

使用只读命令：

```bash
multica project list --output json
multica repo list --output json
multica autopilot list --output json
multica skill list --output json
```

有 `scope_hint` 时，先完成入口参数与范围的项目匹配，再只展示该 Multica project 的 Repo 和相关 Autopilot；`repo list` 返回 workspace 全量 Repo 时，按项目资源关联、Repo URL、描述和 scope 名称过滤。`autopilot list` 只保留绑定该 `project_id` 或描述明确包含该 scope 的候选。无法可靠过滤时，标记 `resource_discovery: partial`，要求用户选择，不假装已完成范围隔离。

完成条件：得到一个用户确认的 Multica `project_id`，并得到该 scope 下的 Repo 候选；未确认前不进入创建阶段。

### 2. 读取 Sentry project

`sentry_org` 固定为 `mico`。使用 `mico` organization 的只读 Sentry 查询能力获取该 organization 下的 project 列表。Sentry project 只从此列表产生，不从 Multica project、Repo 名称、slug 或描述推断。

展示 Sentry project 的名称和标识，要求用户独立选择。查询不可用、权限不足或结果为空时，返回 `needs-info` 或 `blocked`，不得猜测 Sentry project。

完成条件：每个巡检分组都有用户确认的 Sentry project；Sentry project 已确认属于 `mico`。

### 3. 发现飞书群

`feishu_app` 需要群名和 `oc_...` 格式 `chat_id`。优先检查环境中的 `lark-cli` 及其只读群组查询能力：

```bash
command -v lark-cli
lark-cli --help
```

固定复用已绑定的 Sentry 飞书应用，不接受调用方传入或覆盖应用 ID：`app_id=cli_aa1a82ab6d785cc2`，`profile=sentry-notify`。使用该 profile 的 Bot 身份枚举应用已加入的群聊；不得用当前用户身份代替应用身份：

```bash
lark-cli --profile sentry-notify im +chat-list --as bot --types group --page-all --format json
```

从返回的 `data.chats[]` 仅提取并展示 `name`（群名）和 `chat_id`（`oc_...` 群 ID），供用户选择并写入 `feishu_app.chat_id`。`chat_status` 非 `normal` 的群不作为可用目标。分页必须通过 `--page-all` 完成；该命令返回的是应用实际成员群，不是按名称搜索结果。查询不可用、应用未开通 Bot 能力、权限不足或结果为空时，要求用户提供 `chat_id`，并标记 `resource_discovery: partial` 或 `needs-info`，不得猜测群组。

禁止输出、读取或保存 App Secret、access token 或 Webhook；不得把应用 ID、profile 或群 ID 当作凭据回显到日志以外的敏感配置中。

完成条件：得到一个状态为 `normal` 的用户确认群组，或明确标记 `resource_discovery: partial` / `needs-info`。

### 4. 收集配置

使用以下表单向用户提问；已由默认值覆盖的字段不再提问：

```text
业务名称：
Multica project scope：
巡检频率/cron：
订阅者：

巡检配置：
### Sentry 查询
- sentry_org：mico（固定）
- source：
- time_window：
- filter：
- environment：
- sort：
### 项目分组
| 分组 | Sentry project（来自 mico） | Multica Repo | Top N |
| --- | --- | --- | --- |
### 展示配置
- layout：
- display_top_n：
- timezone：

解决单配置（business_resolution_config_v1）：
- resolution_enabled: true | false
### 解决单授权与目标（启用时）
- allowed_projects：
- target_assignee_type: agent | squad
- target_assignee：目标 Agent/Squad UUID

通知渠道：feishu_webhook | feishu_app
```

当 `feishu_webhook` 时补充：

```text
webhook_url：HTTPS URL
```

当 `feishu_app` 时，固定使用以下绑定，不向用户追加应用 ID/profile 参数；仅从查询结果选择目标群：

```text
app_id: cli_aa1a82ab6d785cc2
profile: sentry-notify
chat_id：oc_...
```

当 `resolution_enabled: true` 时，读取已有解决单 Autopilot 描述并收集缺失业务字段：

```text
target_assignee_type: agent | squad
target_assignee: 目标 Agent/Squad UUID
allowed_projects：
priority_mapping：
impact_trend_observation: enabled | disabled
observation_timeout_days：
post_fix_observation_days：
```

目标 UUID、权限和项目白名单属于业务决策，不使用默认值。解决单直接派发给该 Agent/Squad；不创建 Builder 子流程。

Sentry project 与 Multica Repo 是两个独立选择。若配置需要 project-repo 映射，必须逐项由用户确认；不能用名称相似度、slug 或已有描述自动补全。

## Phase 2：规范化与方案

### 配置校验

拒绝未知字段、缺失必填项、重复 Sentry project、空分组、未确认的 project-repo 映射、非正整数、非法枚举、无效 IANA 时区、非 HTTPS URL、非法 `chat_id` 和不一致的 Autopilot 引用。还要确认每个 Sentry project 属于 `mico`，每个 Multica Repo 属于已确认的 Multica scope。

发送配置必须匹配现有 `sentry-daily-top-issues` 规则：

- `feishu_webhook`：`transport=curl`、`msg_type=interactive`、`max_cards_per_run=1`、合法 HTTPS `webhook_url`。
- `feishu_app`：`transport=lark_cli`、`as=bot`、`msg_type=interactive`、`max_cards_per_run=1`、有效 `profile`、`oc_...` `chat_id`。

不要复制 Card JSON、解决单校验、幂等或派发细节；分别复用：

- [日报 Skill](../sentry-daily-top-issues/SKILL.md)
- [解决单 Skill](../sentry-resolution-order/SKILL.md)

两个 Autopilot 都只引用上述现有 Skill。业务名称、scope、项目分组、发送配置、解决单目标和流程开关全部写入对应 Autopilot；不得为单个业务复制、改写或新建 Sentry Skill。

### 解决单 Autopilot 复用判定

在创建前读取候选 Autopilot 的完整详情。只有以下字段全部兼容才复用：

- `profile_ref: skill:sentry-resolution-order`
- `execution_mode`
- Multica project scope
- Sentry organization 固定为 `mico`，以及 `allowed_projects`
- `target_assignee_type` 与 `target_assignee`
- 安全校验、去重键和趋势观测策略

不兼容时创建新的解决单 Autopilot；不得静默修改已有业务 Autopilot。`resolution_enabled: false` 时不创建也不绑定解决单 Autopilot。

### 方案展示

确认前展示完整方案：

```text
业务：
巡检 Autopilot：新建 / 目标 project / Inspector / create_issue / schedule / subscriber
profile_ref：skill:sentry-daily-top-issues
巡检配置：Sentry organization=mico + 已确认的 Sentry project + 独立确认的 Multica Repo 映射 + 展示配置
解决单配置：路由、授权、目标、趋势观测
发送配置：channel、profile/chat_id 或 webhook_url（Webhook 只显示已配置，不回显密钥）
解决单 Autopilot：复用 ID / 新建；直接派发目标类型与 UUID；趋势观测
```

只对业务字段要求明确确认。没有确认时返回 `needs-info`，不执行任何创建、更新、触发或发送命令。

## Phase 3：确认后创建

重新读取远端状态。若候选 Autopilot、Multica project、Repo、Sentry project、Skill 或群组发生变化，重新展示方案并再次确认。

### 创建巡检 Autopilot

始终新建一个业务实例：

```bash
multica autopilot create \
  --title "【<业务名称>】Sentry 每日 Top 巡检" \
  --description "<完整配置描述>" \
  --agent "Inspector" \
  --mode create_issue \
  --project "<project-id>" \
  --subscriber "<subscriber>"
```

描述必须包含：

```text
inspection_type: sentry-daily-top-issues
profile_mode: skill-backed
profile_ref: skill:sentry-daily-top-issues
scope_project: <业务 scope>
```

然后创建用户确认的 schedule：

```bash
multica autopilot trigger-add <autopilot-id> \
  --kind schedule \
  --cron "<cron>" \
  --timezone "<iana-timezone>"
```

### 复用或创建解决单 Autopilot

- 复用：保存现有 ID，不更新其配置。
- 新建：使用 `profile_ref: skill:sentry-resolution-order`、当前业务 scope、用户确认的目标和 `--mode create_issue`。
- 解决单 Autopilot 使用 webhook trigger；不要把飞书 Webhook 或 App Secret 写入描述。
- 创建失败时停止后续操作，报告已完成与未完成项；不自动回滚已成功创建的 Autopilot。

## Phase 4：回读验证

对每个受影响 Autopilot 执行：

```bash
multica autopilot get <autopilot-id> --output json
```

验证 `status`、`assignee`、`execution_mode`、`project_id`、`profile_ref`、触发器、cron、timezone 和 subscriber。验证 Skill 引用：

```bash
multica skill list --output json
```

若 `profile_ref` 指向不存在或名称不一致的 Skill，或 Sentry project 不属于 `mico`，结果为 `blocked`，不得报告配置完成。

## 结果包

成功时输出：

```text
result: executed
inspection_autopilot_id:
resolution_autopilot_id:
sentry_org: mico
resolution_action: reused | created | skipped
scope_project:
inspection_trigger:
resolution_trigger:
subscriber:
resource_discovery:
verification:
remaining_decisions:
```

配置不完整返回 `needs-info`。远端创建、目标绑定、权限或回读失败返回 `blocked`。不得把“Autopilot 已创建”报告为“巡检已运行”或“解决单已派发”。

## 边界

- 不修改现有 `sentry-daily-top-issues` 或 `sentry-resolution-order` 内容。
- 不创建业务解决单，不触发巡检，不发送飞书测试消息。
- 不修改业务代码、Repo、分支、MR 或 Sentry Issue。
- 不回显凭据、Webhook、IP、用户标识或完整堆栈。
