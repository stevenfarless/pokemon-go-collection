from scripts import lab_asset_pipeline


def test_share_packet_handoff_is_available_on_generated_pages(tmp_path):
    for name in ("index.html", "tools.html", "event-calendar.html", "pvp-battle-lab.html"):
        (tmp_path / name).write_text("<html><body><main>test</main></body></html>\n", encoding="utf-8")

    lab_asset_pipeline._rewrite_html(tmp_path, {})

    for name in ("index.html", "tools.html", "event-calendar.html", "pvp-battle-lab.html"):
        source = (tmp_path / name).read_text(encoding="utf-8")
        assert source.count('data-share-packets') == 1
        assert 'src="assets/share-packets.js"' in source


def test_share_packet_injection_is_idempotent(tmp_path):
    page = tmp_path / "index.html"
    page.write_text("<html><body><main>test</main></body></html>\n", encoding="utf-8")

    lab_asset_pipeline._rewrite_html(tmp_path, {})
    first = page.read_text(encoding="utf-8")
    lab_asset_pipeline._rewrite_html(tmp_path, {})
    second = page.read_text(encoding="utf-8")

    assert first == second
    assert second.count('data-share-packets') == 1
