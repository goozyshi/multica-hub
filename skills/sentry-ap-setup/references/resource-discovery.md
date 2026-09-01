# 资源发现 Reference

仅在 `sentry-ap-setup` 进入对应阶段时读取。本 Reference 定义发现时机、只读命令、过滤和
发现状态。它不授权任何远端写操作。

## 发现时机

发现遵循依赖顺序：

1. 第 1 轮之前先完整读取 `mico` Sentry project 列表，再完整读取 Multica project 列表，
   用于生成两套独立候选；Sentry 候选是主错误来源。
2. 第 1 轮确认 scope 和通知渠道后，读取基础资源；复用第 1 步已取得的 `mico` Sentry
   project 列表。
3. 第 2 轮确认 Sentry project 后，读取每个已选 project 的环境元数据。
4. 仅当通知渠道为 `feishu_app` 且用户在后续轮次开启解决单时，读取所有可用 Agent、
   Squad 和解决单 Autopilot 候选。
5. 仅当通知渠道为 `feishu_app` 时，读取飞书群。

未启用的分支不查询、不展示候选、不询问分支字段。

## Multica project scope（Autopilot 归属）

使用：

```bash
multica project list --output json
```

按 `title`、`description`、slug 和已登记 Repo 名称对 `scope_hint` 做大小写不敏感匹配。
匹配只产生候选，不替代用户确认。

- 一个候选：第 1 轮展示名称和可点击链接，要求确认；`project_id` 只保留为系统绑定值。
- 多个候选：第 1 轮要求选择名称和可点击链接，不要求用户手填 `project_id`。
- 没有匹配候选：第 1 轮列出可选项目并要求选择；未选择时该轮返回 `needs-info`。
- 没有 `scope_hint`：唯一明确项目也作为待确认候选；多个项目要求选择。

`scope_hint` 可以作为 Sentry project 的主搜索提示，用于优先检查 `mico` 中是否存在同名
或相近候选；它不参与跨系统推断，也不能自动选择 Sentry project、Repo、飞书群或
Agent/Squad。Multica 候选较多时，仍先确认 Sentry 主候选，再确认 Multica 归属。

面向用户展示候选时，先显示中文项目名称和“用途/归属范围”，再以次要信息显示项目 ID。
不要把原始 JSON、英文状态值或内部字段名作为首屏内容；需要展示状态时使用中文，例如
“进行中”“已暂停”。

## 候选跳转链接

候选进入用户确认卡片前，必须完成“链接交付检查”。链接不是可选的展示增强，而是候选
输出的固定字段；链接只用于用户快速查看和确认，不替代用户选择，也不参与跨系统资源
匹配。

### 标识保留

```text
Multica project record:
- name/title
- project_id

Sentry project record:
- name
- slug
```

匹配、排序和展示过程中不得丢弃 `slug`。Sentry 的 slug 是用户入口和项目确认所需的
唯一标识；候选缺少 slug 时，先重新读取来源列表并重新标准化一次；仍缺失时标记
`resource_discovery: partial`，明确显示“链接未生成：缺少 slug”，不得猜测 ID 或 URL。

### URL 构造

对每条候选使用其自身标识构造完整地址：

```text
Multica project:
https://multica.micoplatform.com/mico-fe/projects/<project-id>

Sentry project:
https://sentry.eventbus.me/organizations/mico/insights/projects/<project-slug>
```

- Multica 地址必须使用该项目自身的 `project_id`；Sentry 地址只使用该项目自身的
  `slug`，不能跨系统混用标识。
- 路径段和查询参数按 URL 规则编码；`mico` 固定写入 Sentry organization 路径。
- 生成后检查 URL 中不再含 `<project-id>` 或 `<project-slug>` 等占位符，且地址指向
  候选自身的 slug。

### 用户输出门禁

每一条展示给用户的候选必须同时包含：

1. 人类可读名称；
2. 完整可见 URL；
3. 同一个 URL 的 Markdown 可点击链接。

固定输出格式：

```text
- Multica 项目： [Omigo-Repo](https://multica.micoplatform.com/mico-fe/projects/<project-id>) · 地址：https://multica.micoplatform.com/mico-fe/projects/<project-id>
- Sentry project： [omigo-h5](https://sentry.eventbus.me/organizations/mico/insights/projects/<project-slug>) · 地址：https://sentry.eventbus.me/organizations/mico/insights/projects/<project-slug>
```

实际输出必须替换所有占位符；不得只输出候选名、代码样式名称或隐藏 URL 的纯文本标签。
链接交付检查未通过时，先修复候选数据或返回 `resource_discovery: partial`，不得进入
“请确认项目”的提问。slug 已验证时，Sentry 项目链接即视为链接交付检查通过。

## 基础资源

Multica scope 确认后读取：

```bash
multica repo list --output json
multica autopilot list --output json
multica skill list --output json
```

过滤规则：

- Repo 只保留可确认属于目标 `project_id` 的资源。依据项目资源关联、Repo URL、描述和
  scope 名称过滤。
- Autopilot 只保留绑定目标 `project_id`，或描述明确包含该 scope 的候选。
- Skill 列表必须包含：
  `sentry-daily-top-issues` 和 `sentry-resolution-order`。
- 过滤无法可靠完成时标记 `resource_discovery: partial`，展示候选并要求用户逐项选择；
  不把全量 workspace 资源当成 scope 内资源。

展示 Repo 和 Autopilot 时，优先使用名称、用途、归属和中文状态；URL、UUID 和内部状态值
只作为确认所需的辅助信息。

