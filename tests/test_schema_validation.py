import json
import os

import pytest
from jsonschema import validate


def test_validate_json_schema() -> None:
    """
    Validates the generated mtbo_events.json against schema.json.
    """
    # Paths
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    data_path = os.path.join(base_dir, "data", "events", "mtbo_events.json")
    schema_path = os.path.join(base_dir, "schema.json")

    # Check existence
    assert os.path.exists(schema_path), "Schema file not found"

    if not os.path.exists(data_path):
        pytest.skip("mtbo_events.json not found, skipping validation test.")

    # Load Schema
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    # Load Data
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)

    # Validate
    # This will raise ValidationError if invalid
    validate(instance=data, schema=schema)
