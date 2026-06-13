"""用于对接 OpenAI Agents SDK 工具 schema 和 guardrail。"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from agents import (
    ToolGuardrailFunctionOutput,
    ToolInputGuardrail,
    ToolOutputGuardrail,
)

from app.agents.resume.observability import record_guardrail_rejections

_ARGUMENT_PARSE_ERROR_KEY = "__tool_arguments_parse_error"


def strict_tool_params_schema(parameters: Any) -> dict[str, Any]:
    """用于生成 OpenAI Agents SDK strict function tool 参数 schema。"""
    schema = deepcopy(parameters) if isinstance(parameters, dict) else {}
    if not schema:
        return {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return _strict_schema_node(schema, preserve_required=True)


def compact_tool_arguments(value: Any) -> Any:
    """用于删除 strict schema 产生的 nullable 占位字段。"""
    if isinstance(value, dict):
        return {
            str(key): compact_tool_arguments(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, list):
        return [compact_tool_arguments(item) for item in value if item is not None]
    return value


def tool_input_guardrail(required: list[str]) -> ToolInputGuardrail[Any]:
    """用于创建校验工具参数 JSON 和业务必填字段的 SDK guardrail。"""
    required_fields = tuple(required)

    def guardrail(data: Any) -> ToolGuardrailFunctionOutput:
        """用于在 SDK 调用业务工具前校验原始参数。"""
        parsed = _parse_tool_arguments(str(data.context.tool_arguments or ""))
        if _ARGUMENT_PARSE_ERROR_KEY in parsed:
            record_guardrail_rejections(1)
            return ToolGuardrailFunctionOutput.reject_content(
                _tool_error_json("invalid_arguments_json", "工具参数不是合法 JSON。", True),
                output_info={"error_code": "invalid_arguments_json"},
            )
        compacted = compact_tool_arguments(parsed)
        if not isinstance(compacted, dict):
            record_guardrail_rejections(1)
            return ToolGuardrailFunctionOutput.reject_content(
                _tool_error_json("invalid_arguments_type", "工具参数必须是对象。", True),
                output_info={"error_code": "invalid_arguments_type"},
            )
        missing = [field for field in required_fields if not compacted.get(field)]
        if missing:
            record_guardrail_rejections(1)
            return ToolGuardrailFunctionOutput.reject_content(
                _tool_error_json(
                    "missing_required_argument",
                    f"工具参数缺少必填字段: {', '.join(missing)}",
                    True,
                ),
                output_info={"error_code": "missing_required_argument", "missing": missing},
            )
        return ToolGuardrailFunctionOutput.allow(output_info={"required": list(required_fields)})

    return ToolInputGuardrail(guardrail_function=guardrail, name="resume_tool_input_contract")


def tool_output_guardrail() -> ToolOutputGuardrail[Any]:
    """用于创建校验业务工具输出格式的 SDK guardrail。"""

    def guardrail(data: Any) -> ToolGuardrailFunctionOutput:
        """用于在业务工具返回后校验输出可回灌给模型。"""
        text = str(data.output or "")
        if not text:
            return ToolGuardrailFunctionOutput.allow(output_info={"empty": True})
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            record_guardrail_rejections(1)
            return ToolGuardrailFunctionOutput.reject_content(
                _tool_error_json("invalid_tool_output", "工具输出不是合法 JSON。", True),
                output_info={"error_code": "invalid_tool_output"},
            )
        if isinstance(parsed, dict):
            return ToolGuardrailFunctionOutput.allow(
                output_info={
                    "success": parsed.get("success"),
                    "recoverable": parsed.get("recoverable"),
                }
            )
        return ToolGuardrailFunctionOutput.allow(output_info={"json_type": type(parsed).__name__})

    return ToolOutputGuardrail(guardrail_function=guardrail, name="resume_tool_output_contract")


def _strict_schema_node(schema: dict[str, Any], *, preserve_required: bool) -> dict[str, Any]:
    """用于递归转换 schema，使 optional 字段以 nullable 形式表达。"""
    next_schema = dict(schema)
    schema_type = next_schema.get("type")
    if schema_type == "object":
        return _strict_object_schema(next_schema, preserve_required=preserve_required)
    if schema_type == "array" and isinstance(next_schema.get("items"), dict):
        next_schema["items"] = _strict_schema_node(next_schema["items"], preserve_required=True)
    for key in ("anyOf", "oneOf", "allOf"):
        if isinstance(next_schema.get(key), list):
            next_schema[key] = [
                _strict_schema_node(item, preserve_required=True) if isinstance(item, dict) else item
                for item in next_schema[key]
            ]
    return next_schema


def _strict_object_schema(schema: dict[str, Any], *, preserve_required: bool) -> dict[str, Any]:
    """用于把对象 schema 转成 strict object，并保留原业务必填语义。"""
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        schema["properties"] = {}
        schema["required"] = []
        schema["additionalProperties"] = False
        return schema
    original_required = set(schema.get("required") or []) if preserve_required else set(properties)
    schema["properties"] = {
        str(key): _strict_property_schema(value, str(key) in original_required)
        for key, value in properties.items()
    }
    schema["required"] = list(schema["properties"].keys())
    schema["additionalProperties"] = False
    return schema


def _strict_property_schema(value: Any, is_required: bool) -> dict[str, Any]:
    """用于转换单个属性 schema，并把非必填属性改成 nullable。"""
    schema = _strict_schema_node(value, preserve_required=True) if isinstance(value, dict) else {}
    return schema if is_required or _allows_null(schema) else _nullable_schema(schema)


def _nullable_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """用于构造 strict schema 兼容的 nullable 属性。"""
    description = schema.get("description")
    nullable: dict[str, Any] = {"anyOf": [schema, {"type": "null"}]}
    if isinstance(description, str):
        nullable["description"] = description
    return nullable


def _allows_null(schema: dict[str, Any]) -> bool:
    """用于判断 schema 是否已经允许 null。"""
    schema_type = schema.get("type")
    if schema_type == "null":
        return True
    if isinstance(schema_type, list) and "null" in schema_type:
        return True
    return any(
        isinstance(item, dict) and item.get("type") == "null"
        for key in ("anyOf", "oneOf")
        for item in schema.get(key, [])
        if isinstance(schema.get(key), list)
    )


def _parse_tool_arguments(arguments: str) -> dict[str, Any]:
    """用于解析原始工具参数 JSON。"""
    try:
        parsed = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return {_ARGUMENT_PARSE_ERROR_KEY: arguments}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def _tool_error_json(code: str, message: str, recoverable: bool) -> str:
    """用于生成可回灌给模型的工具错误 JSON。"""
    return json.dumps(
        {"success": False, "error": code, "message": message, "recoverable": recoverable},
        ensure_ascii=False,
    )


__all__ = [
    "compact_tool_arguments",
    "strict_tool_params_schema",
    "tool_input_guardrail",
    "tool_output_guardrail",
]
