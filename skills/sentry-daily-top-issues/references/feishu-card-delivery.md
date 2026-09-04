# 飞书卡片与发送 Reference

仅在当前 Autopilot 配置需要生成或发送飞书消息时读取本 Reference。它定义发送配置校验、interactive Card 2.0 结构、解决单按钮载荷、发送前一致性校验和通道发送方式；Sentry 查询、排序、详情研判和解决单幂等流程仍以主 Skill 为准。

## 执行门禁

- 先把 Autopilot 的发送配置规范化为 JSON，再生成 Card JSON；禁止直接拼接并发送未经校验的字符串。
- `inspection_url_template` 保留该字段名以兼容历史配置，但规范值采用前缀模式：必须是原始 HTTPS 基础 URL，通常以 `/` 结尾，例如 `https://multica.micoplatform.com/mico-fe/issues/`。发送阶段将当前巡检 Issue ID 直接拼接到前缀后。Markdown 链接、query、fragment 或其他非 HTTPS 值均为配置错误。
- 历史配置仍兼容一个原始 `<Issue-ID>` 占位符，例如 `https://multica.micoplatform.com/mico-fe/issues/<Issue-ID>`；不再要求新配置使用占位符。若编辑器仅将同一 URL 序列化为 `[URL](URL)`，validator 会还原这一层；显示文本和目标不一致的 Markdown 链接仍然拒绝。发送阶段必须先取得当前巡检 Issue ID，并将其传入 validator 的 `--inspection-issue-id` 完成 URL 解析。没有真实 ID 时不得生成“查看巡检单”按钮或发送卡片。
- 配置创建或修改时，先展示规范化配置、Card 预览和 validator 结果，取得一次明确的人类确认后才允许启用或测试发送。配置未变化且已确认的定时运行，可在 validator 通过后自动发送。
- 手工运行、配置变更后的首次运行或 validator 版本变更时，必须再次展示预览并等待确认；未确认不得发送。
- 使用仓库内的 `scripts/validate_feishu_card.py` 校验配置和最终 Card JSON。validator 返回非零、`status` 不是 `valid` 或 `decision` 不是 `ready-to-send` 时，结果为 `blocked` 或 `needs-info`，禁止发送。

## Markdown 动态文本转义

- 进入 Card 2.0 `markdown.content` 的动态文本必须先转义 HTML 字符：`&` 转为 `&amp;`、`<` 转为 `&lt;`、`>` 转为 `&gt;`；例如原始摘要 `<object>.value` 必须序列化为 `&lt;object&gt;.value`，飞书渲染后显示为 `<object>.value`。
- 只转义显示文本变量，不转义 Markdown 结构、链接 URL 或按钮 callback 的原始字段。`issue_title` 在 callback value 中保留原始值，标题 Markdown 使用单独的 `issue_title_markdown` 转义副本。
- `analysis`、`recommendation`、摘要和其他动态 Markdown 文本遵守同一规则；不要在发送前再次 `html.unescape`，避免转义结果重新变成 HTML 标签。
- `div` 的 `plain_text` 不经过 Markdown 解析，但其内容仍必须保持普通文本，不得借此写入 Markdown 语法。
- validator 必须拒绝 Markdown 内容中的未转义 HTML 标签，例如 `<object>`、`<script>`；拒绝后不得发送卡片。

```bash
python3 skills/sentry-daily-top-issues/scripts/validate_feishu_card.py \
  --card /tmp/sentry-card/card.json \
  --config /tmp/sentry-card/send-config.json \
  --operation create \
  --candidate-count <N> \
  --resolution-enabled <true|false> \
  --source-inspection-autopilot-id <来源巡检Autopilot-UUID> \
  --inspection-issue-id <巡检Issue-ID>
```

仅 `resolution_enabled: true` 时，为每条候选追加一次 `--candidate-id <Issue-ID>`；Webhook 只读模式（`false`）不传 `--candidate-id`。

## 发送配置校验

配置解析和发送前都严格校验“发送配置”与通道匹配：

