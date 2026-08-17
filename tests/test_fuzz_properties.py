from __future__ import annotations

import random
import string
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from scripts import build_site


SEED = 0x504F4B45


class DeterministicFuzzProperties(unittest.TestCase):
    def test_export_filename_round_trip_and_malformed_inputs(self) -> None:
        rng = random.Random(SEED)
        origin = datetime(2020, 1, 1, 0, 0, 0)
        for _ in range(300):
            stamp = origin + timedelta(milliseconds=rng.randrange(0, 12 * 365 * 24 * 60 * 60 * 1000))
            name = stamp.strftime("shared-text-%Y-%m-%d %H_%M_%S.") + f"{stamp.microsecond // 1000:03d}.csv"
            parsed = build_site.parse_export_filename(Path(name))
            self.assertIsNotNone(parsed, name)
            self.assertEqual(parsed.timestamp, stamp.replace(microsecond=(stamp.microsecond // 1000) * 1000))

            mutations = (
                name.replace("shared-text-", "sharedtext-", 1),
                name.removesuffix(".csv") + ".txt",
                name.replace("_", ":", 1),
                "x" + name,
            )
            for malformed in mutations:
                self.assertIsNone(build_site.parse_export_filename(Path(malformed)), malformed)

    def test_core_numeric_garbage_never_becomes_plausible_zero(self) -> None:
        rng = random.Random(SEED + 1)
        alphabet = string.ascii_letters + "!@#$%^&*()[]{}"
        for _ in range(250):
            garbage = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 18)))
            row = {"Name": "Pikachu", "Pokemon Number": garbage, "CP": "500"}
            with self.assertRaisesRegex(ValueError, "Pokémon number"):
                build_site.normalize_row(row, 2)

            row = {"Name": "Pikachu", "Pokemon Number": "25", "CP": garbage}
            with self.assertRaisesRegex(ValueError, "CP value"):
                build_site.normalize_row(row, 2)

    def test_normalization_is_deterministic_for_random_optional_fields(self) -> None:
        rng = random.Random(SEED + 2)
        optional = ["HP", "Atk IV", "Def IV", "Sta IV", "IV Avg", "Weight", "Height", "Dust"]
        choices = ["", " ", "0", "1", "15", "1,234", "-1", "abc", "99.5", "∞"]
        for index in range(200):
            row = {"Name": "Eevee", "Pokemon Number": "133", "CP": "500"}
            for field in optional:
                row[field] = rng.choice(choices)
            first = build_site.normalize_row(dict(row), index + 2)
            second = build_site.normalize_row(dict(row), index + 2)
            self.assertEqual(first, second)
            for value in (first["hp"], first["ivs"]["attack"], first["ivs"]["defense"], first["ivs"]["stamina"]):
                self.assertTrue(value is None or isinstance(value, (int, float)))

    def test_unknown_boolean_and_shadow_values_fail_closed(self) -> None:
        rng = random.Random(SEED + 3)
        for _ in range(200):
            token = "".join(rng.choice(string.ascii_letters) for _ in range(rng.randint(2, 16)))
            if token in {"true", "True", "TRUE", "yes", "Yes"}:
                continue
            self.assertFalse(build_site.truthy(token))
            self.assertEqual(build_site.shadow_status(token), "normal")


if __name__ == "__main__":
    unittest.main()
