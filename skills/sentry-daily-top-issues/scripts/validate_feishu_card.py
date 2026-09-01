#!/usr/bin/env python3
"""Validate a Sentry Feishu Card 2.0 payload before delivery.

The validator is intentionally dependency-free. It validates the normalized
Autopilot send configuration together with the rendered Card JSON. It never
sends a message and never prints secret values.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ISSUE_TITLE_RE = re.compile(
    r"^\*\*\[(?P<title>[^\]]+)\]\((?P<url>https://[^)\s]+)\)\*\*$"
)
CHAT_ID_RE = re.compile(r"^oc_[A-Za-z0-9]+$")
AUTOPILOT_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
PLACEHOLDER_RE = re.compile(r"<[^>]+>")
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\([^)]+\)")
RAW_HTML_TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")
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
    "source_inspection_autopilot_id",
    "resolution_config_version",
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


def validate_header_style(
    header: dict[str, Any],
    validator: CardValidation,
) -> None:
    if header.get("template") != "red":
        validator.add(
            "invalid_header_template",
            "告警卡片 header.template 必须为 red",
            "$.header.template",
        )

    title = header.get("title")
    if (
        not isinstance(title, dict)
        or title.get("tag") != "plain_text"
        or not non_empty_string(title.get("content"))
    ):
        validator.add(
            "invalid_header_title",
            "卡片标题必须使用非空 plain_text",
            "$.header.title",
        )


def validate_candidate_visual_style(
    element: dict[str, Any],
    validator: CardValidation,
    path: str,
    *,
    is_title: bool = False,
    require_analysis_label_emphasis: bool = False,
) -> None:
    content = text_content(element)
    tag = element.get("tag")

    if is_title:
        return

    is_metrics = bool(re.match(r"^\**\d[\d,]*\s*次", content)) and "用户" in content
    metrics_prefix = re.match(
        r"^\*\*\d[\d,]*\s*次\s*·\s*\d[\d,]*\s*用户\*\*",
        content,
    )
    if is_metrics and (
        tag != "markdown"
        or metrics_prefix is None
        or content.count("**") != 2
    ):
        validator.add(
            "invalid_metrics_style",
            "事件数和用户数必须由同一个 markdown 元素加粗，最近时间和版本保持常规字重",
            path,
        )

    analysis_label = next(
        (
            label
            for label in ("初判：", "建议：")
            if content.startswith(label) or content.startswith(f"**{label}**")
        ),
        None,
    )
    if analysis_label:
        if tag != "markdown":
            validator.add(
                "invalid_analysis_element",
                "初判和建议必须使用 markdown 元素",
                path,
            )
            return
        emphasized_prefix = f"**{analysis_label}**"
        if require_analysis_label_emphasis and not content.startswith(
            emphasized_prefix
        ):
            validator.add(
                "invalid_analysis_label_style",
                f"{analysis_label} 标签必须加粗，正文保持常规字重",
                path,
            )
        if content.startswith(emphasized_prefix) and "**" in content[len(emphasized_prefix) :]:
            validator.add(
                "invalid_analysis_body_style",
                f"{analysis_label} 正文不得继续使用 Markdown 加粗",
                path,
            )


def validate_context_text_style(
    element: dict[str, Any],
    validator: CardValidation,
    path: str,
    *,
    require_stable_context: bool = False,
) -> None:
    if element.get("tag") == "markdown":
        if require_stable_context:
            validator.add(
                "invalid_context_element",
                "新卡片的项目/归因/版本/路由上下文必须使用 div + plain_text",
                path,
            )
        for field in ("text_color", "text_size", "text_align"):
            if field in element:
                validator.add(
                    "invalid_context_markdown_style",
                    "上下文 markdown 不得依赖颜色、字号或对齐字段",
                    f"{path}.{field}",
                )
        return

    if element.get("tag") != "div":
        validator.add(
            "invalid_context_element",
            "项目/归因/版本/路由上下文必须使用 div 元素",
            path,
        )
        return

    text = element.get("text")
    if not isinstance(text, dict) or text.get("tag") != "plain_text":
        validator.add(
            "invalid_context_text",
            "上下文必须使用 div + plain_text",
            f"{path}.text",
        )
        return

    if require_stable_context:
        expected_style = {
            "text_color": "default",
            "text_size": "notation",
            "text_align": "left",
        }
        for field, expected in expected_style.items():
            if text.get(field) != expected:
                validator.add(
                    "invalid_context_text_style",
                    f"新卡片上下文文本 {field} 必须为 {expected}",
                    f"{path}.text.{field}",
                )
        icon = element.get("icon")
        if (
            not isinstance(icon, dict)
            or icon.get("tag") != "standard_icon"
            or icon.get("token") != "info_outlined"
            or icon.get("color") != "blue"
        ):
            validator.add(
                "invalid_context_icon",
                "新卡片上下文必须使用蓝色 info_outlined 标准图标",
                f"{path}.icon",
            )
        return

    if text.get("text_size") not in {None, "notation"}:
        validator.add(
            "invalid_context_text_style",
            "更新卡片上下文 text_size 只能保持 notation 或沿用历史值",
            f"{path}.text.text_size",
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
    def validate_markdown_fields(value: Any, path: str) -> None:
        if isinstance(value, dict):
            if value.get("tag") == "markdown":
                if "text_color" in value:
                    validator.add(
                        "unsupported_markdown_field",
                        "Card 2.0 的 markdown 元素不支持 text_color 字段",
                        f"{path}.text_color",
                    )
                content = value.get("content")
                if isinstance(content, str) and RAW_HTML_TAG_RE.search(content):
                    validator.add(
                        "unescaped_markdown_html",
                        "Markdown 动态文本不得包含未转义 HTML 标签，请将 < 和 > 转为实体",
                        f"{path}.content",
                    )
            for key, child in value.items():
                validate_markdown_fields(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                validate_markdown_fields(child, f"{path}[{index}]")

    validate_markdown_fields(card, "$")
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

    # Autopilot descriptions are Markdown. Normalize one serialization layer
    # before validating the canonical raw HTTPS prefix or legacy template.
    template = html.unescape(template)

    markdown_match = re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", template)
    if markdown_match:
        label, target = markdown_match.groups()
        if label != target:
            validator.add(
                "markdown_inspection_template",
                "inspection_url_template 不能使用显示文本和目标不一致的 Markdown 链接",
                "$.inspection_url_template",
                decision="needs-info",
            )
        else:
            # Some editors serialize a plain URL as [URL](URL). Normalize one
            # identical wrapper without accepting hidden or rewritten targets.
            template = target
    elif "[" in template or "](" in template:
        validator.add(
            "markdown_inspection_template",
            "inspection_url_template 必须是原始 URL，不能是 Markdown 链接",
            "$.inspection_url_template",
            decision="needs-info",
        )

    placeholders = PLACEHOLDER_RE.findall(template)
    issue_placeholder_count = placeholders.count("<Issue-ID>")
    has_legacy_template = issue_placeholder_count == 1 and not any(
        placeholder != "<Issue-ID>" for placeholder in placeholders
    )
    if issue_placeholder_count > 1:
        validator.add(
            "duplicate_issue_placeholder",
            "inspection_url_template 必须只包含一个 <Issue-ID> 占位符",
            "$.inspection_url_template",
            decision="needs-info",
        )
    if placeholders and not has_legacy_template:
        validator.add(
            "unknown_url_placeholder",
            "inspection_url_template 只能使用前缀模式或一个 <Issue-ID> 占位符",
            "$.inspection_url_template",
            decision="needs-info",
        )
    if not placeholders and ("<" in template or ">" in template):
        validator.add(
            "invalid_inspection_template",
            "inspection_url_template 包含未识别的尖括号内容",
            "$.inspection_url_template",
            decision="needs-info",
        )

    if has_legacy_template:
        url_for_validation = template.replace("<Issue-ID>", "placeholder")
    else:
        url_for_validation = template
        parsed = urlparse(template)
        if not parsed.path.endswith("/"):
            validator.add(
                "invalid_inspection_prefix",
                "inspection_url_template 前缀必须以 / 结尾",
                "$.inspection_url_template",
                decision="needs-info",
            )
        if parsed.query or parsed.fragment:
            validator.add(
                "invalid_inspection_prefix",
                "inspection_url_template 前缀不能包含 query 或 fragment",
                "$.inspection_url_template",
                decision="needs-info",
            )

    if not valid_https_url(url_for_validation):
        validator.add(
            "invalid_inspection_template",
            "inspection_url_template 必须是合法 HTTPS URL 或 HTTPS 前缀",
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

    resolved = (
        template.replace("<Issue-ID>", inspection_issue_id)
        if has_legacy_template
        else f"{template}{inspection_issue_id}"
    )
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
    source_autopilot_id = value.get("source_inspection_autopilot_id")
    if not AUTOPILOT_ID_RE.fullmatch(str(source_autopilot_id or "")):
        validator.add(
            "invalid_source_inspection_autopilot_id",
            "source_inspection_autopilot_id 必须是有效的 Autopilot UUID",
            f"{path}.behaviors[0].value.source_inspection_autopilot_id",
        )
    if value.get("resolution_config_version") != "business_resolution_config_v1":
        validator.add(
            "invalid_resolution_config_version",
            "resolution_config_version 必须是 business_resolution_config_v1",
            f"{path}.behaviors[0].value.resolution_config_version",
        )
    if not valid_https_url(value.get("issue_url")):
        validator.add(
            "invalid_issue_url",
            "issue_url 必须是合法 HTTPS URL",
            f"{path}.behaviors[0].value.issue_url",
        )


def validate_title_callback_consistency(
    title_element: dict[str, Any],
    button: dict[str, Any],
    validator: CardValidation,
    path: str,
) -> None:
    title_match = ISSUE_TITLE_RE.fullmatch(text_content(title_element))
    behaviors = button.get("behaviors")
    if (
        title_match is None
        or not isinstance(behaviors, list)
        or len(behaviors) != 1
        or not isinstance(behaviors[0], dict)
        or behaviors[0].get("type") != "callback"
        or not isinstance(behaviors[0].get("value"), dict)
    ):
        return

    callback_title = behaviors[0]["value"].get("issue_title")
    displayed_title = html.unescape(title_match.group("title"))
    if callback_title != displayed_title:
        validator.add(
            "title_callback_mismatch",
            "卡片标题与 callback 的 issue_title 必须使用同一个 resolved_issue_title",
            f"{path}.behaviors[0].value.issue_title",
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


def top_level_button_indices(card: Any) -> list[int]:
    if not isinstance(card, dict):
        return []
    body = card.get("body")
    elements = body.get("elements") if isinstance(body, dict) else None
    if not isinstance(elements, list):
        return []
    return [
        index
        for index, element in enumerate(elements)
        if isinstance(element, dict) and element.get("tag") == "button"
    ]


def card_without_top_level_buttons(card: Any) -> Any:
    normalized = deepcopy(card)
    if not isinstance(normalized, dict):
        return normalized
    body = normalized.get("body")
    elements = body.get("elements") if isinstance(body, dict) else None
    if isinstance(elements, list):
        body["elements"] = [
            element
            for element in elements
            if not (isinstance(element, dict) and element.get("tag") == "button")
        ]
    return normalized


def validate_card_update(
    previous_card: Any,
    card: Any,
    validator: CardValidation,
) -> None:
    if not isinstance(previous_card, dict) or not isinstance(card, dict):
        return
    previous_elements = (
        previous_card.get("body", {}).get("elements")
        if isinstance(previous_card.get("body"), dict)
        else None
    )
    elements = (
        card.get("body", {}).get("elements")
        if isinstance(card.get("body"), dict)
        else None
    )
    if not isinstance(previous_elements, list) or not isinstance(elements, list):
        return

    previous_button_indices = top_level_button_indices(previous_card)
    button_indices = top_level_button_indices(card)
    if previous_button_indices != button_indices:
        validator.add(
            "card_button_slots_changed",
            "状态更新不得改变顶层按钮位置或数量",
            "$.body.elements",
        )

    if card_without_top_level_buttons(previous_card) != card_without_top_level_buttons(
        card
    ):
        validator.add(
            "card_non_button_structure_changed",
            "状态更新只能替换按钮，不得重建或改变非按钮卡片结构",
            "$",
        )


def validate_candidate_separators(
    elements: list[Any],
    title_indexes: list[int],
    candidate_count: int,
    validator: CardValidation,
    *,
    reject_internal_separators: bool,
) -> None:
    expected_separator_count = max(candidate_count - 1, 0)
    if len(title_indexes) != candidate_count:
        return

    separator_indices = [
        index
        for index, element in enumerate(elements)
        if isinstance(element, dict) and element.get("tag") == "hr"
    ]
    candidate_separator_indices: list[int] = []
    for candidate_index in range(candidate_count - 1):
        start = title_indexes[candidate_index]
        end = title_indexes[candidate_index + 1]
        solution_buttons = [
            index
            for index, element in enumerate(elements[start:end], start)
            if (
                isinstance(element, dict)
                and element.get("tag") == "button"
                and element.get("width") == "default"
            )
        ]
        if len(solution_buttons) != 1:
            continue

        separator_index = solution_buttons[0] + 1
        if (
            separator_index >= end
            or not isinstance(elements[separator_index], dict)
            or elements[separator_index].get("tag") != "hr"
        ):
            validator.add(
                "missing_candidate_separator",
                "相邻候选之间必须有独立 hr 分隔符，且分隔符必须紧跟上一条解决单按钮",
                f"$.body.elements[{separator_index}]",
            )
            continue
        candidate_separator_indices.append(separator_index)
        if separator_index + 1 != end:
            validator.add(
                "invalid_candidate_separator_order",
                "候选 hr 分隔符必须紧邻下一条候选标题",
                f"$.body.elements[{separator_index}]",
            )

    if len(candidate_separator_indices) != expected_separator_count:
        validator.add(
            "candidate_separator_count",
            f"候选分隔符数量为 {len(candidate_separator_indices)}，预期 {expected_separator_count}",
            "$.body.elements",
        )
    if reject_internal_separators:
        for separator_index in separator_indices:
            if separator_index not in candidate_separator_indices:
                validator.add(
                    "unexpected_internal_separator",
                    "指标、初判和建议之间不得插入分隔线",
                    f"$.body.elements[{separator_index}]",
                )


def validate_compact_layout(
    elements: list[Any],
    validator: CardValidation,
) -> None:
    expected_margins = {
        "markdown": "0px",
        "div": "0px",
        "button": "0px",
        "hr": "4px 0px",
    }
    for index, element in enumerate(elements):
        if not isinstance(element, dict):
            continue
        tag = element.get("tag")
        expected_margin = expected_margins.get(tag)
        if expected_margin is None:
            continue
        if element.get("margin") != expected_margin:
            validator.add(
                "invalid_compact_margin",
                f"{tag} 元素 margin 必须为 {expected_margin}",
                f"$.body.elements[{index}].margin",
            )
        if tag == "hr":
            continue

        content = text_content(element)
        if not content.strip():
            validator.add(
                "empty_body_element",
                f"{tag} 元素不得为空",
                f"$.body.elements[{index}]",
            )
        if content.startswith("\n") or content.endswith("\n") or "\n\n" in content:
            validator.add(
                "excessive_body_spacing",
                f"{tag} 元素不得包含首尾空行或连续空行",
                f"$.body.elements[{index}]",
            )


def validate_card(
    card: Any,
    validator: CardValidation,
    candidate_count: int,
    candidate_ids: set[str],
    resolution_enabled: bool,
    expected_inspection_url: str | None,
    *,
    require_create_visual_style: bool,
) -> None:
    if not isinstance(card, dict):
        validator.add("invalid_card", "Card JSON 必须是对象", "$")
        return
    if card.get("schema") != "2.0":
        validator.add("invalid_schema", '根对象 schema 必须是 "2.0"', "$.schema")
    if not isinstance(card.get("header"), dict):
        validator.add("missing_header", "根对象必须包含 header 对象", "$.header")
    else:
        validate_header_style(card["header"], validator)
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

    validate_candidate_separators(
        elements,
        title_indexes,
        candidate_count,
        validator,
        reject_internal_separators=require_create_visual_style,
    )
    validate_compact_layout(elements, validator)

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
        solution_button_kind = validate_solution_button(
            button,
            validator,
            f"$.body.elements[{button_index}]",
            candidate_ids,
        )
        if (
            require_create_visual_style
            and solution_button_kind == "create"
            and isinstance(elements[title_index], dict)
            and isinstance(button, dict)
        ):
            validate_title_callback_consistency(
                elements[title_index],
                button,
                validator,
                f"$.body.elements[{button_index}]",
            )
        content_elements = [
            (index, element)
            for index, element in enumerate(elements[title_index:segment_end], title_index)
            if not (isinstance(element, dict) and element.get("tag") == "button")
        ]
        for content_index, content_element in content_elements:
            if isinstance(content_element, dict):
                validate_candidate_visual_style(
                    content_element,
                    validator,
                    f"$.body.elements[{content_index}]",
                    is_title=content_index == title_index,
                    require_analysis_label_emphasis=require_create_visual_style,
                )
        context_elements = [
            (index, element)
            for index, element in content_elements
            if (
                isinstance(element, dict)
                and element.get("tag") in {"markdown", "div"}
                and not is_issue_title(element)
                and not text_content(element).startswith(
                    ("**", "初判：", "建议：")
                )
            )
        ]
        if not context_elements:
            validator.add(
                "missing_context_element",
                "每条候选必须包含独立的上下文 div",
                f"$.body.elements[{title_index}:{segment_end}]",
            )
        for context_index, context_element in context_elements:
            validate_context_text_style(
                context_element,
                validator,
                f"$.body.elements[{context_index}]",
                require_stable_context=require_create_visual_style,
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
    parser.add_argument(
        "--previous-card",
        help="状态更新前的 Card JSON；传入后只允许按钮状态变化",
    )
    parser.add_argument(
        "--operation",
        choices=("create", "update"),
        default="create",
        help="卡片操作类型；update 必须同时传入 --previous-card",
    )
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
    previous_card = (
        read_json(args.previous_card, validator, "更新前 Card JSON")
        if args.previous_card
        else None
    )
    if args.operation == "update" and not args.previous_card:
        validator.add(
            "missing_previous_card",
            "update 操作必须提供更新前的 Card JSON",
            "$.previous_card",
        )
    if args.operation == "create" and args.previous_card:
        validator.add(
            "unexpected_previous_card",
            "create 操作不得传入更新前的 Card JSON",
            "$.previous_card",
        )
    if card is not None:
        validate_card(
            card,
            validator,
            args.candidate_count,
            set(args.candidate_id),
            args.resolution_enabled,
            expected_url,
            require_create_visual_style=args.operation == "create",
        )
        if args.previous_card and previous_card is not None:
            validate_card_update(previous_card, card, validator)

    report = {
        "status": "valid" if not validator.errors else "invalid",
        "decision": "ready-to-send" if not validator.errors else validator.decision,
        "errors": validator.errors,
        "summary": {
            "candidate_count": args.candidate_count,
            "resolution_enabled": args.resolution_enabled,
            "inspection_button_required": expected_url is not None,
            "inspection_url": expected_url,
            "previous_card_checked": bool(args.previous_card),
        },
    }
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0 if not validator.errors else 1


if __name__ == "__main__":
    sys.exit(main())
