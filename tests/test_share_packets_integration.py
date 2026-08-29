from scripts import lab_asset_pipeline


def test_handoff_bridge_is_global_but_full_packet_engine_is_tools_only(tmp_path):
    names = ("index.html", "tools.html", "event-calendar.html", "pvp-battle-lab.html")
    for name in names:
        (tmp_path / name).write_text("<html><body><main>test</main></body></html>\n", encoding="utf-8")

    lab_asset_pipeline._rewrite_html(tmp_path, {})

    for name in names:
        source = (tmp_path / name).read_text(encoding="utf-8")
        assert source.count("data-glossary-experience") == 1
    assert (tmp_path / "tools.html").read_text(encoding="utf-8").count("data-share-packets") == 1
    for name in ("index.html", "event-calendar.html", "pvp-battle-lab.html"):
        assert "data-share-packets" not in (tmp_path / name).read_text(encoding="utf-8")


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
