---
name: sentry-ap-setup
description: 配置 Sentry 巡检与解决单 Autopilot，确认 workspace 资源和通知分支后创建或复用远端实例。
disable-model-invocation: true
---

# Sentry Autopilot 配置

## 目标与边界

本 Skill 是手动触发的配置编排器。一次配置产生：

- 巡检 Autopilot：始终新建，引用 `skill:sentry-daily-top-issues`，固定
  `inspection_type: sentry-daily-top-issues`。
- 解决单 Autopilot：仅在 `resolution_enabled: true` 时绑定 workspace 级通用路由，
  默认复用兼容实例；仅当 workspace 尚无兼容路由时，才一次性初始化引用
  `skill:sentry-resolution-order` 的通用入口，不按业务重复创建。

巡检目标以 `mico` 下已确认的 Sentry project 为主；Multica 项目只负责 Autopilot 归属和
资源范围。两者独立匹配、分别确认，Multica 候选数量不得改变 Sentry 的优先级。

业务差异只写入巡检 Autopilot 的描述、触发器和解决单 callback 配置，不创建新的业务
Skill。配置阶段不分析 Sentry 结果、不触发巡检、不发送测试消息、不创建业务解决单；仅在
项目环境元数据不可读时，按环境 Reference 执行环境探针或详情回退，只提取环境字段。
启用解决单时，`dedupe_key` 由系统默认写入 `project:issue_id`；用户不填写该字段，运行时
再按实际 Sentry project 和 Issue ID 展开为精确去重键。

## 跨 Skill 依赖

下游能力通过稳定的 Skill 名称和 `profile_ref` 引用，不通过本地文件相对路径嵌套，也不
复制下游实现：

- 生成巡检配置时，读取名称为 `sentry-daily-top-issues` 的 Skill；机器引用固定为
  `skill:sentry-daily-top-issues`。
- 仅在需要生成或发送飞书卡片时，读取该日报 Skill 管理的
  `feishu-card-delivery` Reference。
- 仅在 `resolution_enabled=true` 时，读取名称为 `sentry-resolution-order` 的 Skill
  及其 `resolution-creation-and-dispatch` Reference；机器引用固定为
  `skill:sentry-resolution-order`。

跨 Skill 依赖不可用时返回 `blocked`，不得根据名称猜测、复制或改写下游契约。本 Skill
自己的详细规则通过 `references/*.md` 按阶段读取。

## 执行协议

严格按 Phase 顺序执行。每轮只询问当前依赖已经满足的字段：

1. 同一轮问题的答案不得改变同轮其他问题的出现条件、候选集合或校验规则。
2. 会打开或关闭分支的问题必须先问；分支字段和分支资源发现只能在下一阶段执行。
3. 资源发现采用懒加载。未选 `feishu_app` 时不查询飞书群；Webhook 固定为只读且不查询
   解决单候选。自建应用默认启用解决单动作，因此选定该渠道后读取解决单候选并收集
   解决单配置；用户明确要求只读时才关闭。
4. 未得到明确的人类确认，不执行任何远端写操作。只读查询、规范化和方案展示不算写操作。
5. `needs-info` 表示缺少用户选择或必填输入；`blocked` 表示权限、工具、写入或回读失败；
   `executed` 只表示配置创建或复用并完成验证。

每个 Phase 的完成条件必须满足后才能进入下一 Phase。无法满足时返回对应状态，不用猜测值
或假装完成发现。

## 面向用户的表达

用户看到的是业务设置，不是 Autopilot 内部字段。提问卡片必须：

- 先给中文名称，再给填写方式、示例和影响；不能只展示 `cron`、`subscriber`、
  `environment`、`resolution_enabled` 等英文键。
- 选项使用“中文名称 + 一句话说明”。机器值只作为系统内部映射，不作为用户必须理解的
  参数。
- 用户确认的是项目归属、通知方式、Sentry 项目与 Repo 映射和处理目标；自建应用默认
  开启解决单，只有用户明确要求只读时才关闭，Webhook 固定关闭；
  业务名称、执行时间、`subscriber`、`dedupe_key` 及解决单细节使用默认值或系统核验结果；
  生产环境优先由系统核验，自动路径无法得到唯一值时才请用户提供原始环境名。
- 明确区分两个项目：`Multica 项目`决定 Autopilot、Repo 的资源范围；`Sentry project`
  是要巡检的错误来源项目，organization 固定为 `mico`。
- 明确区分两个通知对象：`Multica 订阅人`自动设置为当前创建人，接收 Autopilot
  运行/状态通知；`飞书通知目标`接收 Sentry 巡检卡片。
