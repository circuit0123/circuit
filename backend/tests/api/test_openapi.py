"""LAUNCH.md: 'OpenAPI spec clean; every endpoint described'. The frontend client is generated from this."""

from circuit.api import api


def operations():
    for path, item in api.get_openapi_schema()["paths"].items():
        for method, op in item.items():
            yield method.upper(), path, op


def test_every_endpoint_has_summary_description_and_tag():
    bad = [(m, p) for m, p, op in operations() if not (op.get("summary") and op.get("description") and op.get("tags"))]
    assert not bad, f"describe these endpoints: {bad}"


def test_operation_ids_are_unique():
    ids = [op["operationId"] for _, _, op in operations()]
    assert len(ids) == len(set(ids))
