from cli.ucli.contracts.contracts import from_openapi, from_proto, report_json
from cli.ucli.boundaries.scan import scan_boundaries


def test_from_openapi_and_proto_and_report():
    o = from_openapi("examples/apis/petstore-mini.yaml")
    assert "module: ROUTE::" in o and "functions:" in o
    p = from_proto("examples/apis/orders.proto")
    assert "module: PROTO::" in p
    # report_json should treat ROUTE/PROTO entries as virtual (no existence check)
    combined = o + "\n---\n" + p
    data = report_json_string(combined)
    assert data.get("issues") == []


def report_json_string(txt: str):
    # helper to feed string to report_json logic
    import tempfile, os

    fd, path = tempfile.mkstemp(suffix=".yaml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(txt)
        from cli.ucli.contracts.contracts import report_json

        return report_json(path)
    finally:
        os.remove(path)


essential_dirs = ["examples", "cli", "contracts"]


def test_boundaries_scanner_finds_interfaces():
    res = scan_boundaries(".")
    assert "/pets" in res.get("openapi_paths", [])
    assert any(rpc for rpc in res.get("proto_rpcs", []))