- 通知方式说明必须写清：机器人地址只发送只读卡片，用于查看错误摘要、指标、初判、建议
  和 Sentry 链接；自建应用默认发送可交互卡片，可查看巡检单、跳转 Multica，并从卡片
  点击“创建解决单”联动通用解决单流程。
- 首屏不展示原始 JSON、单独的完整 UUID 或凭据；资源 ID 必须保留在候选链接中，但不另行
  裸露展示。

详细中文文案、字段映射和通知方式说明见 [配置契约 Reference](references/configuration-contract.md)。

## Phase 0：解析入口并准备第 1 轮

入口格式：

```text
/sentry-ap-setup [scope_hint]
```

入口先完整读取 `mico` organization 的 Sentry project 列表，再读取 Multica project
列表（均包含全部分页结果）。Sentry 是本次创建 Sentry Autopilot 的主错误来源，候选
按 `name` 和 slug 匹配；Multica 是 Autopilot 的归属范围，候选按 `title`、
`description`、slug 和已登记 Repo 名称匹配。两套列表仍独立做本地匹配，`scope_hint`
不是新的 workspace，也不能跨系统自动推断项目、Repo、群组或目标 Agent。Sentry 的
标准化、匹配优先级和候选标记遵循 [资源发现 Reference](references/resource-discovery.md)。
第一条回复必须按 Sentry 优先顺序同时给出两套候选结果：先展示
`mico Sentry project（主错误来源）`，再展示 `Multica 项目（Autopilot 归属）`。
即使其中一套没有匹配，也要在同一张“入口候选卡”中明确显示“没有匹配”并给出可选
候选；不得先只展示 Multica 项目，再等待用户追问 Sentry project。
候选进入任何用户提问前，必须执行 [资源发现 Reference](references/resource-discovery.md)
中的“链接交付检查”：保留所需资源标识、构造完整 URL、检查占位符并同时输出候选名称、
完整地址和可点击链接。检查未通过时不得进入项目确认。

- 一个 Multica 项目候选：把候选名称和可点击链接放入第 1 轮，请用户确认；项目 ID
  只作为系统绑定值。
- 多个 Multica 项目候选：第 1 轮要求用户选择候选名称和链接，不要求用户手填 ID。
- 没有匹配候选：第 1 轮列出可选 Multica project 并要求选择；未选择时该轮返回
  `needs-info`。
- 没有 `scope_hint`：把唯一明确项目作为待确认候选；多个项目要求选择。

入口候选卡必须同时包含两套资源；候选结果必须使用“名称 + 完整地址 + 可点击链接”
展示；资源 ID、slug 只作为系统绑定
值或消歧辅助信息，不单独输出完整 UUID。实际输出不能只显示候选名称或代码样式文本。

Sentry project 只从 `mico` 列表产生：

- 精确匹配：在入口结果中标记“`mico` 中已找到候选”，第 1 轮先确认本次要使用的候选，
  第 2 轮再按分组确认映射。
- 可能匹配：入口结果标记“`mico` 中可能匹配”，列出名称、slug 和标识，第 1 轮确认
  候选，第 2 轮按分组独立选择。
- 没有匹配：明确标记“`mico` 中没有匹配候选”，同时列出可选 project；不得把 Multica
  项目名称当成 Sentry project。
- Sentry 查询失败、权限不足或返回为空：返回 `needs-info` 或 `blocked`，不得进入创建方案。
- 候选链接交付检查失败：先重新读取并标准化候选；只有 slug 也无法校验时返回
  `resource_discovery: partial`，不得输出“请确认项目”的卡片。

Phase 0 完成条件：同一条首轮回复中已出现 Multica 和 Sentry 两个候选区块；每个可展示
候选均有匹配状态、名称、完整地址和可点击链接；两套结果都完成后，才显示第 1 轮问题。

### 第 1 轮：一次确认基础设置

在同一张问题卡片中一次询问以下互不影响的基础设置。先展示通知方式区别，再让用户
选择，不要先查询群聊或询问解决单设置：

| 通知方式                  | 适合场景                                                                                                     | 用户需要提供                 |
| ------------------------- | ------------------------------------------------------------------------------------------------------------ | ---------------------------- |
| 飞书机器人地址（Webhook） | 只读卡片：查看错误摘要、次数、影响用户、初判、建议和 Sentry 链接；可点击“查看巡检单”跳转 Multica，但不能创建解决单    | 下一轮提供 HTTPS 机器人地址  |
| 飞书自建应用              | 可交互卡片：系统默认配置巡检单链接，点击“查看巡检单”跳转 Multica；默认可点击“创建解决单”联动通用解决单流程 | 下一轮从应用已加入的群中选择，巡检单链接自动补全 |

