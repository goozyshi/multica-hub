---
name: branch-mr-safety
description: Enforce safe branch and merge-request workflow for Planner, Coordinator, Builder, and Reviewer. Use whenever creating implementation issues, planning branches, prototype branches, work branches, opening MRs, reviewing MRs, merging planning MRs, or deciding branch targets.
---

# Branch MR Safety

Use this skill for any branch or MR operation.

## Branch Model

Implementation uses one baseline, one integration branch, and a workflow-specific set of role-owned side branches:

```text
base_branch -> source_branch
                    |-> planning_branch  (workflow: planned)
                    |-> work_branch      (workflow: planned | fast-path)
```

- `base_branch`: baseline branch. Default: `main`.
- `source_branch`: feature or hotfix branch that collects work.
- `planning_branch`: Planner-owned docs-only branch created from `source_branch`; used only by `workflow: planned`.
- `work_branch`: Builder-owned branch created from `source_branch`. In `workflow: planned`, `source_branch` must contain `approved_plan_ref`; in `workflow: fast-path`, it must contain the latest authorized source only.

MR stages depend on the workflow:

```text
planned:
  Planning MR: planning_branch -> source_branch
  Builder MR: work_branch -> source_branch
  Final MR: source_branch -> final_mr_target

fast-path:
  Builder MR: work_branch -> source_branch
  Final MR: source_branch -> final_mr_target
```

- `planning_mr_target` must equal `source_branch` when `workflow: planned`; it is `not-required` for `workflow: fast-path`.
- `builder_mr_target` must equal `source_branch`.
- `final_mr_target` defaults to `test`.
- Planner creates only the Planning MR in `workflow: planned`.
- Builder creates only the Builder MR.
- Coordinator merges the Planning MR when required and creates the Final MR after the required reviews and human confirmations.
- Planning MRs must preserve the exact approved planning head in `source_branch` history. Use a merge commit; squash is forbidden.

## Required Issue Fields

Every implementation issue must include:

```md
repo:
workflow: planned | fast-path
base_branch:
source_branch:
source_branch_status:
parent_issue_key:
planning_branch:
planning_mr_target:
approved_plan_ref:
issue_key:
work_branch:
builder_mr_target:
final_mr_target:
```

Do not dispatch Builder or start implementation if any field is missing, unset, or inconsistent.

Workflow rules:

- `workflow: planned` requires `planning_branch`, `planning_mr_target`, and an exact `approved_plan_ref`.
- `workflow: fast-path` skips Planner, Planning MR, and planning approval. Set `planning_branch`, `planning_mr_target`, and `approved_plan_ref` to `not-required`.
- `workflow: fast-path` is only for a small, clear, single-slice change with explicit acceptance criteria and no unresolved product decision.
- Both workflows still require the immutable `spec_ref` used by Reviewer. `fast-path` does not permit issue text, chat text, or a floating MR to replace it.
- Coordinator selects and records `workflow`; Builder must not change it.

`repo` may be any unambiguous repository identifier:

- Multica project name.
- Repository name.
- Remote URL.

If the workspace or issue context exposes exactly one configured project/repository, Coordinator or Planner may infer `repo` from that project. Do not ask for a repo address in that case.

Allowed `source_branch_status` values:

- `create_if_missing`: new feature or hotfix branch. Coordinator creates it from latest `base_branch` before Planner starts. Builder never creates it for an approved-plan workflow.
- `must_exist`: existing integration, feature, or hotfix branch. If remote `source_branch` does not exist, Builder must stop and report a blocker.

## Visibility Rules

Branch/MR fields are internal control-plane data.

- Planner proposes branch intent in the Ticket plan packet when `workflow: planned`.
- Coordinator resolves branch fields, preserves approval evidence when required, and includes the workflow and verified `approved_plan_ref` (or `not-required`) in Builder dispatch packets.
- Builder must use them to create branches and MRs safely.
- Reviewer must use them to verify branch and MR safety.
- Normal user-facing summaries should not list `base_branch`, `source_branch`, `source_branch_status`, `planning_branch`, `planning_mr_target`, `approved_plan_ref`, `work_branch`, `builder_mr_target`, or `final_mr_target`.
- User-facing summaries may say `Branch safety checked`.
- Show detailed branch/MR fields only when the user asks, a blocker occurs, a safety risk exists, or a human decision is required.

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

