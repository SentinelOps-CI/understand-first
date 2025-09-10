# Contracts

This directory contains machine-readable interface contracts and generated formal stubs.

Structure:
- contracts_from_openapi.yaml: Contracts extracted from OpenAPI specs (ROUTE:: modules)
- contracts_from_proto.yaml: Contracts extracted from protobuf/gRPC files (PROTO:: modules)
- contracts.yaml: Optional composed contracts (merged from multiple sources)
- lean/: Lean theorem stubs for invariants derived from contracts

Common commands:
- Generate from OpenAPI:
  - `u contracts from-openapi examples/apis/petstore-mini.yaml -o contracts/contracts_from_openapi.yaml`
- Generate from protobuf:
  - `u contracts from-proto examples/apis/orders.proto -o contracts/contracts_from_proto.yaml`
- Compose multiple sources:
  - `u contracts compose -i contracts/contracts_from_openapi.yaml -i contracts/contracts_from_proto.yaml -o contracts/contracts.yaml`
- Generate Lean invariants:
  - `u contracts lean-stubs contracts/contracts.yaml -o contracts/lean/`
- Verify Lean coverage for contracts:
  - `u contracts verify-lean contracts/contracts.yaml -l contracts/lean`
- Stub property tests:
  - `u contracts stub-tests contracts/contracts.yaml -o tests/test_contracts.py`

Notes:
- OpenAPI generation prefers operationId for function names; otherwise a sanitized verb/path is used.
- PROTO modules record RPC names only; enrich pre/post conditions as you adopt contracts.
- The verify-lean command checks that each function has a corresponding theorem stub in `contracts/lean/`.