| 要确认的设置                 | 用途                                           | 回复方式                             |
| ---------------------------- | ---------------------------------------------- | ------------------------------------ |
| Sentry project（主错误来源） | 确认本次创建 Sentry Autopilot 要巡检的错误项目 | 从 `mico` 候选中选择一个或多个       |
| 巡检归属项目                 | 决定使用哪个 Multica 项目和代码资源            | 从候选中确认项目                     |
| 通知方式                     | 选择上方一种飞书发送方式                       | 选择“飞书机器人地址”或“飞书自建应用” |

业务名称默认使用“<Multica 项目名称> Sentry 巡检”，执行时间默认每天 10:00，Multica
订阅人固定使用当前创建人；这些设置不询问，也不与飞书通知群混淆。这一轮不询问 Webhook
地址、飞书群、解决单按钮开关（自建应用默认开启）、解决单处理目标、观测时长或代码仓库。代码仓库
和分组映射在 Sentry 主候选与 Multica 归属确认后再处理。

完成条件：Sentry 主候选、Multica `project_id`、通知方式都有明确答案，当前创建人
身份可解析。Multica 候选较多时不得替代或延后 Sentry 候选确认；缺少任一必填确认时
返回 `needs-info`，不得执行后续资源发现。

## Phase 1：按已选分支发现资源并批量收集配置

读取 [资源发现 Reference](references/resource-discovery.md)。

### 基础资源发现

第 1 轮完成后，读取：

```bash
multica repo list --output json
multica project resource list <confirmed-project-id> --output json
multica autopilot list --output json
multica skill list --output json
```

`multica repo list` 只提供 workspace 级候选；实际可供 Autopilot 使用的 Repo 以目标
Multica project 的 `project resource list` 为准。展示已确认 scope 下已附加的 Repo
和相关 Autopilot；workspace 候选中与已确认映射相关但尚未附加到项目的 Repo 也可展示，
但必须标记 `resource_discovery: partial`，不得把它当成已可用资源。

复用 Phase 0 已完整获取的 `mico` Sentry project 列表。Sentry project 只从该列表选择，
不使用 Multica project、Repo 名称或描述推断。展示名称、用途、归属和可跳转链接，供用户
独立选择；slug、项目 ID 等技术标识只作为候选确认的辅助信息。

### 分支资源发现

只有第 1 轮已确定分支后才执行：

- `notification_channel=feishu_app`：默认启用解决单；使用固定 `profile=sentry-notify`，以 Bot 身份执行
  `lark-cli` 群聊枚举，只保留 `chat_status=normal` 的 `oc_...` 群。该分支发送可交互
  卡片，默认配置巡检单链接，可点击“查看巡检单”跳转 Multica，并可点击“创建解决单”
  联动通用解决单流程。用户明确要求只读时才关闭解决单动作。
- `notification_channel=feishu_webhook`：不执行任何飞书群查询；下一轮直接收集
  `webhook_url`。该分支发送只读卡片，包含可跳转 Multica 的“查看巡检单”链接，固定
  `resolution_enabled=false`，不创建或绑定解决单 Autopilot。
- 只有 `notification_channel=feishu_app` 且未明确要求只读时，才读取解决单 Autopilot
  候选的完整详情，并执行：

  ```bash
  multica agent list --output json
  multica squad list --output json
  ```

  只展示可用的 Agent 和 Squad 名称、用途；目标 ID 由用户选择名称后自动写入，不要求
  用户手填或记忆 UUID。

分支发现失败时按 Reference 返回 `needs-info`、`blocked` 或
`resource_discovery: partial`。未启用分支展示“未启用/未查询”，不展示虚构结果。

### 第 2 轮：问已具备候选的字段

资源发现完成后，一次询问当前依赖已满足、且答案互不影响的字段：

```text
巡检范围

| 业务分组 | Sentry 项目（错误来源） | 代码仓库（Multica Repo） | 每组最多展示 |
| --- | --- | --- | --- |
| 待确认 | 待选择 | 待选择 | 默认 3 条 |

Sentry 错误环境：默认生产环境；确认分组后，系统核验每个项目的实际名称，例如 `Prod`、
`prod` 或 `Production`。只有用户明确要求时才查询全部环境。
```

根据第 1 轮选择的通知方式，只追加一个通知设置：

```text
飞书机器人 Webhook：填写 HTTPS Webhook 地址；巡检单链接使用系统默认值
```

或：

```text
飞书自建应用：从应用已加入且状态正常的群中选择目标群，巡检单链接使用系统默认值
```