- `channel: feishu_webhook` 要求 `transport: curl`、`msg_type: interactive`、`max_cards_per_run: 1`、`resolution_enabled: false` 和有效 HTTPS `webhook_url`。Webhook 只发送只读卡片，不承载解决单动作。发送给群机器人时，HTTP 请求体必须为外层 `{"msg_type":"interactive","card":<卡片对象>}`；`msg_type` 必须位于最外层。
- `channel: feishu_app` 要求 `transport: lark_cli`、`profile`、`as: bot`、`chat_id`、`msg_type: interactive` 和 `max_cards_per_run: 1`。使用运行环境中已配置并验证的 `lark-cli` profile；`chat_id` 必须是目标群的 `oc_...`。应用机器人必须已加入目标群并拥有发送消息权限。App Secret 只保存在 profile 中，不写入 Autopilot 描述、Issue 或卡片。
- 任一通道字段缺失、类型错误或值不合法时，输出字段级错误，结果为 `needs-info`，不得发起 Sentry 查询或发送消息。

## `global_top_n_markdown_v1` 卡片

使用飞书 interactive Card 2.0 JSON，保持简洁布局。根对象必须包含 `"schema": "2.0"`、`header` 和 `body.elements`；使用实际换行或独立元素，绝不把字符 `\\n` 显示给用户。

### 错误摘要字段提取

每条候选必须先生成唯一的 `resolved_issue_title`，再同时填入 callback 的 `issue_title` 和标题展示副本 `issue_title_markdown`。按以下顺序读取第一个非空字符串，不得由模型自由选择：

1. 详情 `exception.values[0].value`
2. 详情 `message`
3. 详情或列表 `issue_title`
4. 详情 `title`
5. 详情 `culprit`
6. `错误标题缺失`

`metadata.value`、`_fingerprint_info.client_fingerprint`、函数名、堆栈文件名和路由字段只用于证据或上下文，不得抢占前面的标题优先级。若 `exception.values[0].value` 存在，即使同时存在 `title`，也必须使用异常值；例如 `exception.values[0].value` 为 `Event \`ProgressEvent\` (type=error) captured as exception`、`title`为`o.onerror` 时，卡片标题必须是前者。

展示时仅对 `resolved_issue_title` 生成 HTML 转义后的 `issue_title_markdown`；callback 的 `issue_title` 保留同一标题的原始值。最终 Card 标题、callback `issue_title` 和 `resolved_issue_title` 必须一致，否则返回 `blocked`。

序列化要求：每条 Issue 必须拆成独立的 `body.elements`，不得把标题、元数据、指标、路由、初判和建议拼成一个字符串。错误标题使用 `tag:"markdown"` 元素承载 `**[<错误摘要>](<issue_url>)**`；项目/归因/版本/路由上下文使用独立的 `tag:"div"` + `text.tag:"plain_text"`，并设置 `text_color:"default"`、`text_size:"notation"`、`text_align:"left"`，同时使用蓝色信息图标；指标和“初判/建议”使用独立的 `tag:"markdown"` 元素，错误标题、指标中的“事件数 · 用户数”部分和“初判/建议”标签使用 Markdown 加粗。Card 2.0 的 `markdown` 元素不支持 `text_color` 字段；任何 `markdown.text_color` 都必须在发送前被 validator 拒绝。不得在 `plain_text` 中写入 `**`、Markdown 链接或转义换行。需要换行时使用独立元素或真实换行符 `\n`（解析后的 JSON 字符串），发送前检查最终 Card JSON 中不存在字面量 `\\n`、裸 `**` 或未解析的 Markdown 标记。

### 固定 Card 2.0 模板

渲染器必须直接读取仓库模板 `templates/feishu-card-v2.json` 生成卡片。下方 JSON 是同一模板的可读预览；文件是唯一事实源，文件与本文不一致时以文件为准。`{{...}}` 仅表示内容占位符，不是飞书语法；发送前必须全部替换。`resolution_enabled: true` 时，`resolution_autopilot` 缺失必须补为 `4833c3e9-b19b-4ace-bea2-bca87e4f2a01`，存在时也必须精确等于该 UUID；任何未渲染占位符、旧 ID、名称或带后缀字段都必须被 validator 拒绝。禁止让模型自由重建 Card JSON、增加字段或改变元素顺序。候选数量变化时，只复制完整的“候选块”；候选块内部结构和字段保持不变。`查看巡检单`按钮按配置决定是否追加到卡片末尾。

