# Sentry 环境读取 Reference

仅在第 2 轮已确认 Sentry project 后读取。本 Reference 定义如何通过 Sentry MCP
解析每个项目的生产环境实际名称；项目列表、匹配和其他资源发现仍由
`resource-discovery.md` 负责。

## 能力目标

输入一个已从 `mico` project 列表确认的 `project_slug`，输出该项目用于巡检查询的精确
`environment` 字符串，保留 Sentry 原始大小写。用户侧的“生产环境”只是默认语义，不
直接写入 `production`。

Sentry project slug 是本流程唯一需要的项目定位标识。环境读取不依赖 numeric project ID，
也不要求用户提供内部 ID。

## 只读调用契约

优先使用已接入的 Sentry MCP 环境列表能力。MCP 工具名称可以不同，但调用参数必须等价
于：

```text
organization: mico
project_slug: <verified-project-slug>
visibility: all
resource: project environments
```

其 REST 语义为：

```text
GET /api/0/projects/mico/<verified-project-slug>/environments/?visibility=all
```

官方接口返回项目环境列表，每项至少包含：

```text
name: <original-environment-name>
isHidden: <boolean>
```

项目元数据调用不得修改环境可见性，不输出或保存 token、cookie 或其他凭据。若 MCP
支持按 URL 读取资源，使用上述 endpoint；不要因为工具名称不是 `environment` 就跳过
可用的通用资源读取能力。

## 能力探测顺序

在报告“能力不可用”前，按以下顺序探测一次：

1. 查找 Sentry MCP 的项目环境列表能力；
2. 若没有专用方法，查找支持指定只读 endpoint 的通用 Sentry 资源能力；
3. 若仍没有环境列表能力但支持项目详情读取，读取：

   ```text
   GET /api/0/projects/mico/<verified-project-slug>/
   ```

   仅把详情中的非空 `defaultEnvironment` 作为“项目默认环境”候选；它不是完整环境
   列表，来源必须标记为 `project_default`。
4. 若项目级环境列表和项目详情能力均不可用，但 `search_issues` 支持省略
   `environment`，为该 project 执行一次“环境探针”：

   ```text
   organization: mico
   project_slug: <verified-project-slug>
   query: is:unresolved level:error
   time_window: 24h
   environment: omitted
   ```

   只读取 Issue 摘要中的 `environment` 字段，不读取详情、不排序、不做错误分析；同一
   project 只执行一次。该探针只作为环境观测证据，不伪装成项目元数据。
5. 若环境探针成功但摘要没有 `environment`，且返回了可定位的 Issue，则按返回顺序调用
   `get_sentry_resource` 读取 Issue 详情，直到处理完探针结果，或已发现两个不同的生产
   环境候选。详情回退只提取顶层 `environment`、`tags` 中的
   `["environment", "<value>"]` 和 `_dsc.environment`，不做错误分析、不把详情写入
   结果。该来源标记为 `issue_detail_observed`。
6. 探针或详情回退没有生产候选、相关能力未暴露，或用户需要确认唯一原始值时，返回
   `needs-info`，请用户提供该 project 的实际生产环境名称。只有 MCP 调用发生权限拒绝、
   超时或不可解析的硬错误，且没有可用回退时，才返回 `blocked`。

环境探针和 Issue 详情返回的近期环境都不是项目元数据，只能作为明确标注来源的回退证据；
本地样例不能替代本 Reference 的解析结果。探针不得为了寻找环境而改用 `environment: prod`
或 `environment: production` 进行猜测。

## 结果归一化

对每个 project 单独处理，不把不同 project 的环境名称合并：

1. 从环境列表提取非空 `name`；若来源是环境探针，则从 Issue 摘要提取非空
   `environment`；若来源是详情回退，则按顶层 `environment`、`tags` 的 environment
   项、`_dsc.environment` 顺序提取非空值，均保留原始大小写；
2. 将名称转为小写后，只有等于 `prod` 或 `production` 的项才是生产环境候选；
3. 若环境列表没有生产候选，再检查 `project_default` fallback；
4. 不把 `prod`、`Prod`、`Production` 仅按大小写合并成一个字符串。

结果状态：

```text
resolved:
  environment: <exact-original-name>
  source: environment_list | project_default | issue_query_observed | issue_detail_observed | user_confirmed

ambiguous:
  candidates: [<exact-original-name>, ...]

needs-info:
  reason: no production environment candidate or user confirmation required

blocked:
  reason: Sentry MCP environment/detail capability unavailable or unreadable
```

`project_default` 只有在 `defaultEnvironment` 忽略大小写后等于 `prod` 或 `production`
时才能作为生产环境候选；其他默认值不能被改写成生产环境，也不能回退到全部环境。
环境探针和详情回退同样只接受返回值中忽略大小写等于 `prod` 或 `production` 的候选，
并保留原始大小写。它们没有候选时返回 `needs-info`，不把 `production` 当作默认查询值。

## 用户确认规则

- `resolved`：自动采用精确环境值，并在方案中显示来源，例如
  “生产环境（实际值：`Prod`，来源：环境探针）”。
- 同一 project 有多个生产候选：列出原始名称，返回 `needs-info`，让用户选择。
- 没有生产候选：返回 `needs-info`，说明项目未发现 `prod` / `production` 环境，不猜测
  环境名称。
- 自动读取没有得到唯一候选，或相关能力未暴露：返回 `needs-info`，请用户提供原始环境名
  （例如 `Prod`、`prod` 或 `Production`）；用户确认后标记 `source: user_confirmed`。
- MCP 调用发生权限拒绝、超时或不可解析的硬错误，且没有可用回退：返回 `blocked`，说明
  缺少哪种只读能力；不要写成“Sentry 没有环境数据”，也不要要求用户手填内部标识。

只有所有已确认 Sentry project 都得到 `resolved`，或所有歧义都得到用户确认后，才可
进入方案确认和 Autopilot 创建。