自建应用默认提供“创建解决单”按钮，并在下一轮询问解决单授权和处理目标；用户明确要求
只读时才关闭该按钮并跳过解决单配置。Webhook 分支不显示此项，因为它只发送只读卡片。

### 生产环境核验

第 2 轮确认 Sentry project 后，读取 [Sentry 环境读取 Reference](references/sentry-environment.md)。
按其中的 MCP 能力探测、只读调用、环境探针、Issue 详情回退、结果归一化和失败状态处理
每个已选 project；回退只提取环境字段，不做 Issue 分析。自动路径无法得到唯一值时请用户
提供实际环境名；不要把环境读取失败直接描述成“Sentry 没有环境数据”。

### 第 3 轮：问已启用解决单分支的设置

仅当通知方式为“飞书自建应用”且未明确要求只读时，一次询问：

| 要确认的设置         | 中文含义                       | 回复方式                                 |
| -------------------- | ------------------------------ | ---------------------------------------- |
| 允许创建解决单的项目 | 哪些 Sentry 项目允许发起解决单 | 从已验证项目中选择                       |
| 解决单处理目标类型   | 指定单个 Agent 或小队          | 选择 Agent（单个 Agent）或 Squad（小队） |

允许创建解决单的项目只能从已验证的 `mico` Sentry 项目中选择。Sentry 项目与代码仓库
必须独立选择并逐项确认，不能按名称相似度自动映射。修复后影响观察默认开启；风险等级
优先级默认高风险 P1、中风险 P2、低风险 P3；观察时长默认 7 天，修复后继续观察 3 天。
这些默认值不在本轮提问，用户后续可直接修改 Autopilot。

### 第 4 轮：选择解决单处理目标

处理目标类型确定后，从对应的 `multica agent list` 或 `multica squad list` 候选中让用户
选择名称和用途；选中后由系统自动保存平台唯一 ID。不得要求用户输入 UUID。

`resolution_enabled=true` 时默认使用高风险 P1、中风险 P2、低风险 P3；开启修复后影响
观察时默认最多观察 7 天、修复后继续观察 3 天。用户后续可直接修改 Autopilot 配置。

所有询问卡片使用分段标题和 Markdown 表格。用户问题表使用中文业务表头；写入
Autopilot 描述时，才转换为下游要求的 `| 分组 | 项目 | Repo | Top N |` 机器表头。表格不可
渲染时改用结构化字段，不使用连续编号列表或伪表格。

完成条件：所有启用分支的字段齐全且包含系统默认巡检单链接；Webhook 分支的 `resolution_enabled` 为 false；每个
Sentry project 已由 `mico` 列表验证且按环境 Reference 得到 `resolved`，或完成歧义/自动读取失败后的用户确认；
解决单目标来自已读取的 Agent 或 Squad 候选；每个 Multica Repo 已附加到已确认 scope
或已在方案中列出待执行的绑定动作；每一项 project-repo 映射均由用户确认。

## Phase 2：规范化、校验与方案确认

读取 [配置契约 Reference](references/configuration-contract.md) 和
[校验与复用 Reference](references/validation-and-reuse.md)。

执行以下顺序：

1. 拒绝未知字段、缺失必填项、重复 Sentry project、空分组、未确认映射、未附加且未列入
   待执行绑定的 Repo、非正整数、非法枚举、无效 IANA 时区、非 HTTPS URL、非法 `chat_id`
   和不一致的 Autopilot 引用。
2. 校验所有 Sentry project 属于 `mico`，并通过
   `multica project resource list <confirmed-project-id> --output json` 验证每个 Repo 已
   附加到已确认 Multica scope；未附加时把资源绑定列入待确认方案。
3. 规范化发送配置和 Autopilot Markdown 描述，使其符合日报 Skill 的四个配置分区及字段
   契约。
4. 将待写入的完整 Autopilot 描述写入临时文件，并将已确认项目资源列表写入临时文件，运行
   `scripts/validate_autopilot_description.py`。只有返回 `status: valid`、
   `decision: ready-to-create` 才允许展示“可创建”方案；校验结果必须同时显示
   `dedupe_key=project:issue_id` 和通知分支
   `inspection_url_template=https://multica.micoplatform.com/mico-fe/issues/` 的系统默认值。
从 Webhook 切换到默认开启解决单的飞书自建应用时，必须重新生成完整四个配置分区，不能只
   增量修改 `channel`；应用群、解决单授权、处理目标和 `dedupe_key` 必须一起补齐并重新
   校验。
5. 通知方式为自建应用且 `resolution_enabled=true` 时读取候选解决单 Autopilot 完整详情，
   默认复用兼容实例。
   仅当 workspace 尚无兼容通用路由时，才制定一次性初始化方案；不得按业务重复创建或
   静默修改已有实例。