```json
{
  "schema": "2.0",
  "header": {
    "template": "red",
    "title": {
      "tag": "plain_text",
      "content": "【{{scope}}】Sentry 错误巡检 · {{frequency}} Top {{display_top_n}}"
    }
  },
  "body": {
    "elements": [
      {
        "tag": "markdown",
        "content": "{{environment_prefix}}近 {{time_window}} · {{unresolved_count}} 条未解决",
        "margin": "0px"
      },
      {
        "tag": "markdown",
        "content": "**[{{issue_title_markdown}}]({{issue_url}})**",
        "margin": "0px"
      },
      {
        "tag": "div",
        "icon": {
          "tag": "standard_icon",
          "token": "info_outlined",
          "color": "blue"
        },
        "text": {
          "tag": "plain_text",
          "content": "{{group}} · {{ownership}}（{{analysis_status}}）{{route_suffix}}",
          "text_color": "default",
          "text_size": "notation",
          "text_align": "left"
        },
        "margin": "0px"
      },
      {
        "tag": "markdown",
        "content": "**{{event_count}} 次 · {{user_count}} 用户** · 最近 {{last_seen_relative}}{{release_suffix}}",
        "margin": "0px"
      },
      {
        "tag": "markdown",
        "content": "**初判：** {{analysis}}",
        "margin": "0px"
      },
      {
        "tag": "markdown",
        "content": "**建议：** {{recommendation}}",
        "margin": "0px"
      },
      {
        "tag": "button",
        "text": {
          "tag": "plain_text",
          "content": "创建解决单"
        },
        "type": "primary",
        "size": "small",
        "width": "default",
        "behaviors": [
          {
            "type": "callback",
            "value": {
              "action": "create_sentry_resolution",
              "sentry_org": "{{sentry_org}}",
              "project": "{{project}}",
              "issue_id": "{{issue_id}}",
              "issue_title": "{{issue_title}}",
              "issue_url": "{{issue_url}}",
              "event_count": "{{event_count}}",
              "user_count": "{{user_count}}",
              "first_seen": "{{first_seen}}",
              "last_seen": "{{last_seen}}",
              "group": "{{group}}",
              "dedupe_key": "{{project}}:{{issue_id}}",
              "resolution_autopilot": "{{resolution_autopilot}}"
            }
          }
        ],
        "margin": "0px"
      }
    ]
  }
}
```

模板渲染后还必须执行以下机械规则：`event_count`、`user_count` 等载荷字段恢复为正确类型；`{{environment_prefix}}`、`{{route_suffix}}`、`{{release_suffix}}` 缺失时替换为空字符串，非空 `release_suffix` 自带前置 `·`；上下文块必须保持 `div + plain_text(default + notation) + blue info icon`。`resolution_enabled: true` 时，每增加一个候选块就在上一候选按钮后增加一个 `{"tag":"hr","margin":"4px 0px"}`；`false` 时移除候选块中的完整解决单按钮，并在上一候选内容后增加分隔线。两种模式的候选分隔线数量均严格为 `N - 1`；已存在解决单时只替换对应按钮对象；任何 `markdown` 元素不得出现 `text_color`。最后运行 validator，未返回 `status: valid` 和 `decision: ready-to-send` 时禁止发送。

紧凑布局：所有 `markdown`、`div` 和 `button` 元素显式设置 `margin:"0px"`；候选之间的独立 `hr` 分隔线设置 `margin:"4px 0px"`。指标、初判和建议连续展示，不额外插入空白元素制造间距。正文元素不得使用空内容、首尾空行或连续空行。

状态更新必须基于已发送的规范化 Card JSON：先持久化发送成功的完整 Card JSON，更新时复制原卡片，只替换发生状态变化的按钮对象，保留所有非按钮元素及其顺序、标签和视觉字段。首发卡片在渲染“创建解决单”前必须完成解决单 Autopilot 项目范围内的最终幂等预检，按 `project:issue_id` 分页查元数据并对历史描述执行精确去重键兜底；命中活动解决单时首发即展示“查看解决单”，不得先展示创建按钮。状态查询失败时不得安全降级为创建按钮，应返回 `needs-info` 并暂缓发送。处理中、成功和幂等复用等按钮状态更新必须使用 `--operation update`，并将更新前 Card JSON 作为 `--previous-card` 传给 validator；缺少旧卡片、按钮数量或位置变化、非按钮结构变化或视觉字段变化均为 `blocked`，不得调用 Lark 更新接口。失败提示若需要更新正文，也必须通过同一规范化渲染路径生成并保留上下文结构。

