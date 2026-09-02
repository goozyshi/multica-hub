# 执行与验证 Reference

仅在方案已获得明确确认后读取。本 Reference 定义远端写入顺序、失败处理、回读验证和
结果包。

## 写入前复核

确认后重新读取：

```bash
multica project list --output json
multica repo list --output json
multica project resource list <confirmed-project-id> --output json
multica autopilot list --output json
multica skill list --output json
```

重新确认 Sentry project 仍属于 `mico`，并按 `sentry-environment.md` 重新读取每个 project
的生产环境实际名称；如果使用 `feishu_app`，另外验证已确认群仍为 `normal`。如果候选
Autopilot、项目、项目资源、Repo、
Skill、群组或环境值状态变化，停止写入，重新展示完整方案并取得一次确认。

用户确认只授权当前展示的方案。没有确认时不得执行 `create`、`trigger-add`、更新或发送。

## 项目 Repo 资源门禁

`multica autopilot create` 只有 `--project`，没有 `--repo`；创建后通过
`project_id` 继承 Multica 项目已附加的资源。workspace 的 `repo list` 只能发现候选，
不能替代项目资源绑定。

将最新项目资源列表保存为：

```bash
multica project resource list <confirmed-project-id> --output json \
  > /tmp/sentry-ap-setup/project-resources.json
```

每个已确认 Repo 的完整 URL 必须以 `resource_type: github_repo` 出现在该文件中。若缺少：

1. 方案中必须明确显示“将 Repo 绑定到 Multica 项目”；
2. 只有用户确认当前绑定动作后，才执行：

   ```bash
   multica project resource add <confirmed-project-id> \
     --type github_repo \
     --url "<confirmed-repo-url>" \
     --output json
   ```

3. 重新读取项目资源列表并确认所有 Repo 已附加；绑定或回读失败时不得创建 Autopilot。

## Autopilot 描述强校验

将即将写入的完整巡检 Autopilot 描述保存为临时文件，先执行：

```bash
python3 skills/sentry-ap-setup/scripts/validate_autopilot_description.py \
  --description-file /tmp/sentry-ap-setup/inspection-description.md \
  --title "【<Multica 项目名称>】Sentry 巡检" \
  --agent "Inspector" \
  --mode create_issue \
  --project-id "<confirmed-project-id>" \
  --subscriber "<current-creator>" \
  --cron "<confirmed-cron>" \
  --timezone "<confirmed-iana-timezone>" \
  --project-resources-file /tmp/sentry-ap-setup/project-resources.json \
  --repo-url "<confirmed-repo-url>" \
  --output json
```

只有返回 `status: valid` 且 `decision: ready-to-create` 才能继续创建。启用解决单时，
校验结果必须确认描述中存在 `dedupe_key: project:issue_id`；缺失、固定为某个 Issue、
使用业务名称拼接或分支字段残留时，立即停止写入并返回 `needs-info`。

## 创建巡检 Autopilot

巡检实例始终新建：

```bash
multica autopilot create \
  --title "【<Multica 项目名称> Sentry 巡检】Sentry 每日 Top 巡检" \
  --description "<完整的巡检配置描述>" \
  --agent "Inspector" \
  --mode create_issue \
  --project "<confirmed-project-id>" \
  --subscriber "<current-creator>"
```

`--subscriber` 固定使用执行创建操作的当前用户身份。该身份由平台上下文解析，不在提问
轮次中收集或修改。

描述必须引用：

```text
inspection_type: sentry-daily-top-issues
profile_mode: skill-backed
profile_ref: skill:sentry-daily-top-issues
scope_project: <confirmed-scope>
```

描述的四个规范分区和字段格式遵循
[配置契约 Reference](configuration-contract.md)。业务名称、scope、项目分组、发送配置
和解决单配置都写入巡检实例。

创建成功后，仅为该实例添加已确认的 schedule：

```bash
multica autopilot trigger-add <inspection-autopilot-id> \
  --kind schedule \
  --cron "<confirmed-cron>" \
  --timezone "<confirmed-iana-timezone>"
```

添加 schedule 前再次使用同一份已校验描述和配置结果，确认 `resolution_enabled`、通知
分支及 `dedupe_key` 没有被 CLI 参数或编辑器改写。校验不通过时不得添加 trigger。

## 复用或初始化通用解决单路由

### 复用

兼容时只保存已有 ID，不更新已有配置、不更换 trigger、不改项目范围或目标。

### 首次初始化

只有确认 workspace 尚无兼容的通用解决单路由时，才初始化一个通用解决单入口，至少满足：

```text
profile_ref: skill:sentry-resolution-order
execution_mode: create_issue
project scope: workspace 通用 scope
trigger: webhook
business target: 不写入
business project: 不写入
```

使用平台现有 `multica autopilot create` 创建一次通用实例，并为该实例添加 webhook trigger。
后续业务默认复用该实例，不再按业务创建新的解决单 Autopilot。
不要把飞书 Webhook URL、App Secret、access token 或业务 callback 值写入解决单描述。
解决单 Autopilot 的执行者是通用 Coordinator；实际 Agent/Squad 目标只由巡检卡片
callback 携带。

`resolution_enabled=false` 时不创建、不绑定、不添加解决单 trigger。

## 执行顺序和失败处理

推荐顺序：

1. 绑定并回读确认项目 Repo 资源。
2. 创建巡检 Autopilot。
3. 添加巡检 schedule。
4. 复用或初始化通用解决单路由。
5. 添加解决单 webhook trigger（仅首次初始化分支）。

任一步骤失败，立即停止后续操作，记录已完成和未完成项，返回 `blocked`。保留已经成功
创建的资源，不自动回滚、不重复创建、不静默修改旧实例。

创建成功不代表巡检已经运行。解决单配置写入目标也不代表解决单已经创建或派发。

## 回读验证

对每个受影响 Autopilot 执行：

```bash
multica autopilot get <autopilot-id> --output json
```

逐项验证：

- `status`
- `assignee`
- `execution_mode`
- `project_id`
- `profile_ref`
- 启用解决单时，描述中存在 `dedupe_key: project:issue_id`
- 每个 Sentry project 的生产环境实际名称（保留原始大小写）
- trigger 类型
- schedule 的 cron 和 timezone
- subscriber

再执行：

```bash
multica skill list --output json
```

确认 `sentry-daily-top-issues`、`sentry-resolution-order` 存在且名称与
`profile_ref` 一致。Sentry project 仍必须属于 `mico`。

任一关键字段缺失、不匹配、Skill 不存在、权限不足或回读失败，返回 `blocked`。保留已
创建资源和验证错误，不报告配置完成。

## 结果包

成功时输出：

```text
result: executed
inspection_autopilot_id: <id>
resolution_autopilot_id: <id-or-empty>
sentry_org: mico
resolution_action: reused | created | skipped
scope_project: <project-id>
inspection_trigger: <cron-and-timezone>
resolution_trigger: <webhook-or-skipped>
subscriber: <subscriber>
resource_discovery: complete | partial
verification: passed | failed
remaining_decisions: <none-or-items>
```

字段不完整或仍等待用户选择时返回 `needs-info`。创建、绑定、权限或回读失败时返回
`blocked`，并列出已完成及未完成项。

## 边界

- 不创建业务解决单；解决单由下游 callback 流程创建。
- 不执行巡检、不发送测试飞书消息、不分析 Sentry 查询结果。
- 不修改日报 Skill、解决单 Skill、业务代码、Repo、分支、MR 或 Sentry Issue。
- 不输出凭据、Webhook、IP、用户标识或完整堆栈。
