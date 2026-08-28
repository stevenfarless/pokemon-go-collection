from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import trade_resource_labs


class TradeResourceLabPublisherTests(unittest.TestCase):
    def test_contracts_fail_closed_and_keep_guest_ephemeral(self) -> None:
        manifest = {"build_id": "abcdef123456"}
        trade = trade_resource_labs.build_trade_contract(manifest)
        vault = trade_resource_labs.build_resource_contract(manifest)
        self.assertFalse(trade["privacy"]["guest_bytes_leave_browser"])
        self.assertFalse(trade["privacy"]["guest_rows_persisted"])
        self.assertTrue(trade["matching"]["unknown_blocks_expendable_claim"])
        self.assertEqual(trade["inputs"]["player_b"]["preflight_contract"], "data/preflight-contract.json")
        self.assertEqual(trade["matching"]["filters"]["scope"], "current in-memory guest comparison only")
        self.assertFalse(trade["matching"]["filters"]["manual_exclusions_persisted"])
        self.assertIn("unknown", trade["matching"]["filters"]["rarity"])
        self.assertEqual(vault["semantics"]["missing_balance"], "unknown, never zero")
        self.assertTrue(vault["storage"]["unified_backup"])
        self.assertFalse(vault["safety"]["infer_balances_from_collection"])
        self.assertFalse(vault["safety"]["double_spend_silent"])

    def test_publish_writes_pages_schemas_and_tools_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir(parents=True)
            (root / "tools.html").write_text("<html><body><main>Tools\n  </main></body></html>", encoding="utf-8")
            (root / "llms.txt").write_text("bootstrap\n", encoding="utf-8")
            result = trade_resource_labs.publish(Path(directory), root, {"build_id": "abcdef123456"})
            self.assertEqual(result["labs"]["trade_matcher"]["issue"], 147)
            self.assertEqual(result["labs"]["resource_vault"]["issue"], 148)
            trade_page = (root / "trade-matcher.html")
            self.assertTrue(trade_page.is_file())
            self.assertIn("assets/trade-matcher-filters.js", trade_page.read_text(encoding="utf-8"))
            self.assertTrue((root / "resource-vault.html").is_file())
            tools = (root / "tools.html").read_text(encoding="utf-8")
            self.assertIn("trade-resource-labs", tools)
            self.assertIn("data-trade-resource-tools", tools)
            trade = json.loads((root / "data" / "trade-matcher-contract.json").read_text(encoding="utf-8"))
            vault = json.loads((root / "data" / "resource-vault-contract.json").read_text(encoding="utf-8"))
            self.assertEqual(trade["build_id"], "abcdef123456")
            self.assertFalse(trade["matching"]["filters"]["manual_exclusions_persisted"])
            self.assertEqual(vault["storage"]["key"], "pokemon-go-collection:resource-vault:v1")
            self.assertTrue((root / "data" / "trade-matcher-contract.schema.json").is_file())
            self.assertTrue((root / "data" / "resource-vault-contract.schema.json").is_file())


if __name__ == "__main__":
    unittest.main()