1. 红色标题栏：`【<scope>】Sentry 错误巡检 · <frequency> Top <display_top_n>`；`frequency` 根据 `time_window` 推导（`24h` 为“每日”，`7d` 为“每周”，其他值直接显示时间窗），不得写死业务名或周期。
2. 一行摘要：`<environment> · 近 <time_window> · <总 Error Issue 数> 条未解决`；环境缺失时省略，不重复展示 Top 数量。
3. 按全局排名展示 `display_top_n` 条，每条使用独立的文本块，不重复展示各组 Top N。相邻候选之间必须插入一个独立顶层 `{"tag":"hr"}` 元素；`N` 条候选必须恰好有 `N - 1` 个候选分隔符。启用解决单时，分隔符紧跟上一条候选的解决单按钮；Webhook 只读模式下，分隔符紧跟上一条候选内容并紧邻下一条候选标题。最后一条之后不得添加候选分隔符。
4. 每条按示例使用独立文本块（按钮作为独立元素，不计入正文行数），顺序固定：
   - `**[<错误摘要>](<issue_url>)**`，标题加粗并直接链接 Sentry Issue；不展示 `issue_id`、项目短码或其他机器标识。错误摘要字段提取、优先级和 `resolved_issue_title` 一致性以“错误摘要字段提取”为唯一规则，绝不渲染内部字段名。
   - `<分组名> · <Web 前端|后端|客户端>（<初步判断|待核实>） · 路由：<页面路径>`；该上下文使用 `div + plain_text`、`default` 色、`notation` 字号和蓝色信息图标，页面路径缺失时省略路由及前置分隔符；不要展示“全局第 N 条”。
   - `**<event_count> 次 · <user_count> 用户** · 最近 <last_seen 相对时间> · <release>`；仅事件数和用户数部分加粗，时间与版本保持常规字重，`release` 缺失时仅省略该字段，环境不在此行重复展示。
   - `**初判：** <可能原因>`；仅标签加粗，正文保持常规字重并与标签同行，详情证据不足时在正文末尾标注“证据不足”。
   - `**建议：** <建议处理>`；仅标签加粗，正文保持常规字重并与标签同行，使用纯文案，不添加色块或引用块。
5. `resolution_enabled: true` 时，每条正文后立即追加一个 Card 2.0 操作按钮，不能集中到卡片底部；每条只能出现一次。按钮状态固定为三态，卡片背景保持白色：无未关闭解决单时为左对齐、`size:"small"`、`width:"default"`、`type:"primary"`（蓝色描边）的“创建解决单” callback 按钮；回调已受理但解决单尚未返回时为相同尺寸、`type:"default"`、`disabled:true`（灰色禁用）的“处理中…”按钮；已创建或复用解决单且有 URL 时为相同尺寸、`type:"default"`（正常默认样式）的“查看解决单” open_url 按钮。按钮不得包在居中容器内。Card 2.0 回调按钮必须使用 `behaviors`，不得使用旧式顶层 `value`。`resolution_enabled: false` 时保留候选的 Sentry 标题链接和只读分析内容，但每条候选不得生成解决单按钮，也不得保留空按钮占位。
6. `inspection_url_template` 存在且通过执行门禁校验时，将当前巡检 Issue ID 拼接到前缀后（历史 `<Issue-ID>` 模板则执行占位符替换），在卡片底部提供一个独立的 Card 2.0 `button`，设置 `width:"fill"` 撑满整行，使用 `behaviors:[{"type":"open_url","default_url":"<resolved-url>"}]`；未配置模板时省略该按钮。配置存在但无效时按执行门禁返回 `blocked`，不得发送缺少该按钮的卡片。