6. 展示完整业务方案，明确显示巡检 AP 新建、通用解决单路由的复用/初始化/不启用、所有
   分组映射、Repo 资源已附加/待绑定状态、触发器、通知目标和解决单目标。Webhook URL
   只显示“已配置”，不回显 URL；同时说明 Webhook 为只读卡片，自建应用为可交互卡片，
   两者都可通过配置链接跳转 Multica。

方案只对业务字段要求明确确认。没有确认时返回 `needs-info`，不创建、更新、触发或发送。

完成条件：配置规范化成功、复用判定完成、完整方案已展示并获得一次明确确认。

## Phase 3：确认后创建或复用

读取 [执行与验证 Reference](references/execution-and-verification.md)。

确认后重新读取 Multica project、项目资源、Repo、Sentry project、Skill、群组和候选
Autopilot 状态，并将最新项目资源列表保存为校验输入。
任一候选发生变化，重新展示方案并再次确认。

写入前必须使用最新项目资源列表和确认的 Repo URL，对重新生成的完整巡检 Autopilot 描述再次运行
`scripts/validate_autopilot_description.py`。校验不是 `status: valid` 且
`decision: ready-to-create` 时，停止所有写入并返回 `needs-info`；不得沿用上一轮
“已校验”结论。

如果确认的 Repo 尚未附加到目标 Multica project，只有当前方案已明确展示并获得绑定
确认时，才先执行 `multica project resource add`；绑定后必须重新读取项目资源列表，
确认所有 Repo 已存在，再创建 Autopilot。未完成绑定或回读失败时不得创建。

创建规则：

- 巡检 Autopilot 始终新建，使用 `--mode create_issue`、`--agent "Inspector"` 和确认的
  `project_id`，描述中必须包含：

  ```text
  inspection_type: sentry-daily-top-issues
  profile_mode: skill-backed
  profile_ref: skill:sentry-daily-top-issues
  scope_project: <业务 scope>
  ```

- 巡检 schedule 使用已确认的 cron 和 IANA timezone。
- `autopilot create` 没有 `--repo` 参数；代码仓库通过已绑定的 Multica project 资源
  随 `--project` 继承。不得因为创建命令没有 Repo 参数而跳过项目资源核验，也不得把
  未附加的 workspace Repo 当作已绑定资源。
- 解决单复用时只保存现有 ID，不更新配置。
- 解决单仅在 workspace 尚无兼容通用路由、且通知方式为自建应用时初始化，使用
  `profile_ref: skill:sentry-resolution-order`、通用 workspace scope、
  `--mode create_issue` 和 webhook trigger；不写入业务项目、固定 Agent/Squad 或飞书
  Secret。
- 巡检 Autopilot 的解决单目标只写入业务配置，并在生成卡片 callback 时传入
  `target_assignee_type` 和 `target_assignee`。不创建 Builder 子流程。

任一创建或触发操作失败，停止后续操作，报告已完成和未完成项；不自动回滚已成功创建的
Autopilot。

## Phase 4：回读验证与结果

对每个受影响 Autopilot 执行：

```bash
multica autopilot get <autopilot-id> --output json
```

验证 `status`、`assignee`、`execution_mode`、`project_id`、`profile_ref`、触发器、cron、
timezone 和 subscriber；再读取目标项目资源，确认方案中的每个 Git Repo 仍已附加到该
Multica project；若启用解决单，还要验证描述中存在
`dedupe_key: project:issue_id`，再读取：

```bash
multica skill list --output json
```

若 Skill 引用不存在或名称不一致、Sentry project 不属于 `mico`、关键字段回读不匹配，
返回 `blocked`，不得报告配置完成。

成功结果使用以下结果包：

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

配置不完整返回 `needs-info`。远端创建、目标绑定、权限或回读失败返回 `blocked`。
“Autopilot 已创建”不等于“巡检已运行”；“目标已写入配置”不等于“解决单已派发”。

## 不可越过的边界

- 不修改 `sentry-daily-top-issues`、`sentry-resolution-order` 或业务代码。
- 不修改 Repo、分支、MR 或 Sentry Issue。
- 不执行 Sentry 查询结果分析，不触发巡检，不发送测试飞书消息，不创建业务解决单。
- 不输出、读取或保存 App Secret、access token、Webhook、IP、用户标识或完整堆栈。
- 固定使用 `sentry_org=mico`、`app_id=cli_aa1a82ab6d785cc2`、
  `profile=sentry-notify`；调用方不能覆盖应用绑定。
