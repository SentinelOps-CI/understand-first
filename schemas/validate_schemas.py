#!/usr/bin/env python3
"""
Schema validation script for Understand-First JSON schemas.

This script validates example JSON files against their corresponding schemas
and provides detailed error reporting.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
import jsonschema
from jsonschema import validate, ValidationError


class SchemaValidator:
    """Validates JSON data against Understand-First schemas."""

    def __init__(self, schemas_dir: Path):
        self.schemas_dir = schemas_dir
        self.schemas: Dict[str, Dict[str, Any]] = {}
        self.load_schemas()

    def load_schemas(self) -> None:
        """Load all schema files from the schemas directory."""
        schema_files = [
            "map-schema.json",
            "lens-schema.json",
            "trace-schema.json",
            "tour-schema.json",
            "metrics-schema.json",
            "config-schema.json",
        ]

        for schema_file in schema_files:
            schema_path = self.schemas_dir / schema_file
            if schema_path.exists():
                with open(schema_path, "r") as f:
                    schema_name = schema_file.replace("-schema.json", "")
                    self.schemas[schema_name] = json.load(f)
                    print(f"✓ Loaded schema: {schema_name}")
            else:
                print(f"⚠ Missing schema file: {schema_file}")

    def validate_example(self, schema_name: str, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate data against a specific schema."""
        if schema_name not in self.schemas:
            return False, [f"Schema '{schema_name}' not found"]

        try:
            validate(instance=data, schema=self.schemas[schema_name])
            return True, []
        except ValidationError as e:
            return False, [str(e)]
        except Exception as e:
            return False, [f"Validation error: {str(e)}"]

    def validate_schema_file(self, schema_name: str) -> Tuple[bool, List[str]]:
        """Validate a schema file against JSON Schema draft-07."""
        if schema_name not in self.schemas:
            return False, [f"Schema '{schema_name}' not found"]

        try:
            jsonschema.Draft7Validator.check_schema(self.schemas[schema_name])
            return True, []
        except Exception as e:
            return False, [str(e)]

    def validate_all_schemas(self) -> Dict[str, Tuple[bool, List[str]]]:
        """Validate all loaded schemas."""
        results = {}
        for schema_name in self.schemas:
            is_valid, errors = self.validate_schema_file(schema_name)
            results[schema_name] = (is_valid, errors)
        return results

    def validate_examples(self) -> Dict[str, Tuple[bool, List[str]]]:
        """Validate example data from schemas."""
        results = {}
        for schema_name, schema in self.schemas.items():
            if "examples" in schema and schema["examples"]:
                for i, example in enumerate(schema["examples"]):
                    example_name = f"{schema_name}_example_{i+1}"
                    is_valid, errors = self.validate_example(schema_name, example)
                    results[example_name] = (is_valid, errors)
        return results

    def generate_sample_data(self, schema_name: str) -> Dict[str, Any]:
        """Generate sample data based on schema structure."""
        if schema_name not in self.schemas:
            raise ValueError(f"Schema '{schema_name}' not found")

        schema = self.schemas[schema_name]
        return self._generate_from_schema(schema)

    def _generate_from_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively generate sample data from schema."""
        if "type" not in schema:
            return {}

        schema_type = schema["type"]

        if schema_type == "object":
            result = {}
            if "properties" in schema:
                for prop_name, prop_schema in schema["properties"].items():
                    if "default" in prop_schema:
                        result[prop_name] = prop_schema["default"]
                    elif prop_name in schema.get("required", []):
                        result[prop_name] = self._generate_from_schema(prop_schema)
            return result

        elif schema_type == "array":
            if "items" in schema:
                return [self._generate_from_schema(schema["items"])]
            return []

        elif schema_type == "string":
            if "enum" in schema:
                return schema["enum"][0]
            elif "format" == "date-time":
                return "2024-01-15T10:00:00Z"
            else:
                return "sample_string"

        elif schema_type == "integer":
            return schema.get("default", 1)

        elif schema_type == "number":
            return schema.get("default", 1.0)

        elif schema_type == "boolean":
            return schema.get("default", True)

        else:
            return None


def main():
    """Main validation function."""
    schemas_dir = Path(__file__).parent
    validator = SchemaValidator(schemas_dir)

    print("🔍 Understanding-First Schema Validation")
    print("=" * 50)

    # Validate schema structure
    print("\n📋 Validating schema structure...")
    schema_results = validator.validate_all_schemas()

    all_schemas_valid = True
    for schema_name, (is_valid, errors) in schema_results.items():
        if is_valid:
            print(f"✓ {schema_name}: Valid")
        else:
            print(f"✗ {schema_name}: Invalid")
            for error in errors:
                print(f"  - {error}")
            all_schemas_valid = False

    # Validate examples
    print("\n📝 Validating schema examples...")
    example_results = validator.validate_examples()

    all_examples_valid = True
    for example_name, (is_valid, errors) in example_results.items():
        if is_valid:
            print(f"✓ {example_name}: Valid")
        else:
            print(f"✗ {example_name}: Invalid")
            for error in errors:
                print(f"  - {error}")
            all_examples_valid = False

    # Summary
    print("\n📊 Validation Summary")
    print("=" * 50)
    print(f"Schemas loaded: {len(validator.schemas)}")
    print(
        f"Schemas valid: {sum(1 for _, (valid, _) in schema_results.items() if valid)}/{len(schema_results)}"
    )
    print(
        f"Examples valid: {sum(1 for _, (valid, _) in example_results.items() if valid)}/{len(example_results)}"
    )

    if all_schemas_valid and all_examples_valid:
        print("\n🎉 All schemas and examples are valid!")
        return 0
    else:
        print("\n❌ Some schemas or examples have validation errors.")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⏹️ Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)