视觉层级固定为：顶层 `header.template:"red"` 告警标题栏；错误标题使用 `markdown` 的加粗链接（由飞书 Markdown 默认链接样式呈现）；指标中的事件数和用户数部分使用 Markdown 加粗，最近时间和版本保持常规字重；项目/归因/版本/路由等上下文使用 `div + plain_text` 的 `default` 色 `notation` 小字，并以前置蓝色信息图标区分；指标、初判和建议连续展示，不插入中间分隔线；所有 `markdown` 元素不得设置 `text_color`，避免 Card 2.0 接口拒绝未知字段；“初判：”和“建议：”使用同一白色背景的 `markdown` 常规文案，标签必须加粗，正文保持常规字重并与标签同行；不使用色块、引用块、额外底色或高饱和颜色。卡片不得放入完整堆栈、原始标签、长段落、重复列表、IP、用户标识或 Webhook。

上述视觉规则同时适用于首次创建和后续更新。首次创建使用 `--operation create`，要求上下文使用 `div + plain_text(default + notation) + blue info icon`、指标中的事件数和用户数部分加粗、`初判/建议` 标签加粗，并完整通过颜色与层级校验；更新使用 `--operation update --previous-card <previous-card.json>`，先完成当前卡片校验，再额外校验是否仅替换允许变化的按钮。历史卡片若仍使用普通 `markdown` 上下文、灰色小字或未加粗标签，更新时沿用旧结构，不自动迁移非按钮样式。

按钮状态转换：点击“创建解决单”且回调已受理后，立即将同一位置更新为白底灰色禁用的“处理中…”；解决单创建或幂等复用成功后更新为白底默认样式的“查看解决单”并写入解决单 URL；创建失败时恢复为白底蓝色描边的“创建解决单”，并在该条建议后追加简短失败提示。

## Card 2.0 结构硬约束

- 根对象必须为 `schema: "2.0"`，`body.elements` 必须是数组；不得退回无 schema 的 1.0 混合结构。
- `resolution_enabled: true` 时，每条候选必须有一个且仅有一个解决单操作 `tag: "button"`，且为独立左对齐的小按钮（`size:"small"`、`width:"default"`）；三态样式分别为：`type:"primary"` 蓝色描边的“创建解决单” callback、`type:"default"` 且 `disabled:true` 的灰色“处理中…”、`type:"default"` 正常样式的“查看解决单” open_url。callback 按钮的 `value.issue_id` 必须与该条目唯一匹配，处理中状态不得继续触发创建动作。`resolution_enabled: false` 时，每条候选必须没有 `width:"default"` 的解决单按钮。
- Sentry 详情通过错误标题上的 Markdown 链接进入，不再为每条 Issue 添加“查看 Sentry”按钮；解决单状态按钮仍只允许一个。
- 启用解决单时，不得因回调服务尚未配置、详情读取失败或某条初步研判证据不足而移除按钮；这些状态只影响按钮点击后的处理结果。Webhook 只读模式不适用此按钮要求。
- `inspection_url_template` 有值且能解析时，卡片最后必须有一个 `width:"fill"` 的满宽“查看巡检单”按钮并带 `open_url` 行为；前缀模式必须拼接当前巡检 Issue ID，配置存在但解析失败时结果为 `blocked`，不得发送缺少该按钮的卡片。
- 卡片元素数不得超过 200；任一结构或动作校验失败，结果为 `blocked`，不得发送部分卡片或无按钮卡片。

## 解决单动作载荷

仅 `resolution_enabled: true` 生成“创建解决单”按钮。每个“创建解决单”按钮的 `value` 必须包含 `action: create_sentry_resolution`、`sentry_org`、`project`、`issue_id`、`issue_title`、`issue_url`、`event_count`、`user_count`、`first_seen`、`last_seen`、`group`、`resolution_autopilot`、`target_assignee_type`、`target_assignee`、`resolution_config_version` 和按 `dedupe_key` 生成的去重键。`target_assignee_type` 和 `target_assignee` 必须来自当前 Autopilot 的已确认解决单配置；`target_assignee` 必须是对应 Agent 或 Squad 的 UUID。`event_count`、`user_count` 使用本次已按 Autopilot `time_window`、`filter` 和 `environment` 执行的 `search_issues` 返回值，统一记录为当前查询窗口统计；不要求返回字段重复携带 `24h` 或 `7d` 标记。`resolution_config_version` 固定为 `business_resolution_config_v1`。飞书自建应用补充 `actor` 后转发给 `resolution_autopilot`；来源巡检标识、目标、观测配置和可比性上下文不得丢失；“查看解决单”按钮只携带已存在解决单的 URL。

