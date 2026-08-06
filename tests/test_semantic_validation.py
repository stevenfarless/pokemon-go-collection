from __future__ import annotations

import unittest

from scripts.semantic_validation import SemanticValidationError, validate_rows


FIELDS = [
    "Index", "Name", "Pokemon Number", "CP", "HP", "Atk IV", "Def IV", "Sta IV",
    "IV Avg", "Level Min", "Level Max", "Shadow/Purified", "Rank # (G)",
    "Lucky", "Favorite", "Marked for PvP use",
]


def valid_row(**overrides):
    row = {
        "Index": "1", "Name": "Bulbasaur", "Pokemon Number": "1", "CP": "500",
        "HP": "60", "Atk IV": "15", "Def IV": "14", "Sta IV": "13",
        "IV Avg": "93.3", "Level Min": "20.0", "Level Max": "20.0",
        "Shadow/Purified": "0", "Rank # (G)": "12", "Lucky": "0",
        "Favorite": "0", "Marked for PvP use": "",
    }
    row.update(overrides)
    return row


class SemanticValidationTests(unittest.TestCase):
    def test_decimal_required_integer_is_fatal_with_row_context(self):
        with self.assertRaises(SemanticValidationError) as caught:
            validate_rows(FIELDS, [valid_row(CP="500.5")])
        text = str(caught.exception)
        self.assertIn("CSV row 2", text)
        self.assertIn("Bulbasaur", text)
        self.assertIn("'CP'", text)
        self.assertIn("500.5", text)

    def test_non_numeric_optional_value_warns_and_becomes_blank(self):
        rows, warnings = validate_rows(FIELDS, [valid_row(HP="not-a-number")])
        self.assertEqual(rows[0]["HP"], "")
        self.assertEqual(warnings[0].column, "HP")
        self.assertEqual(warnings[0].action, "published as null")

    def test_out_of_range_iv_warns_and_becomes_blank(self):
        rows, warnings = validate_rows(FIELDS, [valid_row(**{"Atk IV": "16"})])
        self.assertEqual(rows[0]["Atk IV"], "")
        self.assertTrue(any(item.column == "Atk IV" for item in warnings))

    def test_unknown_status_code_is_not_silently_normalized(self):
        rows, warnings = validate_rows(FIELDS, [valid_row(**{"Shadow/Purified": "9"})])
        self.assertEqual(rows[0]["Shadow/Purified"], "0")
        self.assertTrue(any(item.column == "Shadow/Purified" for item in warnings))

    def test_blank_optional_values_are_allowed_without_warning(self):
        rows, warnings = validate_rows(FIELDS, [valid_row(HP="", **{"Atk IV": ""})])
        self.assertEqual(rows[0]["HP"], "")
        self.assertEqual(rows[0]["Atk IV"], "")
        self.assertEqual(warnings, [])

    def test_level_increment_and_order_are_sanitized(self):
        rows, warnings = validate_rows(FIELDS, [valid_row(**{"Level Min": "20.3", "Level Max": "20.0"})])
        self.assertEqual(rows[0]["Level Min"], "")
        self.assertEqual(rows[0]["Level Max"], "20.0")
        self.assertTrue(any("0.5-level" in item.message for item in warnings))


if __name__ == "__main__":
    unittest.main()
