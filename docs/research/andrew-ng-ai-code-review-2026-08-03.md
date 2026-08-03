# 吴恩达（Andrew Ng）与 AI Code Review（截至 2026-08-03）

## 结论

用户给出的关键词最可能指向 DeepLearning.AI 于 **2026-07-29** 公告的新短课 **《AI Code Review》**：标题完全匹配，且距本次调研仅 5 天。[官方公告](https://community.deeplearning.ai/t/new-course-enroll-in-ai-code-review/894220)  
但必须修正归因：课程由 **Qodo 的 Nnenna Ndukwe** 主讲并与 Qodo 合作，不是吴恩达授课；官方页面也没有说明吴恩达参与编写或亲自背书。[课程主页](https://www.deeplearning.ai/courses/ai-code-review)

吴恩达本人确实公开讲过与 AI code review 高度相关的通用方法：Reflection、独立批评者、工具化测试、evals/error analysis，以及 agentic coding、开发者反馈、外部反馈三层循环。这些能解释课程工作流的理论背景，但没有一手证据证明《AI Code Review》的每项建议来自吴恩达本人。[Reflection 原文](https://www.deeplearning.ai/the-batch/agentic-design-patterns-part-2-reflection) · [三循环原文](https://www.deeplearning.ai/the-batch/three-key-loops-for-building-great-software)

## 归因边界

### 吴恩达本人明确表达

1. **Reflection：生成、批评、改写、重复。** 吴恩达建议让 LLM 检查已生成代码的 correctness、style、efficiency，给出建设性批评，再结合旧代码和反馈重写；可重复此循环。[原文](https://www.deeplearning.ai/the-batch/agentic-design-patterns-part-2-reflection)
2. **批评不能只靠模型内省。** 可让 agent 运行单元测试等工具，以外部结果检查代码；也可拆成生成 agent 与批评 agent，让不同角色对话改进结果。[原文](https://www.deeplearning.ai/the-batch/agentic-design-patterns-part-2-reflection)
3. **三层软件反馈循环。** Agentic coding loop 依据产品规格和可选 evals 写代码、测试、迭代；developer feedback loop 由开发者检查产品并修订方向或规格；external feedback loop 用 alpha、生产数据、A/B 测试等校验产品方向。[2026-06-26 原文](https://www.deeplearning.ai/the-batch/three-key-loops-for-building-great-software) · [吴恩达个人站日期](https://www.andrewng.org/writing)
4. **Human-in-the-loop 仍必要。** 吴恩达认为人通常比当前 AI 掌握更多用户和业务上下文；只要人知道 AI 不知道的信息，就需要人把知识注入系统。[三循环原文](https://www.deeplearning.ai/the-batch/three-key-loops-for-building-great-software)
5. **用 evals 和错误分析驱动改进。** 他主张先快速做原型、人工检查少量输出，再针对真实失败模式建立数据集和指标；指标可为代码实现的客观指标，也可为 LLM-as-judge，并需持续调整。[2025-10-16 原文](https://www.deeplearning.ai/the-batch/improve-agentic-performance-with-evals-and-error-analysis-part-1)

### DeepLearning.AI 课程/组织内容

以下是《AI Code Review》课程主张，讲述者是 Nnenna Ndukwe，不能写成“吴恩达说”：

- **分层审查。** 编码 agent 完成后先做本地 pre-PR review，修掉低层问题；PR 阶段再交给独立、专门优化为发现风险的 review harness；最后由人处理高信号问题并决定是否合并。[Best Practices Part 1](https://learn.deeplearning.ai/courses/ai-code-review/lesson/79yprh/ai-code-review-best-practices-%E2%80%93-part-1)
- **生成与正式审查解耦。** 同一编码 agent 可做本地自查，但 PR gate 应使用独立 reviewer，降低生成者重复自身盲点的风险。[Best Practices Part 1](https://learn.deeplearning.ai/courses/ai-code-review/lesson/79yprh/ai-code-review-best-practices-%E2%80%93-part-1)
- **以需求和仓库上下文审查，而非只看 diff。** 输入应包括问题/方案、验收标准、Jira/GitHub issue、架构文档、组织规则、agent skills、相关仓库及下游影响，并要求发现项链接到证据。[Part 1](https://learn.deeplearning.ai/courses/ai-code-review/lesson/79yprh/ai-code-review-best-practices-%E2%80%93-part-1) · [Part 2](https://learn.deeplearning.ai/courses/ai-code-review/lesson/jcm17p/ai-code-review-best-practices-%E2%80%93-part-2)
- **按风险分流。** 低风险可由 agent 自动修复；中风险需要讨论；安全、数据完整性、系统行为等高风险项应阻断合并。人拥有最终判断、修复和合并责任。[Part 2](https://learn.deeplearning.ai/courses/ai-code-review/lesson/jcm17p/ai-code-review-best-practices-%E2%80%93-part-2)
- **把 review 变成可质询的对话。** 开发者应追问现实攻击面、下游影响和 diff 外的后果，而不是自动接受每条建议。[Part 2](https://learn.deeplearning.ai/courses/ai-code-review/lesson/jcm17p/ai-code-review-best-practices-%E2%80%93-part-2)
- **把重复问题沉淀为规则。** 对反复出现且确有价值的问题执行 “review → judge → codify/capture → reuse”，形成编码标准或 agent skill，并在未来审查中持续测量。[Part 2](https://learn.deeplearning.ai/courses/ai-code-review/lesson/jcm17p/ai-code-review-best-practices-%E2%80%93-part-2)
- **选择性上下文优于堆满上下文。** 课程实验用 AST 将 25 个文件、1126 行代码切成 99 个函数/类等 chunk，以 `text-embedding-3-large`、Chroma 和向量检索选 top 15；选择性上下文约 3500 字符，相比全量 31000 多字符减少 88.9%，并在该实验的 15 个 PR 上优于无上下文和全上下文。[Context Engine 课程实验](https://learn.deeplearning.ai/courses/ai-code-review/lesson/53tjuk/building-a-context-engine)
- **专门 reviewer ensemble。** 安全 agent 与代码库模式 agent 并行运行，结果去重汇总；同一 15-PR 教学实验中，ensemble 的 F1 为 71.1%，general reviewer 为 60.6%，表现为 precision 上升、recall 略降。[Specialized Agents 课程实验](https://learn.deeplearning.ai/courses/ai-code-review/lesson/jcm17m/building-specialized-code-review-agents)

### 本文归纳

把两组一手内容合并后，一个可落地但不应归因给吴恩达个人的流程是：

1. **先定义审查契约。** Issue 写清目的、非目标、验收标准、风险等级；仓库维护架构、编码规则、安全规则和跨仓依赖。
2. **编码 agent 自检。** 在开 PR 前运行测试、静态分析、类型检查，并按规格做 reflection；只自动修复可验证的低风险问题。
3. **独立 AI reviewer 审 PR。** reviewer 不复用生成角色；输入 diff、任务、选择性仓库上下文、规则和下游关系；输出必须包含 severity、代码位置、证据、影响与建议。
4. **专门 agent 并行。** 按实际风险拆 security、correctness、API compatibility、data migration、codebase pattern 等 reviewer；去重后统一排序。
5. **人做 merge gate。** 人核对业务意图、架构权衡、安全与数据风险，质询证据；AI 不单独批准高风险合并。
6. **持续评测。** 从历史缺陷和人工 review 建 gold set，至少跟踪 precision、recall、F1、每 PR 噪声数、关键缺陷漏报率；按错误分析更新检索、规则和 prompts，而非只换模型。

## 适用边界与风险

- **AI review 是第一遍审查和注意力路由，不是责任转移。** 课程明确保留人的最终判断；吴恩达也明确指出人的上下文优势。[课程](https://learn.deeplearning.ai/courses/ai-code-review/lesson/jcm17p/ai-code-review-best-practices-%E2%80%93-part-2) · [吴恩达](https://www.deeplearning.ai/the-batch/three-key-loops-for-building-great-software)
- **低 precision 会制造评论噪声，低 recall 会漏掉真实问题；无可追溯证据会降低可信度；陈旧规则会形成 context gap。** [课程概览](https://learn.deeplearning.ai/courses/ai-code-review/lesson/de16nq/overview-of-ai-code-review)
- **代码审查不等于 QA。** Review 主要检查增量源码的正确性、可维护性、标准和风险；端到端功能、用户行为、集成和发布准备仍需测试与 QA。[课程概览](https://learn.deeplearning.ai/courses/ai-code-review/lesson/de16nq/overview-of-ai-code-review)
- **同一模型自评存在相关性盲点。** 吴恩达把独立批评 agent 和工具反馈作为增强方法；课程进一步要求 PR 阶段使用独立 review harness。[Reflection](https://www.deeplearning.ai/the-batch/agentic-design-patterns-part-2-reflection) · [课程](https://learn.deeplearning.ai/courses/ai-code-review/lesson/79yprh/ai-code-review-best-practices-%E2%80%93-part-1)
- **课程数值只是教学实验，不是通用产品基准。** 样本仅 15 个 PR，仓库仅 25 文件/1126 行；课程页面未给出跨语言、跨仓库、统计显著性或独立复现实验。不能据此承诺生产提升 10.5 个 F1 百分点。[Context Engine](https://learn.deeplearning.ai/courses/ai-code-review/lesson/53tjuk/building-a-context-engine) · [Specialized Agents](https://learn.deeplearning.ai/courses/ai-code-review/lesson/jcm17m/building-specialized-code-review-agents)
- **选择性检索可能漏上下文。** 课程展示 precision/F1 改善，但 ensemble 实验同时出现 recall 略降；安全关键系统需保留确定性检查、人工审查和针对漏报的 evals。[Specialized Agents](https://learn.deeplearning.ai/courses/ai-code-review/lesson/jcm17m/building-specialized-code-review-agents)
- **上下文接入有权限与数据治理风险。** 课程建议接入 Jira、Confluence、代码库和相关仓库；团队实施时必须按最小权限处理源码、密钥、客户数据和跨仓访问。这一点是本文工程归纳，课程页面未给出完整安全部署方案。

## 对工程团队的最小落地方案

1. 选 30–100 个历史 PR，标注真实问题、严重级别与证据，作为初始 eval set。
2. CI 保留确定性门禁：测试、lint、类型检查、SAST、依赖与 secret 扫描。AI 结果不能替代这些检查。
3. 本地阶段运行生成 agent 自检；PR 阶段运行独立 reviewer，只允许低风险且测试可验证的自动修复。
4. 首批只做 2–3 个专门 reviewer，例如 security、API compatibility、repository conventions，避免 agent 数量先于 eval 证据膨胀。
5. 要求每条发现输出 `severity + location + rule/source + impact + proposed fix`；无证据项降级为建议，不阻断合并。
6. 每周分析误报和漏报；只有重复、稳定、经人确认的模式才固化为规则或 skill，并用保留集验证没有回归。

## 对应课程与工具

### 《AI Code Review》

- **定位：** DeepLearning.AI 中级短课，1 小时 4 分钟，8 个视频、3 个代码示例、1 个 PRO graded assignment；由 Nnenna Ndukwe 主讲、Qodo 合作。[课程主页](https://www.deeplearning.ai/courses/ai-code-review)
- **关键内容：** pre-PR review、独立 review harness、任务与仓库上下文、风险分级、规则/skills 记忆层、AST chunking、embeddings、vector search、专门 reviewer ensemble。[课程主页](https://www.deeplearning.ai/courses/ai-code-review)
- **工具定位：** 课程实验展示 Qodo 风格的独立 PR review 流程，但核心教学包含自建 context engine 和 reviewer ensemble，并非只教产品操作。[课程主页](https://www.deeplearning.ai/courses/ai-code-review)

### 《Agentic AI》

- **定位：** 吴恩达本人主讲的 DeepLearning.AI 中级课程，约 9 小时 55 分钟；不是 code review 专课。[课程主页](https://www.deeplearning.ai/courses/agentic-ai)
- **相关内容：** Reflection、tool use、planning、multi-agent collaboration、evals 和 error analysis；代码生成/批评只是这些通用 agentic patterns 的示例之一。[课程设计模式课节](https://learn.deeplearning.ai/courses/agentic-ai/lesson/rm9bg7/agentic-design-patterns) · [课程结语](https://learn.deeplearning.ai/courses/agentic-ai/lesson/qjhixk/conclusion)

## 证据强度与未确认项

### 强

- 《AI Code Review》的标题、讲师、合作方、时长、课程结构和方法：DeepLearning.AI 官方课程主页及公开课节全文。
- 课程公告日期 2026-07-29：DeepLearning.AI 官方社区 `Community-Team` 公告。
- 吴恩达关于 Reflection、测试工具、双 agent 批评、三层反馈循环、人类上下文优势、evals/error analysis 的观点：以 “Andrew” 署名的 The Batch 原文；三循环日期另由其个人站确认。

### 中

- “关键词最可能指向新课”：基于标题完全匹配与发布时间接近的归纳，不是用户已确认意图。
- 吴恩达的 agentic 方法与《AI Code Review》课程之间存在明显概念对应，但未找到官方材料声明课程直接由这些文章推导。

### 未确认

- 未找到一手证据证明吴恩达亲自设计、审核、授课或公开单独推荐《AI Code Review》。
- 未找到吴恩达本人针对 Qodo 产品的独立评价；不能把课程合作视为个人产品背书。
- DeepLearning.AI 的 Reflection 独立文章页面当前未展示发布日期；本文不写未经页面确认的精确日期。
- 课程实验未公开完整 benchmark 数据集、随机性控制、模型配置、统计显著性或独立复现；实验数值只按课程演示引用。

## 主要一手来源

- DeepLearning.AI《AI Code Review》课程主页：https://www.deeplearning.ai/courses/ai-code-review
- 课程发布公告（2026-07-29）：https://community.deeplearning.ai/t/new-course-enroll-in-ai-code-review/894220
- 课程 Overview：https://learn.deeplearning.ai/courses/ai-code-review/lesson/de16nq/overview-of-ai-code-review
- Best Practices Part 1：https://learn.deeplearning.ai/courses/ai-code-review/lesson/79yprh/ai-code-review-best-practices-%E2%80%93-part-1
- Best Practices Part 2：https://learn.deeplearning.ai/courses/ai-code-review/lesson/jcm17p/ai-code-review-best-practices-%E2%80%93-part-2
- Building a Context Engine：https://learn.deeplearning.ai/courses/ai-code-review/lesson/53tjuk/building-a-context-engine
- Building Specialized Code Review Agents：https://learn.deeplearning.ai/courses/ai-code-review/lesson/jcm17m/building-specialized-code-review-agents
- 吴恩达 Reflection 原文：https://www.deeplearning.ai/the-batch/agentic-design-patterns-part-2-reflection
- 吴恩达三循环原文：https://www.deeplearning.ai/the-batch/three-key-loops-for-building-great-software
- 吴恩达个人站 Writing（日期核验）：https://www.andrewng.org/writing
- 吴恩达 evals/error analysis 原文：https://www.deeplearning.ai/the-batch/improve-agentic-performance-with-evals-and-error-analysis-part-1
- DeepLearning.AI《Agentic AI》课程主页：https://www.deeplearning.ai/courses/agentic-ai
