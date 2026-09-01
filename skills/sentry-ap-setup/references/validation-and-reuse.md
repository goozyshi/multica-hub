# 校验与复用 Reference

仅在配置收集完成后读取。这里负责把用户输入变成可执行方案，不执行远端写操作。

## 字段校验

拒绝以下任一情况，并返回字段级错误及 `needs-info`：

- 未知字段、未知区块、缺失必填项、空项目分组或重复 Sentry project。
- Sentry project 不属于 `mico`，或没有来自 `mico` 列表的独立用户确认。
- Sentry project 缺少已从 `mico` 列表验证的 `slug`，或候选链接不是由该 project 自身的
  `slug` 生成。
- Multica Repo 不属于确认的 `project_id`，或 project-repo 映射未逐项确认。
- 非正整数、非法枚举、无效 IANA timezone 或无法解析的 cron。
- `target_assignee_type` 不是 `agent` 或 `squad`，或 `target_assignee` 不是对应目标的
  UUID。
- `target_assignee` 不来自当前 workspace 的 `multica agent list` 或 `multica squad list`
  候选，或候选已不可用。
- `allowed_projects` 包含未验证的 Sentry project。
- `resolution_enabled=true` 时缺失 `dedupe_key`，或其值不是系统默认模板
  `project:issue_id`。该字段不向用户提问，必须在生成 Autopilot 描述时自动补齐。
- `feishu_app` 的 `chat_id` 不是已确认的 `normal` 群或不符合 `oc_...` 格式。
- `feishu_webhook` 的 `webhook_url` 不是 HTTPS URL。
- `feishu_webhook` 仍启用了解决单动作或携带解决单 callback 配置。
- `subscriber` 不是当前创建人的平台身份。
- 生产环境值未按 `sentry-environment.md` 为每个 Sentry project 得到 `resolved`，或把
  `prod`、`Prod`、`Production` 仅按大小写合并成一个查询值。
- 分支字段与通知渠道、`resolution_enabled` 状态不一致。

`sentry_org` 只能是固定值 `mico`。不使用名称相似度、slug、描述或旧 Autopilot 描述
自动补齐用户未确认的业务值。

## Autopilot 创建前强校验

生成或修改巡检 Autopilot 描述后，必须先运行仓库内的
`scripts/validate_autopilot_description.py`：

```bash
python3 skills/sentry-ap-setup/scripts/validate_autopilot_description.py \
  --description-file /tmp/sentry-ap-setup/inspection-description.md \
  --title "【Omigo H5】Sentry 巡检" \
  --agent "Inspector" \
  --mode create_issue \
  --project-id <confirmed-project-id> \
  --subscriber <current-creator> \
  --cron "0 10 * * *" \
  --timezone Asia/Shanghai \
  --output json
```

只有返回 `status: valid` 且 `decision: ready-to-create` 才允许进入人工方案确认后的远端
写入。脚本至少校验四个配置分区、必填字段、分支一致性、`profile_ref`、Sentry
organization、项目分组、URL、IANA timezone，以及启用解决单时的
`dedupe_key: project:issue_id`。脚本不得只校验通知字段后放行，也不得以“后续 callback
再补齐”为理由跳过缺失字段。缺失的默认字段必须先由规范化步骤补全；缺失的用户确认
字段必须返回 `needs-info` 并回到对应提问轮次；同时校验创建命令的标题、Agent、模式、
Multica project、subscriber、cron 和 timezone。任何一种缺失都不能创建 Autopilot。

## 发送配置矩阵

发送配置必须与已确认渠道完全匹配：

| channel | 必填配置 |
| --- | --- |
| `feishu_webhook` | `transport=curl`、只读卡片（查看错误摘要、指标、初判、建议和 Sentry 链接，不联动 Multica 创建解决单）、`resolution_enabled=false`、`msg_type=interactive`、`max_cards_per_run=1`、HTTPS `webhook_url` |
| `feishu_app` | `transport=lark_cli`、可交互卡片（配置巡检单链接后可点击“查看巡检单”跳转 Multica；开启后可点击“创建解决单”联动通用解决单流程）、`as=bot`、`msg_type=interactive`、`max_cards_per_run=1`、`profile=sentry-notify`、`oc_... chat_id` |

这里的 `msg_type=interactive` 是飞书卡片消息的封装类型；Webhook 分支仍然只读，不因该
字段获得解决单按钮或其他交互动作。

固定 App 绑定为 `app_id=cli_aa1a82ab6d785cc2`、`profile=sentry-notify`。调用方不能
覆盖。App Secret 只保存在 profile 中，不写入 Autopilot 描述、Issue、卡片、方案或日志。
方案只显示“已配置”，不回显 Webhook URL。