为便于 Coordinator 建单时复核，创建按钮值应一并携带列表快照中可用的 `culprit`、`release`、`environment`、`fingerprint`、`risk_score`、`evidence_summary`、`evidence_source`、`snapshot_at`、`detail_snapshot`、`detail_fetched_at`、`analysis_summary` 和 `analysis_confidence`；不可用字段省略，不得填造。`evidence_summary` 只保留脱敏、短文本事实，不放完整堆栈、IP 或用户标识。快照只是触发上下文，不是已确认根因；Coordinator 仅在快照无效时使用自己的 Sentry MCP 对对应 Issue 读取详情/代表性事件后再写入解决单。详情不可用时保留快照并标记“证据不足”。

## 发送前一致性校验

在任何发送命令前，对最终 Card JSON 做结构校验：

- 当有 `N` 条全局候选（`N > 0`）且 `resolution_enabled: true` 时，必须恰好存在 `N` 个独立的解决单 `button` 元素；每条只能有一个，文本和行为根据状态选择“创建解决单” callback、“处理中”禁用或“查看解决单” open_url。callback 按钮的 `value.issue_id` 与对应条目唯一匹配，处理中按钮不得带 callback。
- 当 `resolution_enabled: false` 时，候选仍保留 Sentry 标题链接、上下文、指标、初判和建议，但解决单按钮数量必须为 0，且命令不得传入 `candidate-id`。
- 启用解决单时，不得因回调尚未配置、详情读取失败或某条初步研判证据不足而移除按钮；这些状态只影响按钮点击后的处理结果。Webhook 只读模式不生成按钮。
- `N = 0` 时发送明确的“暂无符合条件的未解决 Error Issue”空态，不生成空动作。
- 结构校验失败时返回 `blocked` 并保留巡检结果，禁止发送部分卡片或无按钮卡片。
- 状态更新时，必须在原卡片基础上只替换按钮对象，使用 `--operation update --previous-card <previous-card.json>` 校验更新前后的非按钮结构和视觉字段；校验失败时不得调用 Lark 更新接口。

## 发送

Webhook 通道使用 `curl --fail-with-body --silent --show-error --max-time <timeout_seconds>` 和 `Content-Type: application/json` 发送，验证 HTTP 成功且飞书响应 `code: 0`；不要重试。发送后删除临时文件，不输出 Webhook。

应用通道将最终卡片对象序列化为紧凑 JSON，通过以下命令发送（不再包裹一层 `msg_type`）：

```bash
lark-cli --profile <profile> im +messages-send \
  --as bot \
  --chat-id <chat_id> \
  --msg-type interactive \
  --content <card-json>
```

验证命令返回 `ok: true` 且包含 `message_id`。profile 缺失、授权/权限不足、机器人不在群内或发送失败时，保留巡检结果并报告 `blocked`；应用通道不得回退旧 Webhook，避免重复通知。

## Callback 透传契约（与 Lark bridge 对齐）

创建解决单 callback 的固定字段必须包括 `resolution_autopilot`、`resolution_config_version`、`target_assignee_type`、`target_assignee`、`source_inspection_autopilot_id`、`inspection_issue_id` 以及 Sentry 基础快照。`resolution_autopilot` 必须是精确 UUID `4833c3e9-b19b-4ace-bea2-bca87e4f2a01`，不能使用 `resolution_autopilot_Xx` 等变体。`source_inspection_autopilot_id` 必须精确等于当前巡检 Autopilot UUID，`inspection_issue_id` 必须精确等于当前巡检运行 Issue UUID；两者不得互换。启用影响观测时追加 `impact_trend_observation` 和创建基线所需的窗口字段 `time_window`、`filter`、`window_start`、`window_end`；`observation_timeout_days`、`post_fix_observation_days` 仅作为历史字段兼容读取，不参与基线判断或后续触发。Lark bridge 必须原样保留这些字段，缺失或值不匹配时阻断而不是只转发 Sentry 字段。
