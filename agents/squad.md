### Workspace policy

浪浪山只服务 SoulStar 业务。仓库别名与 canonical repository URL：

| Repo key       | 用途                         | Repository                                                             |
| -------------- | ---------------------------- | ---------------------------------------------------------------------- |
| `dashboard`    | Web dashboard                | `https://gitlab-vywrajy.micoworld.net/maidocha/web/maidocha-dashboard` |
| `mobile`       | Vue 3 内嵌 H5 页面与部分游戏 | `https://gitlab-vywrajy.micoworld.net/maidocha/web/maidocha-mobile`    |
| `game`         | Vue 2 游戏                   | `https://gitlab-vywrajy.micoworld.net/maidocha/web/maidocha-game`      |
| `official`     | SoulStar 官网                | `https://gitlab-vywrajy.micoworld.net/maidocha/web/maidocha-official`  |
| `dopa-web-pay` | 网页第三方充值               | `https://gitlab-vywrajy.micoworld.net/pay-web/dopa-web-pay`            |

Repo resolution：

- 用户明确指定 repo key 或 repository URL：使用用户指定值。
- 用户未指定 repo：默认使用 `dashboard`。
- 用户使用“dashboard”或“后台”且未给出冲突线索：解析为 `dashboard`。
- 用户指定的 repo key、URL、模块或上下文互相冲突：暂停并请求确认，不静默覆盖。
- Coordinator 必须把解析后的 `repo`、repo key 和 resolution source 写入 issue 与 dispatch packet。
- 成员只使用 dispatch packet 中的最终 `repo`，不得自行猜测或改写 repo。

### 协作规则

- Coordinator 是唯一 dispatcher、唯一用户入口和跨 Agent 状态 owner。
- 飞书/Chat 只用于前置澄清与对齐；父 issue 创建后，用户在 Multica Web 跟踪、评论、批准和验收。
- Coordinator 完成对齐后返回父 issue URL；issue 是后续唯一工作事实源。
- Chat 使用 Chat Brief：首行状态与动作，最多 3 个 grouped questions，详情进入 issue。
- 成员不得互相 assign、触发或建立循环 handoff。
- Coordinator 负责人工 gate、验收、review-fix budget 与 Final MR。
- Squad instructions 只包含短路由与本小队必要 workspace policy，不复制成员的完整 instructions。
- 使用平台注入的 Squad Operating Protocol 与 roster mention 格式。

### 路由

```text
implement | diagnose | prototype | review-fix → Builder
review → Reviewer
inspection → Inspector
```

### 所有权

- 父 requirement issue assign 给 Squad，由 Coordinator leader claim。
- Coordinator 在父 requirement issue 上完成澄清、spec、Ticket plan 和 planning approval。
- execution child issue 按 work type assign 给 Builder。
- review child issue assign 给 Reviewer。
- inspection child issue assign 给 Inspector。
- 所有成员完成或阻塞后只 handoff 给 Coordinator。

### 完成条件

每个 issue 都有明确 owner；work type 已路由到对应成员；成员结果已回到 Coordinator；Coordinator 决定下一步或记录 blocker。
