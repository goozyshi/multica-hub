# Multica 最新功能调研（截至 2026-07-28）

## 结论

- 截止时间：2026-07-28 11:46（UTC+8）。
- 最新稳定版是 **v0.4.12**，发布于 2026-07-27；对应 tag commit 为 `e52b50658a66d09bffed126e34116ad826c03623`。[Release](https://github.com/multica-ai/multica/releases/tag/v0.4.12) · [Tag commit](https://github.com/multica-ai/multica/commit/e52b50658a66d09bffed126e34116ad826c03623)
- 截止调研时，`main` 已前进到 `77b309a5ac1d1dce7d94d05e99836519bb9fdbc9`，比 v0.4.12 多出 Usage 错误分析和统一草稿生命周期等变更；这些属于**未发布功能**，不能按稳定版承诺。[main commit](https://github.com/multica-ai/multica/commit/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9)
- 产品定位仍是开源 managed agents 平台：把本机 coding agent CLI 接入统一的 issue、chat、runtime、skill、autopilot 和 squad 协作层；Multica 负责调度，实际 agent 在用户 runtime 上执行。[README](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/README.md)

## 最新稳定功能：v0.4.12

### 1. GitHub PR 卡片显示实时 CI 与可合并状态

**功能与价值**

关联到 Multica issue 的 GitHub PR 卡片会分别显示检查通过/失败/运行中，以及 ready、conflict、blocked、behind 等可合并状态。用户可在 issue 内判断 PR 是否能合并，无需反复跳到 GitHub。快照由 GitHub API 提供；Webhook、打开卡片和周期刷新负责触发更新；GitHub 暂时不可用时保留带 stale 标记的最后快照。[官方文档](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/apps/docs/content/docs/github-integration.mdx#L20-L33) · [实现提交](https://github.com/multica-ai/multica/commit/ecce589867b949a5a1751a69685a0a61b76e606f)

**使用**

Cloud 已配置。自托管需创建 GitHub App，配置 `GITHUB_APP_SLUG`、`GITHUB_WEBHOOK_SECRET`；CI 与 mergeability 还要求 `GITHUB_APP_ID`、`GITHUB_APP_PRIVATE_KEY`，并授予 Pull requests、Checks、Commit statuses、Metadata 的只读权限，订阅 Pull request、Check suite、Check run、Status 事件。[自托管步骤](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/apps/docs/content/docs/github-integration.mdx#L97-L169)

**限制**

- 只扫描 PR 分支名、标题、正文中的 issue 编号；不扫描 commit message、PR comment，也不支持手工关联。[匹配限制](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/apps/docs/content/docs/github-integration.mdx#L48-L80)
- GitHub App 必须只授予读取权限；已有安装新增权限后，安装所有者还要批准 pending permission request，否则卡片没有 CI/merge 状态。[权限限制](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/apps/docs/content/docs/github-integration.mdx#L121-L133)
- 合并会把关联 issue 改为 Done；仅关闭不合并不会改 issue。Cancelled issue 不会被覆盖。[状态规则](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/apps/docs/content/docs/github-integration.mdx#L59-L72)

### 2. CLI 跨 runtime 复制 agent

**功能与价值**

`multica agent copy` 可从现有 agent 复制 instructions、描述、头像、参数、并发数、权限和 skills，生成新 agent；源 agent 不变。适合把验证过的 agent 配置迁移到另一台机器或另一种 runtime，减少重复配置。[官方内置操作文档](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/server/internal/service/builtin_skills/multica-creating-agents/SKILL.md#L69-L97) · [实现提交](https://github.com/multica-ai/multica/commit/3d4c5c7da2eb11b2238061a3bdc15639e8488275)

**使用**

```bash
multica agent copy <source-agent-id> --name "My Agent (copy)"
multica agent copy <source-agent-id> --runtime-id <target-runtime-id> --model <model>
```

同 runtime 默认继承 model、thinking level、service tier；跨 runtime 必须显式给 `--model`，可用 `--model ""` 接受目标 runtime 默认模型。`--no-skills` 可跳过 skill 复制。[命令契约](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/server/internal/service/builtin_skills/multica-creating-agents/SKILL.md#L79-L97)

**限制**

`custom_env`、`mcp_config`、`runtime_config` 涉及 secret 或机器本地状态，永不自动复制；需通过对应安全参数或复制后 `agent env set` 重新配置。[安全限制](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/server/internal/service/builtin_skills/multica-creating-agents/SKILL.md#L88-L97)

### 3. Lark/飞书入站图片与视频进入 agent 上下文

**功能与价值**

v0.4.12 将飞书/Lark 消息中的图片和视频转成 chat attachments，agent 不再只看到文本，可处理截图、照片和视频型输入。[v0.4.12 官方更新日志源码](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/apps/web/features/landing/i18n/zh.ts#L296-L321) · [实现提交](https://github.com/multica-ai/multica/commit/60048172a7d636c632ab46128824014c56e386e3)

**使用**

管理员在 Agent → Integrations 扫码绑定一个飞书 Bot；成员完成飞书身份绑定后，可私聊 Bot 或在群里 @ Bot。每个 Bot 只绑定一个 agent，回复通过实时卡片持续更新。[接入步骤](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/apps/docs/content/docs/lark-bot-integration.zh.mdx#L8-L35)

**限制**

- 仅工作区成员且完成身份绑定后可使用；群聊 Bot 只读 @ 它的那条消息，不监听整个群。[权限与群聊边界](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/apps/docs/content/docs/lark-bot-integration.zh.mdx#L17-L20) · [成员限制](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/apps/docs/content/docs/lark-bot-integration.zh.mdx#L39-L53)
- 自托管必须设置 base64 编码的 32 字节 `MULTICA_LARK_SECRET_KEY`；否则集成入口隐藏。[自托管限制](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/apps/docs/content/docs/lark-bot-integration.zh.mdx#L68-L87)

### 4. 图片附件预览支持平移/缩放；项目选择器可搜索

图片预览支持 pan/zoom，便于检查大截图和局部细节；项目选择器增加搜索与最大高度，长项目列表更易用。这两项是 Web/Desktop 共享界面改进，无额外安装或服务端配置。[v0.4.12 更新日志](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/apps/web/features/landing/i18n/zh.ts#L296-L307) · [图片预览提交](https://github.com/multica-ai/multica/commit/a964c5229d166dd71d39bdbdc2e97a4283264658) · [项目选择器提交](https://github.com/multica-ai/multica/commit/ef69c3d4a3e5aee3e881e478923c570779b173c9)

### 5. v0.4.12 的可靠性改进

稳定版还修复了：名字含空格时的 @mention 搜索、quick-create 真实错误原因、重复操作的 409/coalesced 处理、issue 列表重连后的同步、Codex session pointer、桌面 inline media、取消 Claude 任务时清理整个进程组、Kiro 大历史图片导致的 resume 失败。这些主要减少假失败、残留进程和无法恢复的会话。[Release changelog](https://github.com/multica-ai/multica/releases/tag/v0.4.12)

## 紧邻稳定版的重要能力

### 6. Claude Opus 5 与持久开发服务交付（v0.4.11）

agent 创建时可选择 Claude Opus 5；该模型不是默认值，需显式选择。Multica 允许 agent 在用户明确要求时，把本地开发/测试服务作为交付物保留到任务结束后，但必须先验证 readiness、把日志持久化、记录 PID/profile，并给出 URL、日志和停止方式；无 supervisor 时只能承诺 best-effort。[v0.4.11 更新日志](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/apps/web/features/landing/i18n/zh.ts#L323-L335) · [Opus 5 实现](https://github.com/multica-ai/multica/commit/e30776dd9b4bfe175c7f9dee6ac0b273797b3f45) · [持久服务约束实现](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/server/internal/daemon/execenv/runtime_config_sections.go#L71-L98)

持久服务例外不适用于测试、构建、CI polling、monitor 或其他尚欠结果的后台任务。[边界](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/server/internal/daemon/execenv/runtime_config_sections.go#L94-L99)

### 7. 自托管 Forgejo/Gitea/GitLab 集成（v0.4.10）

自托管 Multica 可按 workspace 连接 Forgejo、Gitea 或 GitLab。PR/MR 可按 issue 编号自动关联、显示 CI，并在满足 closing keyword 且没有其他 open 关联 PR 时把 issue 改为 Done；可与 GitHub 并用。[官方文档](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/apps/docs/content/docs/vcs-integration.zh.mdx#L8-L18) · [v0.4.10 更新日志](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/apps/web/features/landing/i18n/zh.ts#L337-L363)

该功能仅限自托管部署，默认关闭；必须设置 `MULTICA_VCS_INTEGRATION_ENABLED=true` 和 base64 32 字节 `MULTICA_VCS_SECRET_KEY`，再配置 provider read token 与 webhook。Webhook secret 只显示一次。[安装与限制](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/apps/docs/content/docs/vcs-integration.zh.mdx#L20-L74)

## main 已合并、尚未发布

### 8. Usage 页错误/失败分析

Usage 页新增 Errors 趋势、错误率、失败类别/原因和按 agent 分解，可回答“哪里失败、谁失败”，并将未真正启动就过期的队列任务纳入失败统计。价值是把用量页面从成本观察扩展为运行质量诊断。[实现提交](https://github.com/multica-ai/multica/commit/4d0475ce89c046a8b1ee93db0501d0843ef102c2) · [当前界面源码](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/packages/views/dashboard/components/dashboard-page.tsx#L578-L617) · [后端统计语义](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/server/pkg/db/queries/task_usage.sql#L183-L191)

限制：这是 `main` 功能，不在 v0.4.12 tag 内；生产使用应等下一 release 或自行从源码构建。[v0.4.12 Release](https://github.com/multica-ai/multica/releases/tag/v0.4.12) · [功能提交](https://github.com/multica-ai/multica/commit/4d0475ce89c046a8b1ee93db0501d0843ef102c2)

### 9. 统一 issue/chat/comment 草稿与附件生命周期

创建 issue 的手工模式和 agent 模式改为同一逻辑草稿的独立槽位，共享 project、priority、due date、attachments。模式切换不再清空另一侧内容；附件上传状态被持久化，重载时未完成上传会标为 interrupted；草稿按 workspace 隔离并在登出时清理。价值是降低切换模式、关窗、重载导致的文字或附件丢失。[实现提交](https://github.com/multica-ai/multica/commit/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9) · [草稿数据模型](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/packages/core/issues/stores/draft-store.ts#L16-L44) · [持久化与清理](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/packages/core/issues/stores/draft-store.ts#L175-L249)

限制：同属 `main` 未发布功能；重载后浏览器没有原始文件 bytes，进行中的上传只能恢复为 interrupted，不能无损续传。[上传限制](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/packages/core/issues/stores/draft-store.ts#L38-L44)

## 安装与最短使用路径

### Cloud + 本地 runtime

```bash
# macOS / Linux
brew install multica-ai/tap/multica
multica setup
```

无 Homebrew 可运行官方 install script；Windows 可用 PowerShell installer。`multica setup` 完成 Cloud 配置、浏览器认证并启动 daemon。随后在 Settings → Runtimes 确认 runtime 在线，在 Settings → Agents 创建 agent，再创建 issue 并分配给它。[README 安装与上手](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/README.md#quick-install)

daemon 至少需要一个受支持的 agent CLI 在 `PATH` 上；默认每 3 秒 poll、15 秒 heartbeat，最大并发任务 20。实际模型/API entitlement 仍由各 provider CLI 与用户账号决定。[CLI/Daemon 文档](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/CLI_AND_DAEMON.md#L94-L188)

### 自托管

```bash
curl -fsSL https://raw.githubusercontent.com/multica-ai/multica/main/scripts/install.sh | bash -s -- --with-server
multica setup self-host
```

要求 Docker 与 Docker Compose。也可用 OCI Helm chart 部署到 Kubernetes；官方说明要求 Helm v3.13+（支持 `--take-ownership`）或 v4+、Ingress controller 和默认 StorageClass。[Self-host quick install](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/SELF_HOSTING.md#L15-L56) · [Kubernetes 前置条件](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/SELF_HOSTING.md#L162-L178)

生产环境应配置 Resend 邮件验证码；固定 `MULTICA_DEV_VERIFICATION_CODE` 只能用于 development/private testing，不得暴露到公网。[登录安全限制](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/SELF_HOSTING.md#L87-L97)

## README 建议修改点

1. **新增“Latest in v0.4.12”短节。** 突出 GitHub PR CI/mergeability、`multica agent copy`、Lark 图片/视频、图片 pan/zoom、project picker search；链接到 release 和具体文档。[v0.4.12 Release](https://github.com/multica-ai/multica/releases/tag/v0.4.12)
2. **补 `multica agent copy` 到 CLI 表。** 当前 README 的 CLI 表没有该稳定命令；需同时写明跨 runtime 必须显式选择 model、secret 不复制。[命令文档](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/server/internal/service/builtin_skills/multica-creating-agents/SKILL.md#L69-L97)
3. **同步 supported agents 清单。** 当前 README 与 `CLI_AND_DAEMON.md` 不一致；后者还列出 Gemini、Grok Build CLI、Qwen Code。以 daemon 当前探测实现/CLI 文档为准统一三处列表。[CLI supported agents](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/CLI_AND_DAEMON.md#L135-L157)
4. **修正 Autopilot webhook 表述。** README 宣称 cron、webhook、manual 均可触发，但当前 CLI 文档明确：仅 cron schedule 暴露，数据模型虽有 webhook/api kind，却没有触发它们的 server endpoint。README 应改成“cron + manual；webhook/API 尚未开放”，避免过度承诺。[README](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/README.md#features) · [CLI 限制](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/CLI_AND_DAEMON.md#L670-L732)
5. **在 GitHub integration 旁补自托管 Git providers。** 明确 Forgejo/Gitea/GitLab 仅对自托管 Multica 开放，需 feature flag、secret key、read token、webhook。[官方文档](https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/apps/docs/content/docs/vcs-integration.zh.mdx#L8-L74)
6. **不要把 main-only 两项写成已发布。** Usage Errors 与统一草稿可放“Coming next / on main”，或等下一 tag 后再进 Features。[Usage commit](https://github.com/multica-ai/multica/commit/4d0475ce89c046a8b1ee93db0501d0843ef102c2) · [Draft commit](https://github.com/multica-ai/multica/commit/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9)

## 主要一手来源

- 仓库：https://github.com/multica-ai/multica
- 最新稳定版：https://github.com/multica-ai/multica/releases/tag/v0.4.12
- README：https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/README.md
- 官方文档源码：https://github.com/multica-ai/multica/tree/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/apps/docs/content/docs
- CLI/Daemon 指南：https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/CLI_AND_DAEMON.md
- Self-host 指南：https://github.com/multica-ai/multica/blob/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9/SELF_HOSTING.md
- 2026-07-28 `main` HEAD：https://github.com/multica-ai/multica/commit/77b309a5ac1d1dce7d94d05e99836519bb9fdbc9
