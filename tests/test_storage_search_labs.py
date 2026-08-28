from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import storage_search_labs


class StorageSearchLabPublisherTests(unittest.TestCase):
    def test_registry_and_contracts_fail_closed(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        registry = json.loads((repository_root / "knowledge" / "search-operator-registry.json").read_text(encoding="utf-8"))
        storage_search_labs._validate_registry(registry)
        self.assertEqual(registry["authority"], "Official")
        self.assertFalse(registry["boolean"]["grouping_supported"])
        ids = {item["id"] for item in registry["operators"]}
        self.assertTrue({"dynamax", "gigantamax", "fusion", "hypertraining"}.issubset(ids))

        manifest = {"build_id": "abcdef123456"}
        search = storage_search_labs.build_search_contract(manifest, registry)
        cleanup = storage_search_labs.build_cleanup_contract(manifest)
        self.assertIn("unknown operator", search["semantics"]["unknown_operator"])
        self.assertTrue(search["local_templates"]["unified_backup"])
        self.assertFalse(cleanup["safety"]["automatic_transfer"])
        self.assertFalse(cleanup["safety"]["automatic_transfer_safe_state"])
        self.assertFalse(cleanup["safety"]["missing_data_is_expendability"])
        self.assertTrue(cleanup["local_review_state"]["unified_backup"])

    def test_publish_writes_pages_registry_schemas_and_tools_links(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "data").mkdir(parents=True)
            (output / "tools.html").write_text("<html><body><main>Tools\n  </main></body></html>", encoding="utf-8")
            (output / "llms.txt").write_text("bootstrap\n", encoding="utf-8")
            result = storage_search_labs.publish(repository_root, output, {"build_id": "abcdef123456"})
            self.assertEqual(result["labs"]["storage_cleanup"]["issue"], 149)
            self.assertEqual(result["labs"]["search_builder"]["issue"], 150)
            self.assertTrue((output / "storage-cleanup.html").is_file())
            self.assertTrue((output / "search-builder.html").is_file())
            self.assertTrue((output / "data" / "search-operator-registry.json").is_file())
            self.assertTrue((output / "data" / "search-builder-contract.schema.json").is_file())
            self.assertTrue((output / "data" / "storage-cleanup-contract.schema.json").is_file())
            tools = (output / "tools.html").read_text(encoding="utf-8")
            self.assertIn("storage-search-labs", tools)
            self.assertIn("storage-cleanup.html", tools)
            copied = json.loads((output / "data" / "search-operator-registry.json").read_text(encoding="utf-8"))
            self.assertEqual(copied["source"]["id"], "inventory-search")
            self.assertFalse(copied["boolean"]["grouping_supported"])


if __name__ == "__main__":
    unittest.main()