## 下游配置一致性

巡检 Autopilot 必须引用：

```text
inspection_type: sentry-daily-top-issues
profile_mode: skill-backed
profile_ref: skill:sentry-daily-top-issues
```

解决单 Autopilot 必须引用：

```text
profile_ref: skill:sentry-resolution-order
```

两者都只能引用仓库中存在且名称一致的 Skill。巡检配置中的
`layout=global_top_n_markdown_v1`、`display_top_n`、项目分组列和发送字段必须符合
`sentry-daily-top-issues` Skill。仅在 `resolution_enabled=true` 时，解决单目标、版本和
callback 字段必须符合 `sentry-resolution-order` Skill 及其 Reference。

不要把 Card JSON、解决单幂等、验签或派发实现复制到方案描述；只写下游 Skill 能解析的
配置字段。

## 解决单 Autopilot 复用

只在通知方式为自建应用且 `resolution_enabled=true` 时判断复用。创建前必须读取每个候选的完整详情。候选
同时满足以下条件才可复用：

- `profile_ref` 精确等于 `skill:sentry-resolution-order`。
- `execution_mode` 与本次需要的模式一致；当前新建规则为 `create_issue`。
- 存在可用的通用 webhook trigger。
- 能接收并校验通用 callback，包括 `resolution_autopilot`、目标类型、目标 UUID 和
  `resolution_config_version=business_resolution_config_v1`。

Multica project scope 不是兼容条件。候选的项目范围或业务描述不同，不影响上述兼容
判定；但不能因此静默修改现有实例。

判定结果只能是：

- 兼容：复用现有 ID，不更新配置。
- 不兼容或不存在：先确认 workspace 是否已有其他通用路由候选；确认没有兼容通用路由
  后，才一次性初始化一个通用解决单 Autopilot，不按业务创建实例。
- `resolution_enabled=false`：跳过，不读取、不创建、不绑定。

新建的解决单 Autopilot 不绑定业务项目、业务目标或固定 Agent/Squad；业务目标只存在于
巡检 Autopilot 配置，并在卡片 callback 中传递。不要创建 Builder 子流程。

## 方案展示

确认前展示完整、面向用户的方案。先展示中文含义，再在必要处给出系统动作：

```text
业务方案
| 配置项 | 当前设置 |
| --- | --- |
| 业务名称 | <Multica 项目名称> Sentry 巡检（默认） |
| 巡检归属项目 | <Multica 项目名称>（<project-id>） |
| 巡检 Autopilot | 新建 |
| 通用解决单路由 | 复用 <路由名称> / 首次初始化 / 不启用 |

巡检范围
| 业务分组 | Sentry 项目（错误来源） | 代码仓库 | 每组最多展示 |
| --- | --- | --- | --- |
| <分组> | <已验证项目> | <已验证仓库> | <n> 条 |

执行与通知
| 配置项 | 当前设置 |
| --- | --- |
| 执行时间 | 每天 10:00（默认，系统已自动转换执行计划） |
| Multica 订阅人 | 当前创建人（自动接收 Autopilot 运行单或状态通知） |
| Sentry 错误环境 | 生产环境（按项目使用已核验的 `prod` / `Prod` / `Production`） / 用户明确选择的全部环境 |
| 通知方式 | 飞书机器人地址（只读查看，不联动 Multica 创建解决单） / 飞书自建应用（配置链接后可查看巡检单、跳转 Multica，并按配置创建解决单） |
| 通知目标 | 已配置（Webhook 不回显地址） / <正常群名> |

解决单
| 配置项 | 当前设置 |
| --- | --- |
| 创建解决单按钮 | 开启 / 关闭 / 不适用（只读卡片） |
| 允许创建解决单的项目 | <项目名称> |
| 处理目标 | 单个 Agent / 小队：<目标名称>（平台标识已核验） |
| 风险等级对应优先级 | 高风险 P1 / 中风险 P2 / 低风险 P3（默认） |
| 修复后影响观察 | 开启（默认） |
| 最多观察天数 | 7 天（默认，后续可修改 Autopilot） |
| 修复后继续观察天数 | 3 天（默认，后续可修改 Autopilot） |
```

不要把 `cron`、`subscriber`、`environment`、`resolution_enabled`、
`target_assignee_type` 等内部键作为用户首屏标题。候选、映射、分支状态和待确认值必须
进入表格。没有 Sentry project 验证结果或验证失败时，只展示中文阻塞原因，不展示“已完成
资源发现”方案。

方案中所有业务字段都获得明确确认后，才可进入执行 Phase。确认只授权当前方案，不授权
后续未展示的配置或其他 Autopilot。
