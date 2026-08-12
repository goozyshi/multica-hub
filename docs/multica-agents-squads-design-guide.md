# Multica Agent 与 Squad 设计参考

简要手册，供自定义 agent 与小队时使用。字段与行为以 [multica-ai/multica](https://github.com/multica-ai/multica) 官方文档为准。

官方入口：[Agents](https://multica.ai/docs/agents) · [Create an agent](https://multica.ai/docs/agents-create) · [Squads](https://multica.ai/docs/squads)

---

## 1. 核心概念

| 概念 | 是什么 | 不是什么 |
|------|--------|----------|
| **Agent** | 可复用的身份 + 执行配置；assign / @ / chat 时产生 task | 常驻进程；不是模型本身 |
| **Runtime** | 某台机器上的 agent CLI 执行环境 | Agent 的配置项之一 |
| **Squad** | 1 个 leader agent + 若干 member；提供路由层 | 新 agent；不会自动提高并发 |
| **Skill** | 可复用方法/知识包，claim 时注入 | 不能替代 agent instructions |

执行链路：`issue/chat/@` → **task 入队** → **runtime 上 agent CLI 跑** → 结果回写 issue。

---

## 2. Agent 字段清单

### 必填

| 字段 | 说明 |
|------|------|
| **Name** | 工作区内唯一；board、评论、assign 显示名 |
| **Runtime** | 绑定执行环境（Claude Code、Cursor Agent、Codex 等） |

### 行为与身份（设计重点）

| 字段 | 是否进 prompt | 说明 |
|------|--------------|------|
| **Instructions** | **是，每次 run** | 职责、边界、交付格式、escalation；**主行为契约** |
| **Description** | **否** | 给人看的简介；≤255 字符；列表/详情页展示 |
| **Avatar** | 否 | UI 展示；默认随机 emoji |
| **Skills** | 是（claim 时） | create 后单独绑定；workspace skills + 平台 builtin |

### 访问与执行

| 字段 | 默认 | 说明 |
|------|------|------|
| **Access** | Only me | `Only me` / `Entire workspace` / `Specific people`；决定谁能 assign、@、chat |
| **Model** | runtime 默认 | 可选覆盖 |
| **Thinking level** | runtime 默认 | 依 provider/model |
| **Service tier** | 空 |  mainly Codex |
| **Concurrency limit** | 6 | 范围 1–50；该 agent 并发 task 上限 |
| **Custom arguments** | `[]` | 追加 CLI 参数 |
| **Environment variables** | `{}` | 启动注入；敏感；create 后用 `agent env set` 维护 |
| **MCP** | null | JSON object；可用 `agent update` 更新 |
| **Integrations** | — | 如 Lark Bot（**1 Bot = 1 Agent**） |

### 常见误区

- 只写 `description`、空 `instructions` → agent 有名无行为。
- `description` 当 prompt 用 → 无效。
- `agent create` 不会自动绑 skill → 需 `agent skills add/set`。
- `custom_env` 不能通过 `agent update` 改 → 用 `agent env set`。

### CLI 最小示例

```bash
multica agent create \
  --name "Reviewer" \
  --runtime-id <runtime-id> \
  --description "审查前端 PR" \
  --instructions "只读 diff 和测试；以 issue 评论输出 findings，不直接改代码。"

multica agent skills add <agent-id> --skill-ids <skill-id>
```

---

## 3. Squad 字段清单

### 必填

| 字段 | 说明 |
|------|------|
| **Name** | 小队名；工作区内可不唯一 |
| **Leader** | 必须是 agent；issue assign 给 squad 时 **leader 先 claim** |

Leader 创建后自动成为 member。

### 可选

| 字段 | 是否进 prompt | 说明 |
|------|--------------|------|
| **Members** | roster | agent 或 human；可跨多个 squad |
| **Member role** | leader 可见 | 每人职责；**仅上下文，不自动触发** |
| **Squad instructions** | **leader 每次 run** | 路由规则、协作规范、escalation |
| **Description** | 否 | 卡片简介 |
| **Avatar** | 否 | UI |

### 平台自动注入（不可编辑）

issue **assign 给 squad** 时，leader 每次 run 额外收到：

1. **Squad Operating Protocol** — 硬编码：读 issue、改 `in_progress`、@ 分派、记 evaluation、分派后停手等。
2. **Squad Roster** — 成员 + 标准 `@mention` markdown（须用 roster 格式，plain `@name` 无效）。
3. **Squad Instructions** — 自定义路由规则。

### Squad 不做什么

- 不合并多个 agent 为一个。
- 不自动跑所有 member。
- 不加 agent 本身没有的能力。

### CLI 示例

```bash
multica squad create --name "Delivery" --leader coordinator

multica squad member add <squad-id> \
  --member-id <builder-id> --type agent \
  --role "implement / diagnose / review-fix"

multica squad update <squad-id> \
  --instructions "implement → Builder; review → Reviewer; 分派后停手，不自己实现。"
```

---

## 4. Agent vs Squad 怎么分工

| 场景 | 用 Agent | 用 Squad |
|------|----------|----------|
| 职责单一、assign 时已知执行者 | 直接 assign 专员 | — |
| 多个专长、创建 issue 时不知谁干 | — | assign 给小队，leader 路由 |
| 需要稳定 assignee 名（组而非个人） | — | assign 给小队 |
| 飞书 / Chat 入口 | 绑 Bot 到入口 agent | 飞书不支持 @squad |

**文本分工建议：**

- **Agent instructions** — 完整行为协议（gate、packet、边界、交付）。
- **Squad instructions** — 短路由摘要（谁干什么、何时 escalate）；**不要复制 agent instructions 全文**。
- **Description（agent / squad）** — 只给人看，写用途与版本追踪均可。

---

## 5. 推荐工作流（Issue-first + 飞书）

适用于：飞书用户只 @ 一个 Bot；内部多 agent 分工。

```
飞书 @ 入口 Agent（如 Coordinator Bot）
  → Chat 澄清 / /issue 建父 issue
  → 父 issue assign 给 Squad（稳定组 ownership + leader re-trigger）
  → 子 issue 类型已知时直接 assign 专员（Builder / Reviewer / Inspector）
  → 专员完成 → assign 回 Coordinator（或 @Coordinator + 状态评论）
  → Coordinator 决定 review / 验收 / 下一票
```

| 规则 | 内容 |
|------|------|
| 飞书入口 | 只 @ 入口 agent；1 Bot = 1 Agent |
| 唯一调度 | 只有 leader / Coordinator 建子 issue、assign、触发 review |
| 成员 handoff | Builder/Reviewer 完成只交回 Coordinator，不互 @ 循环 |
| 父票 | assign squad |
| 子票 | 直接 assign 对应 agent |

---

## 6. 设计检查清单

### 新建 Agent 前

- [ ] Runtime 在线且目标 CLI 已安装认证
- [ ] Name 工作区内唯一
- [ ] Instructions 覆盖：职责、禁止项、交付格式、blocker 处理
- [ ] Description 仅作简介（可含 instruction version 供人追踪）
- [ ] Access 设为团队可运行（若需多人 assign/@）
- [ ] Skills 是否需单独绑定
- [ ] Concurrency 是否需限制（默认 6）
- [ ] 敏感配置走 env / MCP，不进 instructions

### 新建 Squad 前

- [ ] Leader 是 dispatcher，不是默认干活的 builder
- [ ] Members 含所有会被 leader 分派的 agent
- [ ] 每个 member 有 role 描述
- [ ] Squad instructions 写路由规则，不重复 leader 完整 instructions
- [ ] 明确哪些 issue assign squad、哪些直接 assign 专员

### 上线前 smoke

- [ ] 无副作用 issue 验证 assign → claim → 评论 → handoff
- [ ] squad assign 时 leader 收到 protocol + roster
- [ ] 飞书 Bot 对话与 `/issue` 建票正常
- [ ] `agent get --output json` 核对 runtime、skills、instructions 已同步

---

## 7. 官方 CLI 速查

```bash
# Agent
multica agent create --name ... --runtime-id ...
multica agent get <id> --output json
multica agent skills add <id> --skill-ids ...
multica agent copy <source-id> [--runtime-id ... --model ...]
multica agent env set <id>   # 维护 custom_env

# Squad
multica squad create --name ... --leader ...
multica squad member add <id> --member-id ... --type agent --role "..."
multica squad update <id> --instructions "..."
multica squad list
```

---

## 8. 参考链接

- 仓库：https://github.com/multica-ai/multica
- Agent 创建契约（源码）：`server/internal/service/builtin_skills/multica-creating-agents/SKILL.md`
- CLI / Daemon：`CLI_AND_DAEMON.md`
- 飞书集成：https://multica.ai/docs/lark-bot-integration（Channels 文档）

本仓库的五 Agent 工作流约束见 [`docs/protocol.md`](protocol.md)；它是本地设计参考，不是 Multica 官方默认行为。