Planner planning branch:

```text
agent/<parent-issue-key>-plan
agent/<parent-issue-key>-plan-rN
```

Use `-rN` for a replacement planning branch, where `N` is a positive revision number. A changed Planning MR head still requires fresh approvals; the suffix does not preserve prior approval.

For `workflow: fast-path`, `planning_branch` must be `not-required`; the planning branch naming rules do not apply.

`issue_key` means the human-visible issue key, such as `MIC-338`.

- Use the visible Multica issue key.
- Do not use project ids.
- Do not use UUIDs.
- Do not use internal task ids.
- `work_branch` must start with `agent/<issue_key>-`.
- `planning_branch` must equal `agent/<parent_issue_key>-plan` or match `agent/<parent_issue_key>-plan-rN`.

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

These rules apply only to `workflow: planned`.

Planner owns only the planning branch, allowed planning-document commits, and docs-only Planning MR. Planner proposes branch fields in its packet; Coordinator validates them and is the only dispatcher.

If user does not specify a branch:

```md
repo: <repo name or remote URL>
base_branch: main
source_branch: feature/<short-slug> or feature/v<version>-<short-slug>
source_branch_status: create_if_missing
parent_issue_key: <visible parent issue key>
planning_branch: agent/<parent-issue-key>-plan
planning_mr_target: same as source_branch
approved_plan_ref: <exact approved Planning MR head SHA; unset until approved>
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
parent_issue_key: <visible parent issue key>
planning_branch: agent/<parent-issue-key>-plan
planning_mr_target: same as source_branch
approved_plan_ref: <exact approved Planning MR head SHA; unset until approved>
issue_key: <visible issue key>
work_branch: agent/<issue-key>-<short-slug>
builder_mr_target: same as source_branch
final_mr_target: test
```

If the work is an online/hotfix issue, use `hotfix/...`, not `feature/...`.

Planner receives the existing parent and planning child keys from Coordinator and uses the visible `parent_issue_key` for `planning_branch`. Planner may propose `work_branch` patterns, but Coordinator creates formal child issues and fills the final visible `issue_key` before dispatch. If the parent key or source branch is unavailable, stop and return `needs-info`; do not invent a branch name.

Planner may:

1. Verify `source_branch` exists at the Coordinator-authorized ref.
2. Create `planning_branch` from latest `source_branch`.
3. Edit and commit only these planning-document paths:
   - `docs/specs/**`
   - `CONTEXT.md`
   - `CONTEXT-MAP.md`
   - `docs/adr/**`
4. Push `planning_branch`.
5. Open Planning MR: `planning_branch -> source_branch`.

Planner must not:

- Merge the Planning MR.
- Modify production code, tests, build configuration, dependency manifests, generated code, or any path outside the docs-only whitelist.
- Create the Final MR.
- Treat an issue approval, branch name, MR number, or stale commit as approval of the current Planning MR head.

## Planning Approval and Coordinator Rules

These rules apply only to `workflow: planned`. A `workflow: fast-path` issue has no Planning MR or planning approval.

Planning approval is bound to the exact Planning MR head commit SHA:

```text
approved_plan_ref = exact Planning MR head SHA approved by humans
```

- Record the Planning MR identity, exact head SHA, immutable `spec_ref`, and Ticket plan reference at the human planning gate.
- Any push, rebase, force-push, amend, merge-from-target, or other head change invalidates the planning approval.
- After a head change, the human must approve the new exact head before merge.
- Approval of one Planning MR never transfers to another MR, including an `-rN` replacement.

Only Coordinator may merge the Planning MR. After exact-head human approval, Coordinator must:

