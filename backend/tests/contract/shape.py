"""Check a JSON response against the OpenAPI description of that operation (the same file the TypeScript client is built from).

A small checker on purpose (no new dependency): $ref, anyOf, types, required fields, enums, array items and
`additionalProperties`. Unknown extra fields in a response are errors: a field the frontend was not told about is a contract change.
"""

import re

from circuit.api import api

_SPEC: dict | None = None


def spec() -> dict:
    global _SPEC
    if _SPEC is None:
        _SPEC = api.get_openapi_schema()
    return _SPEC


def template_for(method: str, path: str) -> str:
    """The OpenAPI path template for a concrete path (/api/jobs/12 -> /api/jobs/{job_id})."""
    found = []
    for template, item in spec()["paths"].items():
        pattern = "^" + re.sub(r"\{[^/]+\}", r"[^/]+", template) + "$"
        if method.lower() in item and re.match(pattern, path):
            found.append((template.count("{"), template))
    if not found:
        raise AssertionError(f"{method} {path} is not in the OpenAPI description")
    return min(found)[1]


def operation(method: str, path: str) -> dict:
    """The operation for a concrete URL path such as /api/jobs/12 ({param} segments match any text). A literal route such as
    /api/jobs/skills-in-demand wins over a template such as /api/jobs/{job_id}."""
    found = []
    for template, item in spec()["paths"].items():
        pattern = "^" + re.sub(r"\{[^/]+\}", r"[^/]+", template) + "$"
        if method.lower() in item and re.match(pattern, path):
            found.append((template.count("{"), item[method.lower()]))
    if not found:
        raise AssertionError(f"{method} {path} is not in the OpenAPI description")
    return min(found, key=lambda f: f[0])[1]


def resolve(schema: dict) -> dict:
    while "$ref" in schema:
        node = spec()
        for part in schema["$ref"].lstrip("#/").split("/"):
            node = node[part]
        schema = node
    return schema


def check(schema: dict, value, where: str = "$") -> list[str]:
    """Problems found (empty list = the value fits the schema)."""
    schema = resolve(schema)
    if "anyOf" in schema or "oneOf" in schema:
        options = schema.get("anyOf") or schema.get("oneOf")
        tried = [check(o, value, where) for o in options]
        return [] if any(not t for t in tried) else [f"{where}: fits none of {len(options)} options ({tried[-1][:1]})"]
    if "enum" in schema:
        return [] if value in schema["enum"] else [f"{where}: {value!r} is not one of {schema['enum']}"]
    if "const" in schema:
        return [] if value == schema["const"] else [f"{where}: {value!r} is not {schema['const']!r}"]
    kind = schema.get("type")
    if kind == "null":
        return [] if value is None else [f"{where}: expected null"]
    if value is None:
        return [f"{where}: null is not allowed"]
    if kind == "object" or "properties" in schema:
        if not isinstance(value, dict):
            return [f"{where}: expected an object, got {type(value).__name__}"]
        problems = []
        props = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                problems.append(f"{where}.{name}: missing")
        for name, item in value.items():
            if name in props:
                problems += check(props[name], item, f"{where}.{name}")
            elif isinstance(schema.get("additionalProperties"), dict):
                problems += check(schema["additionalProperties"], item, f"{where}.{name}")
            elif props and schema.get("additionalProperties") is not True:
                problems.append(f"{where}.{name}: not in the schema")
        return problems
    if kind == "array":
        if not isinstance(value, list):
            return [f"{where}: expected a list"]
        return [p for i, item in enumerate(value) for p in check(schema.get("items", {}), item, f"{where}[{i}]")]
    checks = {
        "string": lambda v: isinstance(v, str),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
    }
    if kind in checks:
        return [] if checks[kind](value) else [f"{where}: expected {kind}, got {type(value).__name__}"]
    return []  # no type given (free-form): anything goes


def check_response(method: str, path: str, status: int, body) -> list[str]:
    """Check one response against the operation's documented response for that status."""
    if status >= 400:  # errors have one shape everywhere (core/errors.py)
        error = body.get("error") if isinstance(body, dict) else None
        ok = isinstance(error, dict) and set(error) == {"code", "message", "details"} and isinstance(error["code"], str)
        return [] if ok else [f"{method} {path}: {status} is not the error envelope {{error: {{code, message, details}}}}"]
    op = operation(method, path)
    responses = op.get("responses", {})
    doc = responses.get(status) or responses.get(str(status))  # the in-memory spec keys by int, the JSON file by string
    if doc is None:
        return [f"{method} {path}: status {status} is not documented (documented: {sorted(map(str, responses))})"]
    content = doc.get("content", {}).get("application/json")
    if content is None:
        return [] if body in (None, "", {}) else [f"{method} {path}: {status} has no body in the schema but one was sent"]
    return check(content["schema"], body)
