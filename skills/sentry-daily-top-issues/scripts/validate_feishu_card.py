#!/usr/bin/env python3
"""Validate a Sentry Feishu Card 2.0 payload before delivery.

The validator is intentionally dependency-free. It validates the normalized
Autopilot send configuration together with the rendered Card JSON. It never
sends a message and never prints secret values.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ISSUE_TITLE_RE = re.compile(
    r"^\*\*\[(?P<title>[^\]]+)\]\((?P<url>https://[^)\s]+)\)\*\*$"
)
CHAT_ID_RE = re.compile(r"^oc_[A-Za-z0-9]+$")
PLACEHOLDER_RE = re.compile(r"<[^>]+>")
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\([^)]+\)")
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

REQUIRED_CALLBACK_FIELDS = (
    "action",
    "sentry_org",
    "project",
    "issue_id",
    "issue_title",
    "issue_url",
    "event_count",
    "user_count",
    "first_seen",
    "last_seen",
    "group",
    "dedupe_key",
    "resolution_autopilot",
)

SENSITIVE_KEYS = {
    "ip",
    "uid",
    "user_id",
    "user_identifier",
    "user_email",
    "webhook",
    "webhook_url",
    "app_secret",
    "access_token",
    "auth_token",
    "stacktrace",
    "stack_trace",
    "full_stack",
    "raw_tags",
    "original_tags",
}


class CardValidation:
    def __init__(self) -> None:
        self.errors: list[dict[str, str]] = []

    def add(
        self,
        code: str,
        message: str,
        path: str,
        *,
        decision: str = "blocked",
    ) -> None:
        self.errors.append(
            {
                "code": code,
                "message": message,
                "path": path,
                "decision": decision,
            }
        )

    @property
    def decision(self) -> str:
        if any(error["decision"] == "needs-info" for error in self.errors):
            return "needs-info"
        return "blocked"


def read_json(path: str, validator: CardValidation, label: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        validator.add("missing_file", f"{label} 文件不存在", path, decision="needs-info")
    except json.JSONDecodeError as error:
        validator.add(
            "invalid_json",
            f"{label} 不是合法 JSON：第 {error.lineno} 行第 {error.colno} 列",
            path,
            decision="needs-info",
        )
    except OSError:
        validator.add("read_error", f"无法读取 {label}", path, decision="needs-info")
    return None


def non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_https_url(value: Any) -> bool:
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def text_content(element: Any) -> str:
    if not isinstance(element, dict):
        return ""
    content = element.get("content")
    if isinstance(content, str):
        return content
    text = element.get("text")
    if isinstance(text, str):
        return text
    if isinstance(text, dict) and isinstance(text.get("content"), str):
        return text["content"]
    return ""


def is_issue_title(element: Any) -> bool:
    return (
        isinstance(element, dict)
        and element.get("tag") == "markdown"
        and bool(ISSUE_TITLE_RE.fullmatch(text_content(element)))
    )


def is_sensitive_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9_]", "_", key.lower())
    return normalized in SENSITIVE_KEYS


def walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield child_path, key, child
            yield from walk(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, f"{path}[{index}]")


def validate_sensitive_content(
    card: Any,
    validator: CardValidation,
) -> None:
    for path, key, value in walk(card):
        if is_sensitive_key(key):
            validator.add(
                "sensitive_field",
                "卡片不得包含敏感字段",
                path,
            )
        if isinstance(value, str):
            if "\\n" in value:
                validator.add(
                    "escaped_newline",
                    "Card JSON 不得包含字面量 \\\\n",
                    path,
                )
            if IPV4_RE.search(value):
                validator.add(
                    "ip_exposure",
                    "卡片不得包含 IP 地址",
                    path,
                )
            if "open.feishu.cn/open-apis/bot/v2/hook/" in value:
                validator.add(
                    "webhook_exposure",
                    "卡片不得包含飞书 Webhook",
                    path,
                )

        if isinstance(value, dict) and value.get("tag") == "plain_text":
            content = text_content(value)
            if "**" in content or MARKDOWN_LINK_RE.search(content):
                validator.add(
                    "markdown_in_plain_text",
                    "plain_text 不得包含 Markdown 标记",
                    path,
                )


def resolve_inspection_url(
    template: Any,
    inspection_issue_id: str | None,
    validator: CardValidation,
) -> str | None:
    if template is None or template == "":
        return None
    if not non_empty_string(template):
        validator.add(
            "invalid_inspection_template",
            "inspection_url_template 必须是非空字符串",
            "$.inspection_url_template",
            decision="needs-info",
        )
        return None

    if "[" in template or "](" in template:
        validator.add(
            "markdown_inspection_template",
            "inspection_url_template 必须是原始 URL，不能是 Markdown 链接",
            "$.inspection_url_template",
            decision="needs-info",
        )
    if not valid_https_url(template.replace("<Issue-ID>", "placeholder")):
        validator.add(
            "invalid_inspection_template",
            "inspection_url_template 必须是合法 HTTPS URL",
            "$.inspection_url_template",
            decision="needs-info",
        )
    if "<Issue-ID>" not in template:
        validator.add(
            "missing_issue_placeholder",
            "inspection_url_template 必须包含 <Issue-ID>",
            "$.inspection_url_template",
            decision="needs-info",
        )
    placeholders = PLACEHOLDER_RE.findall(template)
    if any(placeholder != "<Issue-ID>" for placeholder in placeholders):
        validator.add(
            "unknown_url_placeholder",
            "inspection_url_template 只能使用 <Issue-ID> 占位符",
            "$.inspection_url_template",
            decision="needs-info",
        )
    if not non_empty_string(inspection_issue_id):
        validator.add(
            "missing_inspection_issue_id",
            "存在 inspection_url_template 时必须提供当前巡检 Issue ID",
            "$.inspection_issue_id",
            decision="needs-info",
        )
        return None
    if any(char.isspace() for char in inspection_issue_id) or "<" in inspection_issue_id:
        validator.add(
            "invalid_inspection_issue_id",
            "巡检 Issue ID 含非法字符",
            "$.inspection_issue_id",
            decision="needs-info",
        )
        return None

    resolved = template.replace("<Issue-ID>", inspection_issue_id)
    if "<" in resolved or ">" in resolved or not valid_https_url(resolved):
        validator.add(
            "unresolvable_inspection_url",
            "inspection_url_template 无法解析为合法巡检单 URL",
            "$.inspection_url_template",
        )
        return None
    return resolved


def validate_send_config(
    config: Any,
    validator: CardValidation,
    inspection_issue_id: str | None,
) -> tuple[dict[str, Any], str | None]:
    if not isinstance(config, dict):
        validator.add(
            "invalid_config",
            "发送配置必须是 JSON 对象",
            "$",
            decision="needs-info",
        )
        return {}, None

    send_config = config.get("send_config", config)
    if not isinstance(send_config, dict):
        validator.add(
            "invalid_send_config",
            "send_config 必须是 JSON 对象",
            "$.send_config",
            decision="needs-info",
        )
        return {}, None

    channel = send_config.get("channel")
    if channel not in {"feishu_webhook", "feishu_app"}:
        validator.add(
            "invalid_channel",
            "channel 必须是 feishu_webhook 或 feishu_app",
            "$.channel",
            decision="needs-info",
        )
    elif channel == "feishu_webhook":
        if send_config.get("transport") != "curl":
            validator.add(
                "invalid_transport",
                "feishu_webhook 必须使用 transport: curl",
                "$.transport",
                decision="needs-info",
            )
        if not valid_https_url(send_config.get("webhook_url")):
            validator.add(
                "invalid_webhook_url",
                "feishu_webhook 必须配置合法 HTTPS webhook_url",
                "$.webhook_url",
                decision="needs-info",
            )
    elif channel == "feishu_app":
        required_app_fields = {
            "transport": "lark_cli",
            "as": "bot",
            "msg_type": "interactive",
            "max_cards_per_run": 1,
        }
        for field, expected in required_app_fields.items():
            if send_config.get(field) != expected:
                validator.add(
                    "invalid_app_config",
                    f"feishu_app 的 {field} 必须为 {expected}",
                    f"$.{field}",
                    decision="needs-info",
                )
        if not non_empty_string(send_config.get("profile")):
            validator.add(
                "missing_lark_profile",
                "feishu_app 必须配置 profile",
                "$.profile",
                decision="needs-info",
            )
        if not CHAT_ID_RE.fullmatch(str(send_config.get("chat_id", ""))):
            validator.add(
                "invalid_chat_id",
                "chat_id 必须是纯 oc_... 值，不能附带群名称",
                "$.chat_id",
                decision="needs-info",
            )

    timeout = send_config.get("timeout_seconds")
    if timeout is not None and (
        isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0
    ):
        validator.add(
            "invalid_timeout",
            "timeout_seconds 必须是正整数",
            "$.timeout_seconds",
            decision="needs-info",
        )

    resolved_url = resolve_inspection_url(
        send_config.get("inspection_url_template"),
        inspection_issue_id,
        validator,
    )
    return send_config, resolved_url


def validate_callback_payload(
    button: dict[str, Any],
    validator: CardValidation,
    path: str,
    candidate_ids: set[str],
) -> None:
    behaviors = button.get("behaviors")
    if not isinstance(behaviors, list) or len(behaviors) != 1:
        validator.add(
            "invalid_callback_behaviors",
            "callback 按钮必须包含一个 behaviors 项",
            f"{path}.behaviors",
        )
        return
    behavior = behaviors[0]
    if not isinstance(behavior, dict) or behavior.get("type") != "callback":
        validator.add(
            "invalid_callback_behavior",
            "创建解决单按钮必须使用 callback behavior",
            f"{path}.behaviors[0]",
        )
        return
    if "value" not in behavior or not isinstance(behavior["value"], dict):
        validator.add(
            "missing_callback_value",
            "callback value 必须是对象",
            f"{path}.behaviors[0].value",
        )
        return

    value = behavior["value"]
    for field in REQUIRED_CALLBACK_FIELDS:
        if field not in value or value[field] in ("", None, []):
            validator.add(
                "missing_callback_field",
                f"创建解决单 payload 缺少 {field}",
                f"{path}.behaviors[0].value.{field}",
            )
    issue_id = value.get("issue_id")
    if candidate_ids and issue_id not in candidate_ids:
        validator.add(
            "unmatched_issue_id",
            "callback value.issue_id 不属于当前候选项",
            f"{path}.behaviors[0].value.issue_id",
        )
    if (
        non_empty_string(value.get("project"))
        and non_empty_string(value.get("issue_id"))
        and value.get("dedupe_key") != f"{value['project']}:{value['issue_id']}"
    ):
        validator.add(
            "invalid_dedupe_key",
            "dedupe_key 必须等于 project:issue_id",
            f"{path}.behaviors[0].value.dedupe_key",
        )
    if value.get("action") != "create_sentry_resolution":
        validator.add(
            "invalid_callback_action",
            "action 必须是 create_sentry_resolution",
            f"{path}.behaviors[0].value.action",
        )
    if not valid_https_url(value.get("issue_url")):
        validator.add(
            "invalid_issue_url",
            "issue_url 必须是合法 HTTPS URL",
            f"{path}.behaviors[0].value.issue_url",
        )


def validate_solution_button(
    button: Any,
    validator: CardValidation,
    path: str,
    candidate_ids: set[str],
) -> str:
    if not isinstance(button, dict):
        validator.add("invalid_button", "解决单按钮必须是对象", path)
        return "invalid"
    if button.get("tag") != "button":
        validator.add("invalid_button_tag", "解决单按钮 tag 必须是 button", path)
    if button.get("size") != "small" or button.get("width") != "default":
        validator.add(
            "invalid_button_dimensions",
            "解决单按钮必须是 size: small、width: default",
            path,
        )

    label = text_content(button.get("text"))
    button_type = button.get("type")
    disabled = button.get("disabled") is True
    if label == "创建解决单":
        if button_type != "primary" or disabled:
            validator.add(
                "invalid_create_button_style",
                "创建解决单按钮必须是未禁用的 primary",
                path,
            )
        validate_callback_payload(button, validator, path, candidate_ids)
        return "create"

    if label == "处理中…":
        if button_type != "default" or not disabled:
            validator.add(
                "invalid_processing_button_style",
                "处理中…按钮必须是 disabled 的 default",
                path,
            )
        behaviors = button.get("behaviors")
        if behaviors:
            if not isinstance(behaviors, list) or any(
                isinstance(item, dict) and item.get("type") == "callback"
                for item in behaviors
            ):
                validator.add(
                    "processing_callback",
                    "处理中…按钮不得继续携带 callback",
                    f"{path}.behaviors",
                )
        return "processing"

    if label == "查看解决单":
        if button_type != "default" or disabled:
            validator.add(
                "invalid_view_button_style",
                "查看解决单按钮必须是未禁用的 default",
                path,
            )
        behaviors = button.get("behaviors")
        if (
            not isinstance(behaviors, list)
            or len(behaviors) != 1
            or not isinstance(behaviors[0], dict)
            or behaviors[0].get("type") != "open_url"
            or not valid_https_url(behaviors[0].get("default_url"))
        ):
            validator.add(
                "invalid_view_behavior",
                "查看解决单按钮必须使用带合法 URL 的 open_url behavior",
                f"{path}.behaviors",
            )
        return "view"

    validator.add(
        "unknown_solution_button",
        "解决单按钮文本必须是创建解决单、处理中…或查看解决单",
        f"{path}.text",
    )
    return "invalid"


def validate_inspection_button(
    button: Any,
    expected_url: str,
    validator: CardValidation,
    path: str,
) -> None:
    if not isinstance(button, dict):
        validator.add("invalid_inspection_button", "巡检单按钮必须是对象", path)
        return
    button_text = button.get("text")
    if (
        button.get("tag") != "button"
        or button.get("width") != "fill"
        or not isinstance(button_text, dict)
        or button_text.get("tag") != "plain_text"
        or text_content(button_text) != "查看巡检单"
        or button.get("type") != "default"
        or button.get("size") != "small"
    ):
        validator.add(
            "invalid_inspection_button",
            "巡检单按钮必须是 default/small/fill 的独立按钮",
            path,
        )
    behaviors = button.get("behaviors")
    if (
        not isinstance(behaviors, list)
        or len(behaviors) != 1
        or not isinstance(behaviors[0], dict)
        or behaviors[0].get("type") != "open_url"
        or behaviors[0].get("default_url") != expected_url
    ):
        validator.add(
            "invalid_inspection_behavior",
            "巡检单按钮必须使用指向当前巡检 Issue 的 open_url behavior",
            f"{path}.behaviors",
        )


def validate_card(
    card: Any,
    validator: CardValidation,
    candidate_count: int,
    candidate_ids: set[str],
    resolution_enabled: bool,
    expected_inspection_url: str | None,
) -> None:
    if not isinstance(card, dict):
        validator.add("invalid_card", "Card JSON 必须是对象", "$")
        return
    if card.get("schema") != "2.0":
        validator.add("invalid_schema", '根对象 schema 必须是 "2.0"', "$.schema")
    if not isinstance(card.get("header"), dict):
        validator.add("missing_header", "根对象必须包含 header 对象", "$.header")
    body = card.get("body")
    elements = body.get("elements") if isinstance(body, dict) else None
    if not isinstance(elements, list):
        validator.add(
            "invalid_elements",
            "body.elements 必须是数组",
            "$.body.elements",
        )
        return
    if len(elements) > 200:
        validator.add(
            "too_many_elements",
            "Card 元素数不得超过 200",
            "$.body.elements",
        )

    validate_sensitive_content(card, validator)

    title_indexes = [
        index for index, element in enumerate(elements) if is_issue_title(element)
    ]
    if len(title_indexes) != candidate_count:
        validator.add(
            "candidate_count_mismatch",
            f"Card 标题候选数为 {len(title_indexes)}，预期 {candidate_count}",
            "$.body.elements",
        )
    if candidate_count > 0 and not title_indexes:
        validator.add(
            "missing_candidates",
            "存在候选项时必须生成错误标题 Markdown 元素",
            "$.body.elements",
        )
    if candidate_count == 0 and not any(
        "暂无符合条件的未解决 Error Issue" in text_content(element)
        for element in elements
    ):
        validator.add(
            "missing_empty_state",
            "无候选项时必须输出明确空态",
            "$.body.elements",
        )
    if len(candidate_ids) != candidate_count:
        validator.add(
            "candidate_ids_mismatch",
            "candidate_id 数量必须等于候选项数量",
            "$.candidate_ids",
            decision="needs-info",
        )

    top_level_buttons = [
        (index, element)
        for index, element in enumerate(elements)
        if isinstance(element, dict) and element.get("tag") == "button"
    ]
    nested_buttons = []
    for index, element in enumerate(elements):
        if not isinstance(element, dict):
            continue
        for path, _, child in walk(element, f"$.body.elements[{index}]"):
            if path != f"$.body.elements[{index}]" and isinstance(child, dict):
                if child.get("tag") == "button":
                    nested_buttons.append(path)
    for path in nested_buttons:
        validator.add(
            "nested_button",
            "按钮必须作为独立 body.elements，不能嵌套",
            path,
        )

    inspection_buttons = [
        (index, button)
        for index, button in top_level_buttons
        if isinstance(button, dict) and button.get("width") == "fill"
    ]
    solution_buttons = [
        (index, button)
        for index, button in top_level_buttons
        if isinstance(button, dict) and button.get("width") == "default"
    ]

    expected_solution_count = candidate_count if resolution_enabled else 0
    if len(solution_buttons) != expected_solution_count:
        validator.add(
            "solution_button_count",
            f"解决单按钮数为 {len(solution_buttons)}，预期 {expected_solution_count}",
            "$.body.elements",
        )

    for title_position, title_index in enumerate(title_indexes):
        segment_end = (
            title_indexes[title_position + 1]
            if title_position + 1 < len(title_indexes)
            else len(elements)
        )
        segment_buttons = [
            (index, button)
            for index, button in solution_buttons
            if title_index < index < segment_end
        ]
        if len(segment_buttons) != 1:
            validator.add(
                "candidate_button_count",
                "每条候选必须有且仅有一个解决单按钮",
                f"$.body.elements[{title_index}:{segment_end}]",
            )
            continue
        button_index, button = segment_buttons[0]
        validate_solution_button(
            button,
            validator,
            f"$.body.elements[{button_index}]",
            candidate_ids,
        )
        segment_text = " ".join(text_content(element) for element in elements[title_index:segment_end])
        if "初判：" not in segment_text:
            validator.add(
                "missing_analysis",
                "每条候选必须包含初判",
                f"$.body.elements[{title_index}:{segment_end}]",
            )
        if "建议：" not in segment_text:
            validator.add(
                "missing_recommendation",
                "每条候选必须包含建议",
                f"$.body.elements[{title_index}:{segment_end}]",
            )
        if not re.search(r"\d[\d,]*\s*次", segment_text) or "用户" not in segment_text:
            validator.add(
                "missing_metrics",
                "每条候选必须包含事件数和用户数指标",
                f"$.body.elements[{title_index}:{segment_end}]",
            )

    if expected_inspection_url is None:
        if inspection_buttons:
            validator.add(
                "unexpected_inspection_button",
                "未配置 inspection_url_template 时不得生成巡检单按钮",
                "$.body.elements",
            )
    elif len(inspection_buttons) != 1:
        validator.add(
            "inspection_button_count",
            "配置有效巡检 URL 时必须恰好有一个查看巡检单按钮",
            "$.body.elements",
        )
    else:
        button_index, button = inspection_buttons[0]
        validate_inspection_button(
            button,
            expected_inspection_url,
            validator,
            f"$.body.elements[{button_index}]",
        )
        if title_indexes and button_index <= title_indexes[-1]:
            validator.add(
                "inspection_button_order",
                "查看巡检单按钮必须位于所有候选内容之后",
                f"$.body.elements[{button_index}]",
            )


def parse_bool(value: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise argparse.ArgumentTypeError("只能是 true 或 false")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="校验 Sentry 飞书 Card 2.0 JSON，不执行发送"
    )
    parser.add_argument("--card", required=True, help="Card JSON 文件")
    parser.add_argument("--config", required=True, help="规范化发送配置 JSON 文件")
    parser.add_argument("--candidate-count", required=True, type=int)
    parser.add_argument(
        "--candidate-id",
        action="append",
        default=[],
        help="候选 Sentry Issue ID；每个候选传一次",
    )
    parser.add_argument("--resolution-enabled", required=True, type=parse_bool)
    parser.add_argument("--inspection-issue-id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validator = CardValidation()

    if args.candidate_count < 0:
        validator.add(
            "invalid_candidate_count",
            "candidate-count 不能为负数",
            "$.candidate_count",
            decision="needs-info",
        )
    if len(set(args.candidate_id)) != len(args.candidate_id):
        validator.add(
            "duplicate_candidate_id",
            "candidate-id 不得重复",
            "$.candidate_ids",
            decision="needs-info",
        )

    config = read_json(args.config, validator, "发送配置")
    send_config, expected_url = validate_send_config(
        config,
        validator,
        args.inspection_issue_id,
    )
    configured_resolution = send_config.get("resolution_enabled")
    if configured_resolution is not None and configured_resolution != args.resolution_enabled:
        validator.add(
            "resolution_state_mismatch",
            "命令参数 resolution-enabled 与发送配置不一致",
            "$.resolution_enabled",
        )

    card = read_json(args.card, validator, "Card JSON")
    if card is not None:
        validate_card(
            card,
            validator,
            args.candidate_count,
            set(args.candidate_id),
            args.resolution_enabled,
            expected_url,
        )

    report = {
        "status": "valid" if not validator.errors else "invalid",
        "decision": "ready-to-send" if not validator.errors else validator.decision,
        "errors": validator.errors,
        "summary": {
            "candidate_count": args.candidate_count,
            "resolution_enabled": args.resolution_enabled,
            "inspection_button_required": expected_url is not None,
            "inspection_url": expected_url,
        },
    }
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0 if not validator.errors else 1


if __name__ == "__main__":
    sys.exit(main())