## Sentry project（主错误来源）

使用 `mico` organization 的只读 Sentry 查询能力获取完整 project 列表，包含全部分页结果；
不要只按用户输入调用名称搜索。Sentry project 只能从该列表选择，并逐项展示名称和按模板
生成的可跳转链接；slug 作为链接和项目确认标识。

- 即使使用 `scope_hint` 独立搜索 Sentry project，也只生成候选和“是否找到”的结果；
  最终仍由用户按分组确认。
- 对 `scope_hint` 和每个 Sentry project 的 `name`、`slug` 做确定性标准化：去除首尾空格、
  转为小写，将空格、连字符和下划线统一为分隔符。
- 匹配优先级固定为：原始名称或 slug 大小写不敏感精确匹配；标准化后精确匹配；名称或
  slug 包含全部输入词的可能匹配；无匹配。
- 精确匹配也只标记“已找到候选”，可能匹配标记“可能匹配”；任何匹配都不能替代用户
  按分组确认。
- 不从 Multica project、Repo 名称、slug 或描述推断 Sentry project。
- 每个巡检分组必须使用用户确认且已在 `mico` 列表验证的 project。
- 查询不可用、权限不足或返回为空时，返回 `needs-info` 或 `blocked`，不得继续创建方案。

`sentry_org` 固定为 `mico`，不向用户询问。

### 入口候选卡

第 1 轮之前必须把两套独立匹配结果按 Sentry 优先顺序合并到同一张“入口候选卡”：

1. `mico Sentry project（主错误来源）`：展示匹配状态、候选名称、slug 和可点击链接；
2. `Multica 项目（Autopilot 归属）`：展示匹配状态、用途、候选名称和可点击链接。

两套结果都必须出现。某一套没有匹配时，仍在同一张卡片中显示“没有匹配”，并列出可选
候选；不得先发送只有 Multica 项目的回复，再等待用户追问 Sentry project。入口卡展示
完成后，才发送第 1 轮的 Sentry 主候选、Multica 归属和通知方式问题。Multica 候选
较多时，不得让其选择阻塞 Sentry 候选展示或确认。

## Sentry 生产环境

第 2 轮确认 Sentry project 后，读取本 Skill 的
`references/sentry-environment.md`，按该 Reference 完成环境能力探测、只读查询、结果归一化
和失败处理。这里仅定义读取时机；环境名称、MCP 调用参数和状态契约以该 Reference 为准。

## Agent 和 Squad 候选

只有通知方式为 `feishu_app` 且用户开启解决单时执行：

```bash
multica agent list --output json
multica squad list --output json
```

命令返回 workspace 中可用的 Agent 和 Squad；Agent 默认不包含 archived 项。展示名称、
用途或简介，平台唯一 ID 只作为隐藏绑定值或必要时的辅助信息。用户先在第 3 轮确认
“单个 Agent”或“小队”，再在第 4 轮从对应候选中选择名称；系统自动写入对应 ID，不要求
用户输入或记忆 UUID。

列表读取失败、结果为空或目标不可用时返回 `needs-info` 或 `blocked`，不得使用昵称、历史
描述或猜测的 UUID 代替候选。

## 飞书群

只有 `notification_channel=feishu_app` 时执行：

```bash
command -v lark-cli
lark-cli --help
lark-cli --profile sentry-notify im +chat-list \
  --as bot \
  --types group \
  --page-all \
  --format json
```

固定绑定：

```text
app_id: cli_aa1a82ab6d785cc2
profile: sentry-notify
```

使用该 profile 的 Bot 身份枚举应用实际加入的群，不使用当前用户身份。必须通过
`--page-all` 获取完整分页结果。从 `data.chats[]` 只提取：

- `name`
- `chat_id`，且格式为 `oc_...`

只展示 `chat_status=normal` 的群。群聊结果是应用成员列表，不是按名称搜索结果。
用户确认群后才写入 `feishu_app.chat_id`。

如果命令不可用、Bot 能力未开通、权限不足或结果为空：

- 要求用户提供待验证的 `oc_...` `chat_id`；
- 标记 `resource_discovery: partial` 或 `needs-info`；
- 不猜测群名、群 ID 或应用身份。

`feishu_webhook` 分支禁止执行上述群聊查询。该分支只收集并校验用户提供的 HTTPS
`webhook_url`。

## 解决单 Autopilot 候选

只有通知方式为 `feishu_app` 且用户确认开启解决单时，才从 Autopilot 列表筛选候选，并对
每个候选读取完整详情：

```bash
multica autopilot get <autopilot-id> --output json
```

候选详情供 [校验与复用 Reference](validation-and-reuse.md) 判断。不能因为存在名称相似、
scope 相同或旧描述就直接复用。

## 状态定义

- `resource_discovery: complete`：所需列表已取得，关联和归属可验证。
- `resource_discovery: partial`：列表部分可用，仍可在用户提供明确标识后继续验证。
- `needs-info`：缺少用户选择、输入或可验证的资源标识。
- `blocked`：权限、工具或远端读取失败，无法安全验证。

任何状态都不允许绕过用户确认或把未验证资源写入 Autopilot。

## 凭据边界

不得输出、读取或保存 App Secret、access token、Webhook 内容或其他凭据。应用 ID、profile
和用户确认的群 ID 是配置标识，不是凭据；Webhook 在方案中只显示“已配置”，不回显完整 URL。
