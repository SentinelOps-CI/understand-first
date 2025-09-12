# Understand-First JSON Schemas

This directory contains standardized JSON schemas for all Understand-First data formats. These schemas ensure consistency across the platform and enable proper validation and tooling support.

## Schema Files

- `map-schema.json` - Repository map format
- `lens-schema.json` - Understanding lens format  
- `trace-schema.json` - Runtime trace format
- `tour-schema.json` - Understanding tour format
- `metrics-schema.json` - Metrics and instrumentation format
- `config-schema.json` - Configuration file format

## Usage

### Validation

Validate JSON files against schemas:

```bash
# Install jsonschema
pip install jsonschema

# Validate a map file
python -c "
import json
from jsonschema import validate
with open('schemas/map-schema.json') as f:
    schema = json.load(f)
with open('maps/repo.json') as f:
    data = json.load(f)
validate(instance=data, schema=schema)
print('Map is valid!')
"
```

### IDE Support

For VS Code, install the "JSON Schema" extension and add to your settings:

```json
{
  "json.schemas": [
    {
      "fileMatch": ["maps/*.json"],
      "url": "./schemas/map-schema.json"
    },
    {
      "fileMatch": ["lenses/*.json"],
      "url": "./schemas/lens-schema.json"
    },
    {
      "fileMatch": ["traces/*.json"],
      "url": "./schemas/trace-schema.json"
    },
    {
      "fileMatch": ["tours/*.json"],
      "url": "./schemas/tour-schema.json"
    }
  ]
}
```

## Schema Evolution

- **Version 1.0**: Initial schema definitions
- **Backward Compatibility**: New versions maintain backward compatibility
- **Deprecation**: Deprecated fields are marked but not removed
- **Migration**: Tools provided for schema migration when needed

## Contributing

When adding new fields to data formats:

1. Update the corresponding schema file
2. Add examples in the schema description
3. Update this README if needed
4. Test validation with existing data files
5. Document breaking changes in CHANGELOG.md
