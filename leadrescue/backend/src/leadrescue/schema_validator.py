"""Minimal, dependency-free JSON Schema validator.

Supports the subset used by the analysis contract: type (including type lists),
enum, required, properties, additionalProperties: false, items, minLength,
maxLength, maxItems, uniqueItems. Kept dependency-free so the Lambda package has
no compiled third-party wheels. Tests cross-check it against the `jsonschema` library.
"""

from __future__ import annotations

_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "null": lambda v: v is None,
}


def validate(instance, schema: dict, path: str = "$") -> list[str]:
    """Return a list of human-readable validation errors (empty when valid)."""
    errors: list[str] = []
    expected = schema.get("type")
    if expected is not None:
        types = expected if isinstance(expected, list) else [expected]
        if not any(_TYPE_CHECKS[t](instance) for t in types):
            return [f"{path}: expected {' or '.join(types)}"]
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: value not in allowed set")
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: shorter than {schema['minLength']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: longer than {schema['maxLength']}")
    if isinstance(instance, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}.{key}: required")
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in props:
                    errors.append(f"{path}.{key}: unexpected property")
        for key, sub in props.items():
            if key in instance:
                errors.extend(validate(instance[key], sub, f"{path}.{key}"))
    if isinstance(instance, list):
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: more than {schema['maxItems']} items")
        if schema.get("uniqueItems") and len({repr(i) for i in instance}) != len(instance):
            errors.append(f"{path}: items must be unique")
        if "items" in schema:
            for i, item in enumerate(instance):
                errors.extend(validate(item, schema["items"], f"{path}[{i}]"))
    return errors
