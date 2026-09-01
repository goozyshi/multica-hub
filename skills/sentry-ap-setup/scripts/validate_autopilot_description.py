#!/usr/bin/env python3
"""Validate a generated Sentry inspection Autopilot description.

This validator is dependency-free and runs before any Autopilot write. It
checks the machine-readable Markdown contract, branch-specific fields, and
the generated dedupe-key template without printing secret values.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


SECTIONS = {
    "基本信息": "basic",
    "巡检配置": "inspection",
    "解决单配置（business_resolution_config_v1）": "resolution",
    "发送配置": "send",
}

ALLOWED_FIELDS = {
    "basic": {
        "business_name",
        "scope_project",
        "inspection_type",
        "profile_mode",
        "profile_ref",
    },
    "inspection": {
        "sentry_org",
        "source",
        "time_window",
        "filter",
        "environment",
        "sort",
        "display_top_n",
        "layout",
        "timezone",
    },
    "resolution": {
        "resolution_enabled",
        "resolution_autopilot",
        "allowed_projects",
        "dedupe_key",
        "target_assignee_type",
        "target_assignee",
        "priority_mapping",
        "impact_trend_observation",
        "observation_timeout_days",
        "post_fix_observation_days",
    },
    "send": {
        "channel",
        "transport",
        "msg_type",
        "max_cards_per_run",
        "profile",
        "as",
        "chat_id",
        "webhook_url",
    },
}

REQUIRED_FIELDS = {
    "basic": {
        "business_name",
        "scope_project",
        "inspection_type",
        "profile_mode",
        "profile_ref",
    },
    "inspection": {
        "sentry_org",
        "source",
        "time_window",
        "filter",
        "environment",
        "sort",
        "display_top_n",
        "layout",
        "timezone",
    },
    "resolution": {"resolution_enabled"},
    "send": {"channel", "transport", "msg_type", "max_cards_per_run"},
}

FIELD_RE = re.compile(r"^-\s+([a-z][a-z0-9_]*):\s*(.*)$")
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
CHAT_ID_RE = re.compile(r"^oc_[A-Za-z0-9]+$")
PLACEHOLDER_RE = re.compile(r"<[^>]+>|\{\{[^}]+\}\}")
CRON_FIELD_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))


class Validation:
    def __init__(self) -> None:
        self.errors: list[dict[str, str]] = []

    def add(self, code: str, message: str, path: str) -> None:
        self.errors.append({"code": code, "message": message, "path": path})


def section_for_heading(heading: str) -> str | None:
    if heading in SECTIONS:
        return SECTIONS[heading]
    if heading.startswith("解决单配置（"):
        return "resolution"
    return None


def parse_description(
    description: str,
    validator: Validation,
) -> tuple[dict[str, dict[str, str]], list[tuple[str, str, str]]]:
    fields = {section: {} for section in ALLOWED_FIELDS}
    groups: list[tuple[str, str, str]] = []
    section: str | None = None
    in_group_table = False

    for line_number, raw_line in enumerate(description.splitlines(), 1):
        line = raw_line.strip()
        if line.startswith("## ") and not line.startswith("### "):
            heading = line[3:].strip()
            section = section_for_heading(heading)
            in_group_table = False
            if section is None:
                validator.add(
                    "unknown_section",
                    "Autopilot 描述包含未知二级区块",
                    f"line:{line_number}",
                )
            continue

        if line.startswith("### "):
            in_group_table = (
                section == "inspection" and line[4:].strip() == "项目分组"
            )
            continue

        if in_group_table and line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) != 3:
                if not all(set(cell) <= {"-", ":", " "} for cell in cells):
                    validator.add(
                        "invalid_project_group_row",
                        "项目分组表格必须包含分组、项目、Top N 三列",
                        f"line:{line_number}",
                    )
                continue
            if cells == ["分组", "项目", "Top N"] or all(
                set(cell) <= {"-", ":", " "} for cell in cells
            ):
                continue
            groups.append((cells[0], cells[1], cells[2]))
            continue

        match = FIELD_RE.fullmatch(line)
        if not match:
            continue
        key, value = match.groups()
        if section is None:
            validator.add(
                "field_outside_section",
                f"字段 {key} 不属于任何规范配置区块",
                f"line:{line_number}",
            )
            continue
        if key not in ALLOWED_FIELDS[section]:
            validator.add(
                "unknown_field",
                f"区块中不允许字段 {key}",
                f"{section}.{key}",
            )
            continue
        if key in fields[section]:
            validator.add(
                "duplicate_field",
                f"字段 {key} 重复出现",
                f"{section}.{key}",
            )
            continue
        fields[section][key] = value.strip()

    return fields, groups


def required_fields(
    fields: dict[str, dict[str, str]],
    validator: Validation,
) -> None:
    for section, keys in REQUIRED_FIELDS.items():
        for key in sorted(keys):
            if not fields[section].get(key):
                validator.add(
                    "missing_required_field",
                    f"缺少必填字段 {key}",
                    f"{section}.{key}",
                )


def expect_value(
    values: dict[str, str],
    section: str,
    key: str,
    expected: str,
    validator: Validation,
) -> None:
    actual = values.get(key)
    if actual is not None and actual != expected:
        validator.add(
            "invalid_field_value",
            f"{key} 必须为 {expected}",
            f"{section}.{key}",
        )


def validate_positive_integer(
    values: dict[str, str],
    section: str,
    key: str,
    validator: Validation,
) -> None:
    value = values.get(key)
    if value is None:
        return
    if not value.isdigit() or int(value) <= 0:
        validator.add(
            "invalid_positive_integer",
            f"{key} 必须是正整数",
            f"{section}.{key}",
        )


def validate_concrete_value(
    value: str | None,
    path: str,
    validator: Validation,
) -> None:
    if value and PLACEHOLDER_RE.search(value):
        validator.add(
            "unresolved_placeholder",
            "生成的 Autopilot 描述不得保留占位符",
            path,
        )


def valid_https_url(value: str | None) -> bool:
    if not value or any(char.isspace() for char in value):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def valid_cron_field(value: str, minimum: int, maximum: int) -> bool:
    for term in value.split(","):
        if not term:
            return False
        base, separator, step = term.partition("/")
        if separator and (not step.isdigit() or int(step) <= 0):
            return False
        if base in {"*", "?"}:
            continue
        if "-" in base:
            bounds = base.split("-")
            if len(bounds) != 2 or not all(bound.isdigit() for bound in bounds):
                return False
            start, end = (int(bound) for bound in bounds)
            if start > end or start < minimum or end > maximum:
                return False
            continue
        if not base.isdigit() or not minimum <= int(base) <= maximum:
            return False
    return True


def valid_cron(value: str | None) -> bool:
    if not value:
        return False
    fields = value.split()
    return len(fields) == 5 and all(
        valid_cron_field(field, minimum, maximum)
        for field, (minimum, maximum) in zip(fields, CRON_FIELD_RANGES)
    )


def validate_groups(
    groups: list[tuple[str, str, str]],
    validator: Validation,
) -> None:
    if not groups:
        validator.add(
            "missing_project_groups",
            "巡检配置必须至少包含一个项目分组",
            "inspection.project_groups",
        )
        return
    for index, (group, project, top_n) in enumerate(groups):
        path = f"inspection.project_groups[{index}]"
        if not group or not project:
            validator.add(
                "empty_project_group",
                "项目分组的分组名和 Sentry project 不能为空",
                path,
            )
        if not top_n.isdigit() or int(top_n) <= 0:
            validator.add(
                "invalid_group_top_n",
                "项目分组 Top N 必须是正整数",
                f"{path}.top_n",
            )
        validate_concrete_value(project, f"{path}.project", validator)


def validate_branch_contract(
    fields: dict[str, dict[str, str]],
    groups: list[tuple[str, str, str]],
    validator: Validation,
) -> None:
    basic = fields["basic"]
    inspection = fields["inspection"]
    resolution = fields["resolution"]
    send = fields["send"]

    expect_value(
        basic,
        "basic",
        "inspection_type",
        "sentry-daily-top-issues",
        validator,
    )
    expect_value(basic, "basic", "profile_mode", "skill-backed", validator)
    expect_value(
        basic,
        "basic",
        "profile_ref",
        "skill:sentry-daily-top-issues",
        validator,
    )
    expect_value(inspection, "inspection", "sentry_org", "mico", validator)
    expect_value(inspection, "inspection", "source", "search_issues", validator)
    expect_value(inspection, "inspection", "sort", "freq", validator)
    expect_value(
        inspection,
        "inspection",
        "layout",
        "global_top_n_markdown_v1",
        validator,
    )

    validate_groups(groups, validator)
    validate_positive_integer(inspection, "inspection", "display_top_n", validator)

    timezone = inspection.get("timezone")
    if timezone:
        try:
            ZoneInfo(timezone)
        except Exception:
            validator.add(
                "invalid_timezone",
                "timezone 必须是有效的 IANA 时区",
                "inspection.timezone",
            )

    channel = send.get("channel")
    resolution_value = resolution.get("resolution_enabled")
    if resolution_value not in {"true", "false"}:
        validator.add(
            "invalid_resolution_enabled",
            "resolution_enabled 必须是 true 或 false",
            "resolution.resolution_enabled",
        )
    resolution_enabled = resolution_value == "true"

    expect_value(send, "send", "msg_type", "interactive", validator)
    expect_value(send, "send", "max_cards_per_run", "1", validator)

    if channel == "feishu_webhook":
        expect_value(send, "send", "transport", "curl", validator)
        if not send.get("webhook_url"):
            validator.add(
                "missing_branch_field",
                "Webhook 分支缺少必填字段 webhook_url",
                "send.webhook_url",
            )
        elif not valid_https_url(send["webhook_url"]):
            validator.add(
                "invalid_webhook_url",
                "Webhook 必须配置合法 HTTPS 地址",
                "send.webhook_url",
            )
        if resolution_enabled:
            validator.add(
                "webhook_resolution_enabled",
                "Webhook 只读分支的 resolution_enabled 必须为 false",
                "resolution.resolution_enabled",
            )
        for key in ("profile", "as", "chat_id"):
            if key in send:
                validator.add(
                    "unexpected_branch_field",
                    f"Webhook 分支不得携带 {key}",
                    f"send.{key}",
                )
    elif channel == "feishu_app":
        expect_value(send, "send", "transport", "lark_cli", validator)
        expect_value(send, "send", "profile", "sentry-notify", validator)
        expect_value(send, "send", "as", "bot", validator)
        for key in ("profile", "as", "chat_id"):
            if not send.get(key):
                validator.add(
                    "missing_branch_field",
                    f"飞书自建应用分支缺少必填字段 {key}",
                    f"send.{key}",
                )
        chat_id = send.get("chat_id")
        if chat_id and not CHAT_ID_RE.fullmatch(chat_id):
            validator.add(
                "invalid_chat_id",
                "chat_id 必须是 oc_... 格式",
                "send.chat_id",
            )
        for key in ("webhook_url",):
            if key in send:
                validator.add(
                    "unexpected_branch_field",
                    f"飞书自建应用分支不得携带 {key}",
                    f"send.{key}",
                )
    elif channel:
        validator.add(
            "invalid_channel",
            "channel 必须是 feishu_webhook 或 feishu_app",
            "send.channel",
        )

    resolution_required = {
        "resolution_autopilot",
        "allowed_projects",
        "dedupe_key",
        "target_assignee_type",
        "target_assignee",
        "priority_mapping",
        "impact_trend_observation",
        "observation_timeout_days",
        "post_fix_observation_days",
    }
    if resolution_enabled:
        for key in sorted(resolution_required):
            if not resolution.get(key):
                if key == "dedupe_key":
                    message = (
                        "缺少 dedupe_key；系统默认值为 project:issue_id，"
                        "生成阶段必须写入 Autopilot 描述"
                    )
                else:
                    message = f"启用解决单时缺少必填字段 {key}"
                validator.add("missing_resolution_field", message, f"resolution.{key}")

        if resolution.get("dedupe_key") and resolution["dedupe_key"] != "project:issue_id":
            validator.add(
                "invalid_dedupe_key",
                "dedupe_key 必须使用系统默认模板 project:issue_id",
                "resolution.dedupe_key",
            )
        if resolution.get("target_assignee_type") not in {"agent", "squad"}:
            validator.add(
                "invalid_target_assignee_type",
                "target_assignee_type 必须是 agent 或 squad",
                "resolution.target_assignee_type",
            )
        if resolution.get("target_assignee") and not UUID_RE.fullmatch(
            resolution["target_assignee"]
        ):
            validator.add(
                "invalid_target_assignee",
                "target_assignee 必须是有效 UUID",
                "resolution.target_assignee",
            )
        observation = resolution.get("impact_trend_observation")
        if observation not in {"enabled", "disabled"}:
            validator.add(
                "invalid_observation_config",
                "impact_trend_observation 必须是 enabled 或 disabled",
                "resolution.impact_trend_observation",
            )
        if observation == "enabled":
            validate_positive_integer(
                resolution,
                "resolution",
                "observation_timeout_days",
                validator,
            )
            validate_positive_integer(
                resolution,
                "resolution",
                "post_fix_observation_days",
                validator,
            )
        elif observation == "disabled" and any(
            resolution.get(key)
            for key in ("observation_timeout_days", "post_fix_observation_days")
        ):
            validator.add(
                "invalid_observation_config",
                "未启用影响趋势观测时不得携带观测窗口字段",
                "resolution.impact_trend_observation",
            )
    else:
        for key in resolution_required - {"resolution_enabled"}:
            if resolution.get(key):
                validator.add(
                    "unexpected_resolution_field",
                    f"未启用解决单时不得携带 {key}",
                    f"resolution.{key}",
                )

    concrete_fields = (
        ("basic", "business_name"),
        ("basic", "scope_project"),
        ("basic", "profile_ref"),
        ("inspection", "sentry_org"),
        ("inspection", "environment"),
        ("resolution", "resolution_autopilot"),
        ("resolution", "allowed_projects"),
        ("resolution", "dedupe_key"),
        ("resolution", "target_assignee"),
        ("send", "profile"),
        ("send", "chat_id"),
        ("send", "webhook_url"),
    )
    for section, key in concrete_fields:
        validate_concrete_value(fields[section].get(key), f"{section}.{key}", validator)


def validate_create_arguments(
    fields: dict[str, dict[str, str]],
    arguments: dict[str, str | None],
    validator: Validation,
) -> None:
    for key in ("title", "agent", "mode", "project_id", "subscriber", "cron", "timezone"):
        if not arguments.get(key):
            validator.add(
                "missing_create_argument",
                f"Autopilot 创建参数缺少 {key}",
                f"create.{key}",
            )

    for key in ("title", "agent", "project_id", "subscriber", "cron", "timezone"):
        validate_concrete_value(arguments.get(key), f"create.{key}", validator)

    if arguments.get("mode") and arguments["mode"] != "create_issue":
        validator.add(
            "invalid_create_argument",
            "Autopilot mode 必须为 create_issue",
            "create.mode",
        )
    if arguments.get("agent") and arguments["agent"] != "Inspector":
        validator.add(
            "invalid_create_argument",
            "Autopilot agent 必须为 Inspector",
            "create.agent",
        )
    if arguments.get("project_id") and not UUID_RE.fullmatch(arguments["project_id"]):
        validator.add(
            "invalid_create_argument",
            "Autopilot project 必须是有效 UUID",
            "create.project_id",
        )
    if arguments.get("cron") and not valid_cron(arguments["cron"]):
        validator.add(
            "invalid_create_argument",
            "Autopilot cron 必须是合法的五段式表达式",
            "create.cron",
        )
    description_timezone = fields["inspection"].get("timezone")
    create_timezone = arguments.get("timezone")
    if (
        description_timezone
        and create_timezone
        and description_timezone != create_timezone
    ):
        validator.add(
            "create_argument_mismatch",
            "创建参数 timezone 必须与 Autopilot 描述中的 timezone 一致",
            "create.timezone",
        )


def validate_description(
    description: str,
    create_arguments: dict[str, str | None],
) -> dict[str, Any]:
    validator = Validation()
    fields, groups = parse_description(description, validator)
    required_fields(fields, validator)
    validate_branch_contract(fields, groups, validator)
    validate_create_arguments(fields, create_arguments, validator)
    resolution_enabled = fields["resolution"].get("resolution_enabled") == "true"
    report: dict[str, Any] = {
        "status": "valid" if not validator.errors else "invalid",
        "decision": "ready-to-create" if not validator.errors else "needs-info",
        "errors": validator.errors,
        "normalized_defaults": (
            {"dedupe_key": "project:issue_id"} if resolution_enabled else {}
        ),
    }
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="校验 Sentry Autopilot 描述，不执行远端写入"
    )
    parser.add_argument("--description-file", required=True, help="Autopilot 描述文件")
    parser.add_argument("--title", help="Autopilot 标题")
    parser.add_argument("--agent", help="Autopilot 执行 Agent")
    parser.add_argument("--mode", help="Autopilot 执行模式")
    parser.add_argument("--project-id", help="Autopilot 所属 Multica project UUID")
    parser.add_argument("--subscriber", help="Autopilot 订阅人")
    parser.add_argument("--cron", help="Autopilot schedule cron")
    parser.add_argument("--timezone", help="Autopilot schedule timezone")
    parser.add_argument("--output", choices=("json",), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        description = Path(args.description_file).read_text(encoding="utf-8")
    except FileNotFoundError:
        report = {
            "status": "invalid",
            "decision": "needs-info",
            "errors": [
                {
                    "code": "missing_file",
                    "message": "Autopilot 描述文件不存在",
                    "path": args.description_file,
                }
            ],
            "normalized_defaults": {},
        }
        print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
        return 1
    except OSError:
        report = {
            "status": "invalid",
            "decision": "needs-info",
            "errors": [
                {
                    "code": "read_error",
                    "message": "无法读取 Autopilot 描述文件",
                    "path": args.description_file,
                }
            ],
            "normalized_defaults": {},
        }
        print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
        return 1

    report = validate_description(
        description,
        {
            "title": args.title,
            "agent": args.agent,
            "mode": args.mode,
            "project_id": args.project_id,
            "subscriber": args.subscriber,
            "cron": args.cron,
            "timezone": args.timezone,
        },
    )
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0 if report["status"] == "valid" else 1


if __name__ == "__main__":
    sys.exit(main())