1. Fetch the current Planning MR and verify its identity.
2. Verify `planning_mr_target == source_branch` and the MR target is exactly `source_branch`.
3. Verify the current Planning MR head equals the exact approved SHA.
4. Verify every changed path is in the docs-only whitelist.
5. Verify the MR contains no production-code or unrelated changes.
6. Merge without squash. Use a merge commit so the exact `approved_plan_ref` remains in history.
7. Fetch updated `source_branch`.
8. Verify `approved_plan_ref` is an ancestor of, and therefore reachable from, `source_branch`.
9. Stop and report a blocker instead of dispatching Builder if any verification fails.

Coordinator owns Builder dispatch after the planning merge in `workflow: planned`, or after source-branch setup in `workflow: fast-path`. The dispatch must include the workflow and either the verified `approved_plan_ref` or `not-required`. Coordinator also owns Final MR creation after review and human confirmation.

## Builder Rules

Builder must follow this order:

1. Read all required branch fields, including `repo`, `workflow`, and `source_branch_status`.
2. Verify the selected repo matches `repo`.
3. Verify `builder_mr_target == source_branch`.
4. Fetch latest `base_branch`.
5. Check whether `source_branch` exists.
6. If `workflow: planned` and remote `source_branch` does not exist, stop and report a blocker; Coordinator must create it before Planner starts.
7. If `workflow: fast-path`, `source_branch_status = create_if_missing`, and remote `source_branch` does not exist, create it from latest `base_branch` and push it.
8. If `source_branch_status = must_exist` and remote `source_branch` does not exist, stop and report a blocker.
9. Fetch latest `source_branch`.
10. If `workflow: planned`, verify `approved_plan_ref` is present.
11. If `workflow: planned`, verify `approved_plan_ref` is an ancestor of, and therefore reachable from, latest `source_branch`. If `workflow: fast-path`, verify `approved_plan_ref = not-required`.
12. Create `work_branch` from that verified `source_branch`.
13. Commit only to `work_branch`.
14. Open Builder MR: `work_branch -> source_branch`.
15. For Builder MR, enabling "delete source branch after merge" is allowed and preferred because it deletes `work_branch`.
16. Do not open Final MR.

Builder must stop and return a blocker to Coordinator if:

- Required branch fields are missing.
- Selected repo does not match `repo`.
- `builder_mr_target != source_branch`.
- `workflow: planned` but `approved_plan_ref` is missing.
- `workflow: planned` but `approved_plan_ref` is not reachable from latest `source_branch`.
- `workflow: fast-path` but any planning field is not `not-required`.
- `issue_key` is missing or is not the visible issue key.
- `work_branch` does not start with `agent/<issue_key>-`.
- `work_branch` contains a UUID, project id, or internal task id instead of the visible issue key.
- `source_branch_status` is not `create_if_missing` or `must_exist`.
- `source_branch_status = must_exist` and remote `source_branch` does not exist.
- Tool defaults MR target to `main`.
- Tool cannot control MR target.
- MR diff includes unrelated changes.
- The operation would commit to `base_branch`, `source_branch`, `main`, release branches, or shared integration branches.

## Prototype Throwaway Branch Rules

A prototype used to answer a design question is disposable exploration, not implementation.

Recommended branch:

```text
agent/<issue-key>-prototype
```

- Create the prototype branch from the explicitly selected starting ref.
- Never merge it into `base_branch`, `source_branch`, `work_branch`, `main`, release branches, or shared integration branches.
- Never open a Builder MR or Final MR from it.
- Do not treat prototype commits as implementation or `approved_plan_ref`.
- Preserve and report the branch ref so humans and later agents can inspect the result.
- Reimplement approved behavior on a normal `work_branch`; do not merge or cherry-pick the prototype into the main branch chain.

## Final MR Rules

Final MR is:

```text
source_branch -> final_mr_target
```

- Coordinator creates it only after review and human confirmation.
- Do not delete `source_branch` after final merge.
- MR to `main` requires explicit human instruction.

## Reviewer Rules

Reviewer checks branch safety as part of review:

