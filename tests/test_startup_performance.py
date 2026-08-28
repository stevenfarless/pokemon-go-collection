import json
from pathlib import Path

from scripts import startup_performance


def _record():
    return {
        "pokemon_number": 25,
        "name": "Pikachu",
        "form": "Normal",
        "gender": "Male",
        "cp": 500,
        "hp": 60,
        "ivs": {
            "average_percent": 95.56,
            "total": 43,
            "attack": 15,
            "defense": 14,
            "stamina": 14,
            "is_hundo": False,
            "is_nundo": False,
            "scan_confidence": "unused",
        },
        "level": {"minimum": 20, "maximum": 50, "estimate": "unused"},
        "moves": {"fast": "Quick Attack", "charged": "Surf", "charged_second": None, "legacy": ["unused"]},
        "status": {
            "shadow_purified": "normal",
            "lucky": False,
            "favorite": True,
            "marked_for_pvp": False,
            "unused": True,
        },
        "pvp": {
            league: {
                "rank_percent": 99.0,
                "rank_number": 1,
                "stat_product": 1234.5,
                "dust_cost": 10000,
                "candy_cost": 20,
                "evolution_name": "Raichu",
                "evolution_form": "Normal",
                "status": "normal",
                "unused": "large detail",
            }
            for league in ("great", "ultra", "little")
        },
        "dates": {"catch": "2026-01-01", "scan": "2026-01-02", "original_scan": "2026-01-01", "unused": "x"},
        "size": {"weight": 6.0, "height": 0.4, "unused": "x"},
        "dust": 2500,
        "identity": {"record_id": "full-record-only"},
        "provenance": {"raw": "large full-record-only data"},
    }


def test_compact_record_keeps_collection_fields_and_drops_detail_only_metadata():
    compact = startup_performance.compact_record(_record())

    assert compact["name"] == "Pikachu"
    assert compact["ivs"]["attack"] == 15
    assert compact["pvp"]["great"]["rank_percent"] == 99.0
    assert compact["dates"]["scan"] == "2026-01-02"
    assert "scan_confidence" not in compact["ivs"]
    assert "unused" not in compact["pvp"]["great"]
    assert "identity" not in compact
    assert "provenance" not in compact


def test_prepare_publishes_content_hashed_startup_view_and_rehashes_app(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "assets").mkdir()
    (tmp_path / "data" / "pokemon.json").write_text(
        json.dumps({"records": [_record()]}),
        encoding="utf-8",
    )
    old_app = "assets/app.aaaaaaaaaaaa.js"
    (tmp_path / old_app).write_text(
        'async function load(){return fetch("data/pokemon.json?v=abcdef123456");}\n',
        encoding="utf-8",
    )
    for filename in ("index.html", "404.html"):
        (tmp_path / filename).write_text(
            f'<script defer src="{old_app}"></script>\n',
            encoding="utf-8",
        )
    manifest = {
        "build_id": "abcdef123456",
        "source_file": "shared-text-2026-08-27.csv",
        "assets": {"app": old_app},
    }

    startup_path = startup_performance.prepare(tmp_path, manifest)

    assert startup_path.startswith("data/collection-startup.")
    assert startup_path.endswith(".json")
    startup_payload = json.loads((tmp_path / startup_path).read_text(encoding="utf-8"))
    assert startup_payload["build_id"] == "abcdef123456"
    assert startup_payload["record_count"] == 1
    assert startup_payload["records"] == [startup_performance.compact_record(_record())]
    assert not (tmp_path / old_app).exists()
    new_app = manifest["assets"]["app"]
    assert new_app != old_app
    assert f'fetch("{startup_path}")' in (tmp_path / new_app).read_text(encoding="utf-8")
    for filename in ("index.html", "404.html"):
        html = (tmp_path / filename).read_text(encoding="utf-8")
        assert new_app in html
        assert old_app not in html


def test_finalize_inlines_collection_platform_css_and_omits_unmounted_action_workflows(tmp_path: Path):
    (tmp_path / "assets").mkdir()
    assets = {
        "design_system_styles": "assets/design-system.111111111111.css",
        "platform_styles": "assets/platform.222222222222.css",
        "product_experience_styles": "assets/product-experience.333333333333.css",
        "action_workflows_styles": "assets/action-workflows.444444444444.css",
        "action_workflows": "assets/action-workflows.555555555555.js",
    }
    for key, relative in assets.items():
        content = f".{key}{{display:block}}" if relative.endswith(".css") else "globalThis.actionWorkflowsLoaded = true;"
        (tmp_path / relative).write_text(content, encoding="utf-8")

    html = "\n".join([
        f'<link rel="stylesheet" href="{assets["design_system_styles"]}" data-platform-style="design_system_styles">',
        f'<link rel="stylesheet" href="{assets["platform_styles"]}" data-platform-style="platform_styles">',
        f'<link rel="stylesheet" href="{assets["product_experience_styles"]}" data-platform-style="product_experience_styles">',
        f'<link rel="stylesheet" href="{assets["action_workflows_styles"]}" data-platform-style="action_workflows_styles">',
        f'<script defer src="{assets["action_workflows"]}" data-platform-script="action_workflows"></script>',
    ])
    (tmp_path / "index.html").write_text(html, encoding="utf-8")

    startup_performance.finalize(tmp_path, {"assets": assets})

    result = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert result.count("data-startup-inline-css") == 3
    for key in startup_performance.PLATFORM_INLINE_STYLE_KEYS:
        assert f'data-platform-style="{key}"' in result
        assert (tmp_path / assets[key]).read_text(encoding="utf-8") in result
    assert "action_workflows_styles" not in result
    assert 'data-platform-script="action_workflows"' not in result
