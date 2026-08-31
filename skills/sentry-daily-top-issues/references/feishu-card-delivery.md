# 飞书卡片与发送 Reference

仅在当前 Autopilot 配置需要生成或发送飞书消息时读取本 Reference。它定义发送配置校验、interactive Card 2.0 结构、解决单按钮载荷、发送前一致性校验和通道发送方式；Sentry 查询、排序、详情研判和解决单幂等流程仍以主 Skill 为准。

## 执行门禁

- 先把 Autopilot 的发送配置规范化为 JSON，再生成 Card JSON；禁止直接拼接并发送未经校验的字符串。
- `inspection_url_template` 必须是原始 HTTPS URL，并且包含唯一占位符 `<Issue-ID>`。示例：`https://multica.micoplatform.com/mico-fe/issues/<Issue-ID>`。Markdown 链接、基础路径或无法替换为当前巡检 Issue ID 的值均为配置错误。
- 配置创建或修改时，先展示规范化配置、Card 预览和 validator 结果，取得一次明确的人类确认后才允许启用或测试发送。配置未变化且已确认的定时运行，可在 validator 通过后自动发送。
- 手工运行、配置变更后的首次运行或 validator 版本变更时，必须再次展示预览并等待确认；未确认不得发送。
- 使用仓库内的 `scripts/validate_feishu_card.py` 校验配置和最终 Card JSON。validator 返回非零、`status` 不是 `valid` 或 `decision` 不是 `ready-to-send` 时，结果为 `blocked` 或 `needs-info`，禁止发送。

```bash
python3 skills/sentry-daily-top-issues/scripts/validate_feishu_card.py \
  --card /tmp/sentry-card/card.json \
  --config /tmp/sentry-card/send-config.json \
  --candidate-count <N> \
  --candidate-id <Issue-ID> \
  --resolution-enabled true \
  --inspection-issue-id <巡检Issue-ID>
```

## 发送配置校验

配置解析和发送前都严格校验“发送配置”与通道匹配：

- `channel: feishu_webhook` 要求 `transport: curl`、`msg_type: interactive`、`max_cards_per_run: 1` 和有效 HTTPS `webhook_url`。发送给群机器人时，HTTP 请求体必须为外层 `{"msg_type":"interactive","card":<卡片对象>}`；`msg_type` 必须位于最外层。
- `channel: feishu_app` 要求 `transport: lark_cli`、`profile`、`as: bot`、`chat_id`、`msg_type: interactive` 和 `max_cards_per_run: 1`。使用运行环境中已配置并验证的 `lark-cli` profile；`chat_id` 必须是目标群的 `oc_...`。应用机器人必须已加入目标群并拥有发送消息权限。App Secret 只保存在 profile 中，不写入 Autopilot 描述、Issue 或卡片。
- 任一通道字段缺失、类型错误或值不合法时，输出字段级错误，结果为 `needs-info`，不得发起 Sentry 查询或发送消息。

## `global_top_n_markdown_v1` 卡片

使用飞书 interactive Card 2.0 JSON，保持简洁布局。根对象必须包含 `"schema": "2.0"`、`header` 和 `body.elements`；使用实际换行或独立元素，绝不把字符 `\\n` 显示给用户。

序列化要求：每条 Issue 必须拆成独立的 `body.elements`，不得把标题、元数据、指标、路由、初判和建议拼成一个字符串。错误标题使用 `tag:"markdown"` 元素承载 `**[<错误摘要>](<issue_url>)**`；指标和“初判/建议”使用独立的 `tag:"markdown"` 元素以承载加粗和颜色，项目/归因/版本/路由等元数据使用 `tag:"div"` + `text.tag:"plain_text"`，并设置 `text_color:"grey"`、`text_size:"notation"`、`text_align:"left"`。不得在 `plain_text` 中写入 `**`、Markdown 链接或转义换行。需要换行时使用独立元素或真实换行符 `\n`（解析后的 JSON 字符串），发送前检查最终 Card JSON 中不存在字面量 `\\n`、裸 `**` 或未解析的 Markdown 标记。

1. 红色标题栏：`【<scope>】Sentry 错误巡检 · <frequency> Top <display_top_n>`；`frequency` 根据 `time_window` 推导（`24h` 为“每日”，`7d` 为“每周”，其他值直接显示时间窗），不得写死业务名或周期。
2. 一行摘要：`<environment> · 近 <time_window> · <总 Error Issue 数> 条未解决`；环境缺失时省略，不重复展示 Top 数量。
3. 按全局排名展示 `display_top_n` 条，每条使用独立的文本块和细分隔线，不重复展示各组 Top N。
4. 每条按示例使用独立文本块（按钮作为独立元素，不计入正文行数），顺序固定：
   - `**[<错误摘要>](<issue_url>)**`，标题加粗并直接链接 Sentry Issue；不展示 `issue_id`、项目短码或其他机器标识。错误摘要优先取异常信息或 `issue_title`，缺失时才使用 `culprit`；若仍缺失使用“错误标题缺失”，绝不渲染内部字段名。
   - `<分组名> · <Web 前端|后端|客户端>（<初步判断|待核实>）`；不要展示“全局第 N 条”。
   - `**<event_count> 次** · <user_count> 用户 · 最近 <last_seen 相对时间> · <release>`；`release` 缺失时仅省略该字段，环境不在此行重复展示。
   - `路由：<页面路径>`；页面路径缺失时省略。
   - `初判：<可能原因>`；标签与正文同行，详情证据不足时在正文末尾标注“证据不足”。
   - `建议：<建议处理>`；标签与正文同行，使用纯文案，不添加色块或引用块。
