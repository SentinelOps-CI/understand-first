# Understand-First CLI

Install:
```bash
pip install -e .
# or: pip install understand-first
```

Core commands:
- `u scan <path> -o maps/repo.json`
- `u lens from-seeds --map maps/repo.json --seed <seed> -o maps/lens.json`
- `u trace module <pyfile> <function> -o traces/trace.json`
- `u lens merge-trace maps/lens.json traces/trace.json -o maps/lens_merged.json`
- `u tour maps/lens_merged.json -o tours/local.md`
- `u contracts from-openapi <spec.yaml> -o contracts/contracts_from_openapi.yaml`
- `u contracts from-proto <file.proto> -o contracts/contracts_from_proto.yaml`
- `u contracts check contracts/contracts.yaml`
- `u visual delta maps/old_lens.json maps/new_lens.json -o maps/delta.svg`
- `u glossary -o docs/glossary.md`
- `u dashboard --repo maps/repo.json --lens maps/lens_merged.json --bounds maps/boundaries.json -o docs/understanding-dashboard.md`
- `u doctor`