- For `workflow: planned`, Planning MR target is `source_branch`.
- For `workflow: planned`, Planning MR changed only docs-only whitelist paths.
- For `workflow: planned`, human planning approval names the exact current Planning MR head.
- For `workflow: planned`, Planning MR was merged by Coordinator without squash.
- For `workflow: planned`, `approved_plan_ref` is reachable from `source_branch`.
- For `workflow: planned`, `work_branch` was created from a `source_branch` containing `approved_plan_ref`.
- For `workflow: fast-path`, verify that planning fields are `not-required` and that the work branch was created from the latest authorized `source_branch`.
- Builder MR target is `source_branch`.
- Final MR was not created by Builder.
- Builder changed only `work_branch`.
- Builder MR delete-source-branch, if enabled, deletes only `work_branch`.
- No MR defaults to `main` unless explicitly approved.

## Role Boundaries

- Planner: owns the planning branch, docs-only commits, and Planning MR creation in `workflow: planned`. Its write whitelist is `docs/specs/**`, `CONTEXT.md`, `CONTEXT-MAP.md`, and `docs/adr/**`.
- Coordinator: owns workflow selection, source-branch setup, exact-head approval validation when planned, Planning MR merge when required, formal issue creation, Builder dispatch with the workflow and plan ref, reviewed Builder MR merge when policy allows, and Final MR creation after acceptance.
- Builder: implements only on `work_branch` created from verified `source_branch`, then creates only the Builder MR.
- Reviewer: verifies planning approval integrity, branch ancestry, path scope, implementation quality, and MR targets. Reviewer does not merge or create the Final MR.
- Prototype exception: Builder uses only `agent/<issue-key>-prototype`; it opens no MR, enters no review, and returns evidence to Coordinator.

## Examples

New feature, no version:

```md
repo: soulstar-dashboard
workflow: planned
base_branch: main
source_branch: feature/guild-invite
source_branch_status: create_if_missing
parent_issue_key: MIC-1
planning_branch: agent/MIC-1-plan
planning_mr_target: feature/guild-invite
approved_plan_ref: <exact approved Planning MR head SHA>
issue_key: MIC-12
work_branch: agent/MIC-12-guild-invite
builder_mr_target: feature/guild-invite
final_mr_target: test
```

New feature, versioned:

```md
repo: soulstar-dashboard
workflow: planned
base_branch: main
source_branch: feature/v2.42-guild-invite
source_branch_status: create_if_missing
parent_issue_key: MIC-1
planning_branch: agent/MIC-1-plan
planning_mr_target: feature/v2.42-guild-invite
approved_plan_ref: <exact approved Planning MR head SHA>
issue_key: MIC-12
work_branch: agent/MIC-12-guild-invite
builder_mr_target: feature/v2.42-guild-invite
final_mr_target: test
```

Existing feature branch:

```md
repo: soulstar-dashboard
workflow: planned
base_branch: feature/v2.42-pretty-ai
source_branch: feature/v2.42-pretty-ai
source_branch_status: must_exist
parent_issue_key: MIC-2
planning_branch: agent/MIC-2-plan
planning_mr_target: feature/v2.42-pretty-ai
approved_plan_ref: <exact approved Planning MR head SHA>
issue_key: MIC-13
work_branch: agent/MIC-13-invite-filter
builder_mr_target: feature/v2.42-pretty-ai
final_mr_target: test
```

Online hotfix:

```md
repo: soulstar-dashboard
workflow: planned
base_branch: main
source_branch: hotfix/v2.42-login
source_branch_status: create_if_missing
parent_issue_key: MIC-3
planning_branch: agent/MIC-3-plan
planning_mr_target: hotfix/v2.42-login
approved_plan_ref: <exact approved Planning MR head SHA>
issue_key: MIC-14
work_branch: agent/MIC-14-login
builder_mr_target: hotfix/v2.42-login
final_mr_target: test
```

Fast-path small change:

```md
repo: soulstar-dashboard
workflow: fast-path
base_branch: main
source_branch: feature/button-copy
source_branch_status: create_if_missing
parent_issue_key: MIC-4
planning_branch: not-required
planning_mr_target: not-required
approved_plan_ref: not-required
issue_key: MIC-15
work_branch: agent/MIC-15-button-copy
builder_mr_target: feature/button-copy
final_mr_target: test
```
