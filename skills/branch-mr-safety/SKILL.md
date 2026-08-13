---
name: branch-mr-safety
description: Enforce safe branch and merge-request workflow for Planner, Builder, and Reviewer. Use whenever creating implementation issues, creating branches, opening MRs, reviewing MRs, or deciding branch targets.
---

# Branch MR Safety

Use this skill for any branch or MR operation.

## Branch Model

All implementation work uses three layers:

```text
base_branch -> source_branch -> work_branch
```

- `base_branch`: baseline branch. Default: `main`.
- `source_branch`: feature or hotfix branch that collects work.
- `work_branch`: Builder-owned branch where code changes happen.

MRs use two stages:

```text
Builder MR: work_branch -> source_branch
Final MR: source_branch -> final_mr_target
```

- `builder_mr_target` must equal `source_branch`.
- `final_mr_target` defaults to `test`.
- Builder creates only the Builder MR.
- Planner or human creates the Final MR after review and human confirmation.

## Required Issue Fields

Every implementation issue must include:

```md
repo:
base_branch:
source_branch:
source_branch_status:
issue_key:
work_branch:
builder_mr_target:
final_mr_target:
```

Do not start implementation if any field is missing or inconsistent.

`repo` may be any unambiguous repository identifier:

- Multica project name.
- Repository name.
- Remote URL.

If the workspace or issue context exposes exactly one configured project/repository, Planner may infer `repo` from that project. Do not ask for a repo address in that case.

Allowed `source_branch_status` values:

- `create_if_missing`: new feature or hotfix branch. If remote `source_branch` does not exist, Builder must create it from latest `base_branch`.
- `must_exist`: existing integration, feature, or hotfix branch. If remote `source_branch` does not exist, Builder must stop and report a blocker.

## Visibility Rules

Branch/MR fields are internal control-plane data.

- Planner must include them in internal Builder dispatch packets.
- Builder must use them to create branches and MRs safely.
- Reviewer must use them to verify branch and MR safety.
- Public Delivery context may show the repo key, `source_branch`, `final_mr_target`, and MR link.
- Keep `base_branch`, `source_branch_status`, `work_branch`, `builder_mr_target`, safety checks, and all raw packet fields agent-only.
- User-facing summaries may say `Branch safety checked`.

## Branch Naming

New feature work:

```text
feature/<short-slug>
feature/v<version>-<short-slug>
```

Production or online hotfix:

```text
hotfix/<short-slug>
hotfix/v<version>-<short-slug>
```

Builder work branch:

```text
agent/<issue-key>-<short-slug>
```

`issue_key` means the human-visible issue key, such as `MIC-338`.

- Use the visible Multica issue key.
- Do not use project ids.
- Do not use UUIDs.
- Do not use internal task ids.
- `work_branch` must start with `agent/<issue_key>-`.

Slug rules:

- 2-4 words.
- Lowercase kebab-case.
- Keep it short.
- If a source branch name already exists for unrelated work, add issue id:

```text
feature/v<version>-<issue-key>-<short-slug>
hotfix/v<version>-<issue-key>-<short-slug>
```

## Planner Rules

Planner decides branch fields before assigning Builder.

If user does not specify a branch:

```md
repo: <repo name or remote URL>
base_branch: main
source_branch: feature/<short-slug> or feature/v<version>-<short-slug>
source_branch_status: create_if_missing
issue_key: <visible issue key>
work_branch: agent/<issue-key>-<short-slug>
builder_mr_target: same as source_branch
final_mr_target: test
```

If user specifies an existing feature/hotfix branch:

```md
repo: <repo name or remote URL>
base_branch: <existing feature/hotfix branch>
source_branch: <existing feature/hotfix branch>
source_branch_status: must_exist
issue_key: <visible issue key>
work_branch: agent/<issue-key>-<short-slug>
builder_mr_target: same as source_branch
final_mr_target: test
```

If the work is an online/hotfix issue, use `hotfix/...`, not `feature/...`.

Planner must create or identify the child issue first, read its visible `issue_key`, then fill `work_branch` before assigning Builder. If the visible issue key is unavailable, stop and mark `needs-info`; do not invent a branch name.

## Builder Rules

Builder must follow this order:

1. Read all required branch fields, including `repo` and `source_branch_status`.
2. Verify the selected repo matches `repo`.
3. Verify `builder_mr_target == source_branch`.
4. Fetch latest `base_branch`.
5. Check whether `source_branch` exists.
6. If `source_branch_status = create_if_missing` and remote `source_branch` does not exist, create it from latest `base_branch` and push it.
7. If `source_branch_status = must_exist` and remote `source_branch` does not exist, stop and report a blocker.
8. Fetch latest `source_branch`.
9. Create `work_branch` from `source_branch`.
10. Commit only to `work_branch`.
11. Open Builder MR: `work_branch -> source_branch`.
12. For Builder MR, enabling "delete source branch after merge" is allowed and preferred because it deletes `work_branch`.
13. Do not open Final MR.

Builder must stop and ask human/Planner if:

- Required branch fields are missing.
- Selected repo does not match `repo`.
- `builder_mr_target != source_branch`.
- `issue_key` is missing or is not the visible issue key.
- `work_branch` does not start with `agent/<issue_key>-`.
- `work_branch` contains a UUID, project id, or internal task id instead of the visible issue key.
- `source_branch_status` is not `create_if_missing` or `must_exist`.
- `source_branch_status = must_exist` and remote `source_branch` does not exist.
- Tool defaults MR target to `main`.
- Tool cannot control MR target.
- MR diff includes unrelated changes.
- The operation would commit to `base_branch`, `source_branch`, `main`, release branches, or shared integration branches.

## Final MR Rules

Final MR is:

```text
source_branch -> final_mr_target
```

- Create only after explicit human authorization. Product acceptance occurs after the target environment is available.
- Do not delete `source_branch` after final merge.
- MR to `main` requires explicit human instruction.

## Reviewer Rules

Reviewer checks branch safety as part of review:

- Builder MR target is `source_branch`.
- Final MR was not created by Builder.
- Builder changed only `work_branch`.
- Builder MR delete-source-branch, if enabled, deletes only `work_branch`.
- No MR defaults to `main` unless explicitly approved.

## Examples

New feature, no version:

```md
repo: soulstar-dashboard
base_branch: main
source_branch: feature/guild-invite
source_branch_status: create_if_missing
issue_key: MIC-12
work_branch: agent/MIC-12-guild-invite
builder_mr_target: feature/guild-invite
final_mr_target: test
```

New feature, versioned:

```md
repo: soulstar-dashboard
base_branch: main
source_branch: feature/v2.42-guild-invite
source_branch_status: create_if_missing
issue_key: MIC-12
work_branch: agent/MIC-12-guild-invite
builder_mr_target: feature/v2.42-guild-invite
final_mr_target: test
```

Existing feature branch:

```md
repo: soulstar-dashboard
base_branch: feature/v2.42-pretty-ai
source_branch: feature/v2.42-pretty-ai
source_branch_status: must_exist
issue_key: MIC-13
work_branch: agent/MIC-13-invite-filter
builder_mr_target: feature/v2.42-pretty-ai
final_mr_target: test
```

Online hotfix:

```md
repo: soulstar-dashboard
base_branch: main
source_branch: hotfix/v2.42-login
source_branch_status: create_if_missing
issue_key: MIC-14
work_branch: agent/MIC-14-login
builder_mr_target: hotfix/v2.42-login
final_mr_target: test
```
