---
name: inspection-autopilot-manager
description: Create and manage Inspector autopilots, reuse inspection logic across projects, decide whether a new inspection skill is necessary, and update scope with explicit before/after confirmation. Use when creating an inspection autopilot or changing which project an existing inspection runs against.
disable-model-invocation: true
---

# Inspection Autopilot Manager

An inspection has two layers:

- **Inspection definition**: `inspection_type` plus inline steps or a reusable skill.
- **Autopilot instance**: schedule, project scope, subscriber, and issue-creation settings.

Reuse one definition across many project-scoped Autopilot instances. Do not duplicate a skill only because scope changes.

## Required inputs

- Inspection goal and pass/fail signal.
- Initial project scope.
- Schedule and timezone, or `manual only`.
- Read-only or approved-execute behavior.
- Requester/subscriber.

Infer `inspection_type`, title, and whether a skill is needed. Do not ask for discoverable project or agent IDs.

## Decide whether to create a skill

Always create an Autopilot. Create a new skill only when at least one is true:

- Existing skills do not cover the inspection logic.
- The logic has meaningful branching, thresholds, domain rules, or a custom report schema.
- Multiple inspection types will reuse the logic.
- It calls external APIs/MCP or needs durable tool instructions.
- It may write files or execute dangerous commands and needs an auditable allowlist.

Otherwise use an **inline profile**: put the short, deterministic, read-only steps in the Autopilot description and register the `inspection_type` without creating a skill.

Decision order:

1. Exact existing skill match → reuse.
2. Simple deterministic read-only check → inline profile.
3. Everything else → create or extend a skill with `writing-great-skills`.

## Scope model

Multica Autopilot has one `--project` value. Treat each Autopilot instance as project-scoped.

- **Replace A with B**: update the existing instance.
- **Add B while keeping A**: create a sibling instance for B using the same inspection definition and trigger settings.
- **Remove B**: pause the B instance by default. Delete only when the human explicitly requests deletion.

Never modify inspection logic when only scope changes.

## Create workflow

1. Search registered inspection types and existing skills.
2. Choose `profile_mode: inline | skill-backed`.
3. Resolve the project ID with `multica project list --output json`.
4. Draft:
   - `inspection_type`
   - profile mode and skill reference, if any
   - Autopilot title
   - project scope
   - description
   - schedule/timezone
   - subscriber
5. Show the complete proposal and ask for one explicit approval.
6. After approval:
   - Create/register a skill only when `profile_mode: skill-backed`.
   - Register the `inspection_type`.
   - Create the Autopilot:

```sh
multica autopilot create \
  --title "<title> · <project>" \
  --description "<description>" \
  --agent "Inspector" \
  --mode create_issue \
  --project "<project-id>" \
  --subscriber "<requester>"
```

7. Add a schedule when provided:

```sh
multica autopilot trigger-add <autopilot-id> \
  --kind schedule \
  --cron "<cron>" \
  --timezone "<iana-timezone>"
```

8. Verify with `multica autopilot get <id> --output json`.

## Scope-change workflow

The human must name the Autopilot or provide its ID.

1. Read current state:

```sh
multica autopilot get <id> --output json
```

2. Resolve target project IDs.
3. Classify the request:
   - `replace`: A stops; B takes over.
   - `add`: A continues; B also runs.
   - `remove`: named project stops.
4. Show a concise before/after diff:

```text
Autopilot:
Inspection definition:
Scope action:
Before:
After:
Schedule changes: none | <exact change>
Subscriber changes: none | <exact change>
```

5. Ask for one explicit approval.
6. Execute:
   - `replace`:

```sh
multica autopilot update <id> \
  --title "<inspection title> · <project-b>" \
  --project "<project-b-id>" \
  --description "<same logic, scope updated>"
```

   - `add`: create a sibling Autopilot for B; copy mode, description logic, priority, subscribers, and triggers. Change only project-specific scope text and title suffix.
   - `remove`: pause the project-scoped instance:

```sh
multica autopilot update <id> --status paused
```

7. Verify every affected instance with `multica autopilot get`.

## Description contract

Every description includes:

```md
inspection_type: <type>
profile_mode: inline | skill-backed
profile_ref: inline@<version> | skill:<name>@<version>
scope_project: <project-name>
requested_by: <requester>

目标：<inspection goal and pass/fail signal>
步骤：<short inline steps, or "follow profile_ref">
输出：摘要 → findings → evidence → recommended actions → remaining decisions
规则：所有面向人的文本使用简体中文。危险动作必须先提案并取得人工确认。
```

Keep inspection logic identical across sibling instances. Scope-specific values belong only in `scope_project`, title, and project-bound parameters.

## Safety

- Only target `Inspector`.
- Only use `create_issue` mode.
- Refuse to update an existing Autopilot whose current agent or mode differs.
- No create/update/pause/delete before approval.
- Re-read state immediately before mutation; changed state requires a new proposal.
- Never replace subscribers, triggers, schedule, priority, or inspection logic during a scope-only change.
- Never fabricate IDs.
- Any partial failure stops the workflow and reports completed versus pending operations.

## Completion

Report:

- `inspection_type`
- profile mode/ref
- skill reused/created, or `none`
- Autopilot IDs
- project scope per instance
- trigger per instance
- subscriber per instance
- verification result
- remaining manual server-sync step