5. 每条正文后立即追加一个 Card 2.0 操作按钮，不能集中到卡片底部；每条只能出现一次。按钮状态固定为三态，卡片背景保持白色：无未关闭解决单时为左对齐、`size:"small"`、`width:"default"`、`type:"primary"`（蓝色描边）的“创建解决单” callback 按钮；回调已受理但解决单尚未返回时为相同尺寸、`type:"default"`、`disabled:true`（灰色禁用）的“处理中…”按钮；已创建或复用解决单且有 URL 时为相同尺寸、`type:"default"`（正常默认样式）的“查看解决单” open_url 按钮。按钮不得包在居中容器内。Card 2.0 回调按钮必须使用 `behaviors`，不得使用旧式顶层 `value`。
6. `inspection_url_template` 存在且通过执行门禁校验时，将 `<Issue-ID>` 替换为当前巡检 Issue ID，在卡片底部提供一个独立的 Card 2.0 `button`，设置 `width:"fill"` 撑满整行，使用 `behaviors:[{"type":"open_url","default_url":"<resolved-url>"}]`；未配置模板时省略该按钮。配置存在但无效时按执行门禁返回 `blocked`，不得发送缺少该按钮的卡片。

视觉层级固定为：错误标题使用 `markdown` 的加粗蓝色链接；事件数和异常趋势使用低饱和红色或深红色强调；项目/归因/版本/路由等上下文使用 `div` 的灰色小字；“初判：”和“建议：”使用同一白色背景的 `markdown` 常规深色文案，标签可半粗但与正文同行；不使用色块、引用块、额外底色或高饱和颜色。除蓝、红、灰三种强调色外，不引入其他高饱和颜色。卡片不得放入完整堆栈、原始标签、长段落、重复列表、IP、用户标识或 Webhook。

按钮状态转换：点击“创建解决单”且回调已受理后，立即将同一位置更新为白底灰色禁用的“处理中…”；解决单创建或幂等复用成功后更新为白底默认样式的“查看解决单”并写入解决单 URL；创建失败时恢复为白底蓝色描边的“创建解决单”，并在该条建议后追加简短失败提示。

## Card 2.0 结构硬约束

- 根对象必须为 `schema: "2.0"`，`body.elements` 必须是数组；不得退回无 schema 的 1.0 混合结构。
- 每条候选必须有一个且仅有一个解决单操作 `tag: "button"`，且为独立左对齐的小按钮（`size:"small"`、`width:"default"`）；三态样式分别为：`type:"primary"` 蓝色描边的“创建解决单” callback、`type:"default"` 且 `disabled:true` 的灰色“处理中…”、`type:"default"` 正常样式的“查看解决单” open_url。callback 按钮的 `value.issue_id` 必须与该条目唯一匹配，处理中状态不得继续触发创建动作。
- Sentry 详情通过错误标题上的 Markdown 链接进入，不再为每条 Issue 添加“查看 Sentry”按钮；解决单状态按钮仍只允许一个。
- 不得因回调服务尚未配置、详情读取失败或某条初步研判证据不足而移除按钮；这些状态只影响按钮点击后的处理结果。
- `inspection_url_template` 有值且能解析时，卡片最后必须有一个 `width:"fill"` 的满宽“查看巡检单”按钮并带 `open_url` 行为；配置存在但解析失败时结果为 `blocked`，不得发送缺少该按钮的卡片。
- 卡片元素数不得超过 200；任一结构或动作校验失败，结果为 `blocked`，不得发送部分卡片或无按钮卡片。

## 解决单动作载荷

每个“创建解决单”按钮的 `value` 必须包含 `action: create_sentry_resolution`、`sentry_org`、`project`、`issue_id`、`issue_title`、`issue_url`、`event_count`、`user_count`、`first_seen`、`last_seen`、`group` 和按 `dedupe_key` 生成的去重键。飞书自建应用补充 `actor` 后转发给 `resolution_autopilot`；“查看解决单”按钮只携带已存在解决单的 URL。

为便于 Coordinator 建单时复核，创建按钮值应一并携带列表快照中可用的 `culprit`、`release`、`environment`、`fingerprint`、`risk_score`、`evidence_summary`、`evidence_source`、`snapshot_at`、`detail_snapshot`、`detail_fetched_at`、`analysis_summary`、`analysis_confidence` 和 `inspection_issue_id`；不可用字段省略，不得填造。`evidence_summary` 只保留脱敏、短文本事实，不放完整堆栈、IP 或用户标识。快照只是触发上下文，不是已确认根因；Coordinator 仅在快照无效时使用自己的 Sentry MCP 对对应 Issue 读取详情/代表性事件后再写入解决单。详情不可用时保留快照并标记“证据不足”。

## 发送前一致性校验

在任何发送命令前，对最终 Card JSON 做结构校验：

- 当有 `N` 条全局候选（`N > 0`）且 `resolution_enabled: true` 时，必须恰好存在 `N` 个独立的解决单 `button` 元素；每条只能有一个，文本和行为根据状态选择“创建解决单” callback、“处理中”禁用或“查看解决单” open_url。callback 按钮的 `value.issue_id` 与对应条目唯一匹配，处理中按钮不得带 callback。
- 不得因回调尚未配置、详情读取失败或某条初步研判证据不足而移除按钮；这些状态只影响按钮点击后的处理结果。
- `N = 0` 时发送明确的“暂无符合条件的未解决 Error Issue”空态，不生成空动作。
- 结构校验失败时返回 `blocked` 并保留巡检结果，禁止发送部分卡片或无按钮卡片。

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
