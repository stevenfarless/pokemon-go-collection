from __future__ import annotations

import unittest

from jsonschema import Draft202012Validator, ValidationError

from scripts.schema_contracts import (
    CORE_COLUMNS,
    analyze_source_columns,
    manifest_schema,
    pokemon_payload_schema,
    summary_schema,
)


class SchemaContractsTests(unittest.TestCase):
    def test_source_columns_distinguish_required_optional_and_unknown(self) -> None:
        report = analyze_source_columns(["CP", "Name", "Pokemon Number", "Future Column"])
        self.assertEqual(report["missing_required_columns"], [])
        self.assertIn("Atk IV", report["missing_optional_columns"])
        self.assertEqual(report["unknown_columns"], ["Future Column"])
        self.assertTrue(report["warnings"])
        self.assertEqual(report["required_columns"], list(CORE_COLUMNS))

    def test_missing_core_column_is_reported(self) -> None:
        report = analyze_source_columns(["Name", "CP"])
        self.assertEqual(report["missing_required_columns"], ["Pokemon Number"])

    def test_all_published_schemas_are_valid_draft_2020_12(self) -> None:
        for schema in (pokemon_payload_schema(), summary_schema(), manifest_schema()):
            Draft202012Validator.check_schema(schema)

    def test_payload_schema_rejects_invalid_record(self) -> None:
        validator = Draft202012Validator(pokemon_payload_schema())
        with self.assertRaises(ValidationError):
            validator.validate({"manifest": {}, "records": [{"name": "Pikachu"}]})


if __name__ == "__main__":
    unittest.main()
