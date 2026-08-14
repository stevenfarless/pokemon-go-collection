from __future__ import annotations

import unittest
from pathlib import Path

from scripts import foundation_build


ROOT = Path(__file__).resolve().parents[1]


class ConnectivityProbeTests(unittest.TestCase):
    def test_probe_uses_get_manifest_instead_of_head_navigation(self) -> None:
        probe = foundation_build._OFFLINE_CONNECTIVITY_PROBE
        self.assertIn('new URL("data/build-manifest.json", location.href)', probe)
        self.assertIn('target.searchParams.set("connectivity"', probe)
        self.assertIn('method: "GET"', probe)
        self.assertNotIn('method: "HEAD"', probe)
        self.assertNotIn('fetch(location.href', probe)

    def test_service_worker_keeps_connectivity_probe_network_only(self) -> None:
        service_worker = (ROOT / "site" / "sw.js").read_text(encoding="utf-8")
        network_only = 'if (url.searchParams.has("connectivity"))'
        data_branch = 'const isData = url.pathname.includes("/data/")'
        self.assertIn(network_only, service_worker)
        self.assertIn('event.respondWith(fetch(event.request));', service_worker)
        self.assertLess(service_worker.index(network_only), service_worker.index(data_branch))


if __name__ == "__main__":
    unittest.main()
