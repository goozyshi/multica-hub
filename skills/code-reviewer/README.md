# Code Reviewer

面向 AI Agent 的结构化代码审查 Skill。以高级工程师视角进行审查，覆盖架构设计、安全性、性能和代码质量。

## 功能特性

- **SOLID 原则** - 检测 SRP、OCP、LSP、ISP、DIP 违规
- **安全扫描** - XSS、注入攻击、SSRF、竞态条件、权限缺陷、密钥泄露
- **性能分析** - N+1 查询、CPU 热点、缓存缺失、内存问题
- **错误处理** - 异常吞没、异步错误、边界缺失
- **边界条件** - Null 处理、空集合、Off-by-one、数值溢出
- **清理规划** - 识别死代码并制定安全删除方案

## 使用方式

安装完成后，直接运行：

```
/code-reviewer
```

Skill 会自动审查当前 git 变更。

## 工作流程

1. **预检** - 通过 `git diff` 确定变更范围
2. **SOLID + 架构** - 检查设计原则
3. **清理候选** - 查找死代码 / 未使用代码
4. **安全扫描** - 漏洞检测
5. **代码质量** - 错误处理、性能、边界条件
6. **输出** - 按严重程度分级 (P0-P3)
7. **确认** - 实施修复前征求用户意见

## 严重程度

| 等级 | 级别     | 处理方式                 |
| ---- | -------- | ------------------------ |
| P0   | Critical | 必须阻止合并             |
| P1   | High     | 合并前应修复             |
| P2   | Medium   | 当前修复或创建 follow-up |
| P3   | Low      | 可选优化                 |

## 目录结构

```
code-reviewer/
├── SKILL.md                      # Skill 主定义文件
├── agents/
│   └── agent.yaml                # Agent 接口配置
└── references/
    ├── solid-checklist.md        # SOLID 异味检查清单
    ├── security-checklist.md     # 安全与可靠性清单
    ├── code-quality-checklist.md # 错误处理、性能、边界条件
    └── removal-plan.md           # 代码清理规划模板
```

## 参考资料

每份清单提供详细的检查提示和反模式说明：

- **solid-checklist.md** - SOLID 违规 + 常见代码异味
- **security-checklist.md** - OWASP 风险、竞态条件、加密、供应链安全
- **code-quality-checklist.md** - 错误处理、缓存策略、N+1 查询、Null 安全
- **removal-plan.md** - 安全删除 vs 延期删除及回滚方案

## License

MIT
