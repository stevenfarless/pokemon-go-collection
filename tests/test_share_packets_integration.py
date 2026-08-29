from scripts import lab_asset_pipeline


def test_handoff_bridge_is_global_but_full_packet_engine_is_tools_only(tmp_path):
    names = ("index.html", "tools.html", "event-calendar.html", "pvp-battle-lab.html")
    for name in names:
        (tmp_path / name).write_text("<html><body><main>test</main></body></html>\n", encoding="utf-8")

    lab_asset_pipeline._rewrite_html(tmp_path, {})

    for name in names:
        source = (tmp_path / name).read_text(encoding="utf-8")
        assert source.count("data-glossary-experience") == 1
    tools = (tmp_path / "tools.html").read_text(encoding="utf-8")
    assert tools.count("data-share-packets") == 1
    assert "data-share-current" not in tools
    event = (tmp_path / "event-calendar.html").read_text(encoding="utf-8")
    assert 'data-share-type="event-plan"' in event
    pvp = (tmp_path / "pvp-battle-lab.html").read_text(encoding="utf-8")
    assert 'data-share-type="team"' in pvp
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert 'data-share-type="pokemon-decision"' in index
    for name in ("index.html", "event-calendar.html", "pvp-battle-lab.html"):
        source = (tmp_path / name).read_text(encoding="utf-8")
        assert "data-share-current" in source
        assert "data-share-packets" not in source


def test_packet_type_mapping_is_deterministic():
    assert lab_asset_pipeline._share_packet_type("trade-matcher.html") == "trade-shortlist"
    assert lab_asset_pipeline._share_packet_type("diagnostics.html") == "diagnostic"
    assert lab_asset_pipeline._share_packet_type("scan-inbox.html") == "rescan-request"
    assert lab_asset_pipeline._share_packet_type("storage-cleanup.html") == "resource-plan"
    assert lab_asset_pipeline._share_packet_type("collection.html") == "pokemon-decision"


def test_asset_injection_is_idempotent(tmp_path):
    page = tmp_path / "tools.html"
    page.write_text("<html><body><main>test</main></body></html>\n", encoding="utf-8")

    lab_asset_pipeline._rewrite_html(tmp_path, {})
    first = page.read_text(encoding="utf-8")
    lab_asset_pipeline._rewrite_html(tmp_path, {})
    second = page.read_text(encoding="utf-8")

    assert first == second
    assert second.count("data-glossary-experience") == 1
    assert second.count("data-share-packets") == 1
