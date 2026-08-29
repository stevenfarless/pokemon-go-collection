"""Build-time registry and publication for external source/license provenance.

The registry is intentionally repository-owned and fail-closed. Provider inputs,
pinned community knowledge, build dependencies, and runtime-loaded third-party
assets are checked before provenance is published. Human-readable credits and
the machine index are generated from the same reviewed source records.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any, Mapping

REGISTRY_SCHEMA_VERSION = "1.0.0"
REGISTRY_PATH = Path("knowledge/source-registry.json")
PROVENANCE_PATH = Path("data/provenance/index.json")
CREDITS_PATH = Path("credits.html")

_REQUIRED_GROUPS = (
    "source",
    "review",
    "attribution",
    "permissions",
    "acquisition",
    "production",
    "replacement",
)

_REMOTE_ASSET_PATTERNS = (
    re.compile(r"<script\b[^>]*\bsrc=[\"']https?://", re.IGNORECASE),
    re.compile(r"<link\b[^>]*\bhref=[\"']https?://", re.IGNORECASE),
    re.compile(r"<(?:img|source)\b[^>]*\bsrc=[\"']https?://", re.IGNORECASE),
    re.compile(r"url\(\s*[\"']?https?://", re.IGNORECASE),
    re.compile(r"@import\s+(?:url\()?\s*[\"']?https?://", re.IGNORECASE),
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _require_string(mapping: Mapping[str, Any], field: str, context: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}.{field} must be a non-empty string")
    return value


def _git_blob_sha(path: Path) -> str:
    content = path.read_bytes()
    prefix = f"blob {len(content)}\0".encode()
    return hashlib.sha1(prefix + content).hexdigest()


def load_registry(repository_root: Path) -> dict[str, Any]:
    path = repository_root / REGISTRY_PATH
    if not path.is_file():
        raise ValueError(f"Reviewed source registry is missing: {REGISTRY_PATH.as_posix()}")
    return _read_json(path)


def _source_by_id(registry: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    sources = registry.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("source registry requires a non-empty sources array")
    by_id: dict[str, Mapping[str, Any]] = {}
    for index, source in enumerate(sources):
        if not isinstance(source, Mapping):
            raise ValueError(f"source registry sources[{index}] must be an object")
        source_id = _require_string(source, "id", f"sources[{index}]")
        if source_id in by_id:
            raise ValueError(f"source registry contains duplicate source id {source_id!r}")
        by_id[source_id] = source
    return by_id


def _validate_source_entry(source: Mapping[str, Any], repository_root: Path) -> None:
    source_id = _require_string(source, "id", "source")
    for group in _REQUIRED_GROUPS:
        if not isinstance(source.get(group), Mapping):
            raise ValueError(f"source {source_id!r} requires object {group!r}")

    source_meta = source["source"]
    _require_string(source_meta, "project", f"source {source_id}.source")
    _require_string(source_meta, "url", f"source {source_id}.source")
    exact_version = _require_string(source_meta, "exact_version", f"source {source_id}.source")
    _require_string(source_meta, "version_date", f"source {source_id}.source")

    review = source["review"]
    if review.get("status") != "reviewed":
        raise ValueError(f"source {source_id!r} is not marked reviewed")
    _require_string(review, "reviewed_at", f"source {source_id}.review")
    _require_string(review, "basis", f"source {source_id}.review")
    _require_string(review, "reference", f"source {source_id}.review")

    attribution = source["attribution"]
    if not isinstance(attribution.get("required"), bool):
        raise ValueError(f"source {source_id!r} attribution.required must be boolean")
    _require_string(attribution, "text", f"source {source_id}.attribution")
    notice_path = attribution.get("notice_path")
    if notice_path is not None:
        if not isinstance(notice_path, str) or not notice_path:
            raise ValueError(f"source {source_id!r} attribution.notice_path must be null or a path")
        if not (repository_root / notice_path).is_file():
            raise ValueError(f"source {source_id!r} required notice is missing: {notice_path}")

    permissions = source["permissions"]
    if not isinstance(permissions.get("redistribution_allowed"), bool):
        raise ValueError(f"source {source_id!r} permissions.redistribution_allowed must be boolean")
    if not isinstance(permissions.get("modification_allowed"), bool):
        raise ValueError(f"source {source_id!r} permissions.modification_allowed must be boolean")
    _require_string(permissions, "redistribution_scope", f"source {source_id}.permissions")
    for field in ("upstream_prose_included", "upstream_images_included", "upstream_visual_assets_included"):
        if not isinstance(permissions.get(field), bool):
            raise ValueError(f"source {source_id!r} permissions.{field} must be boolean")

    _require_string(source, "classification", f"source {source_id}")
    _require_string(source, "authority", f"source {source_id}")

    acquisition = source["acquisition"]
    _require_string(acquisition, "method", f"source {source_id}.acquisition")
    for field in ("automated_source_access", "runtime_network_required"):
        if not isinstance(acquisition.get(field), bool):
            raise ValueError(f"source {source_id!r} acquisition.{field} must be boolean")

    production = source["production"]
    if not isinstance(production.get("active"), bool):
        raise ValueError(f"source {source_id!r} production.active must be boolean")
    provider_ids = production.get("provider_ids")
    governed_paths = production.get("governed_paths")
    if not isinstance(provider_ids, list) or not all(isinstance(value, str) and value for value in provider_ids):
        raise ValueError(f"source {source_id!r} production.provider_ids must be a string array")
    if not isinstance(governed_paths, list) or not governed_paths:
        raise ValueError(f"source {source_id!r} production.governed_paths must be a non-empty string array")
    for governed in governed_paths:
        if not isinstance(governed, str) or not governed:
            raise ValueError(f"source {source_id!r} contains an invalid governed path")
        if not (repository_root / governed).exists():
            raise ValueError(f"source {source_id!r} governed path is missing: {governed}")

    replacement = source["replacement"]
    _require_string(replacement, "remove_or_replace", f"source {source_id}.replacement")

    fingerprint_path = source_meta.get("fingerprint_path")
    if fingerprint_path is not None:
        if not isinstance(fingerprint_path, str) or not fingerprint_path:
            raise ValueError(f"source {source_id!r} source.fingerprint_path must be a path")
        fingerprint_target = repository_root / fingerprint_path
        if not fingerprint_target.is_file():
            raise ValueError(f"source {source_id!r} fingerprint path is missing: {fingerprint_path}")
        expected = exact_version.removeprefix("git-blob:")
        if not exact_version.startswith("git-blob:") or _git_blob_sha(fingerprint_target) != expected:
            raise ValueError(
                f"source {source_id!r} reviewed fingerprint no longer matches {fingerprint_path}; "
                "review the changed external input and update the registry"
            )


def _validate_pvpoke_lock(registry: Mapping[str, Any], repository_root: Path) -> None:
    by_id = _source_by_id(registry)
    source = by_id.get("pvpoke-stable-knowledge")
    if source is None:
        raise ValueError("pinned PvPoke knowledge lacks reviewed source registry entry")
    lock = _read_json(repository_root / "knowledge" / "source-lock.json")
    lock_source = lock.get("source") or {}
    if lock_source.get("commit") != source["source"].get("exact_version"):
        raise ValueError("PvPoke source-lock commit differs from reviewed source registry")
    if lock_source.get("commit_date") != source["source"].get("version_date"):
        raise ValueError("PvPoke source-lock date differs from reviewed source registry")
    if lock_source.get("license") != source["review"].get("basis"):
        raise ValueError("PvPoke source-lock license differs from reviewed source registry")


def _provider_files(repository_root: Path) -> list[Path]:
    providers = repository_root / "external" / "providers"
    return sorted(providers.glob("*.json")) if providers.is_dir() else []


def _validate_provider_coverage(registry: Mapping[str, Any], repository_root: Path) -> None:
    by_id = _source_by_id(registry)
    provider_owners: dict[str, list[Mapping[str, Any]]] = {}
    for source in by_id.values():
        production = source["production"]
        if not production.get("active"):
            continue
        for provider_id in production.get("provider_ids", []):
            provider_owners.setdefault(str(provider_id), []).append(source)

    active_provider_ids: set[str] = set()
    for path in _provider_files(repository_root):
        payload = _read_json(path)
        provider_id = _require_string(payload, "provider", path.as_posix())
        active_provider_ids.add(provider_id)
        owners = provider_owners.get(provider_id, [])
        if len(owners) != 1:
            raise ValueError(
                f"production provider {provider_id!r} in {path.relative_to(repository_root)} requires exactly one "
                "active reviewed source registry entry"
            )
        owner = owners[0]
        license_info = payload.get("license")
        if not isinstance(license_info, Mapping):
            raise ValueError(f"production provider {provider_id!r} lacks explicit license metadata")
        if license_info.get("redistribution_permitted") is not True:
            raise ValueError(f"production provider {provider_id!r} is not explicitly redistributable")
        if owner["review"].get("status") != "reviewed" or owner["permissions"].get("redistribution_allowed") is not True:
            raise ValueError(f"production provider {provider_id!r} lacks reviewed central redistribution approval")
        acquisition = payload.get("acquisition") or {}
        automated = acquisition.get("automated_source_scraping")
        if automated is not False:
            raise ValueError(f"production provider {provider_id!r} must explicitly disable automated source scraping")
        if owner["acquisition"].get("automated_source_access") is False and automated is not False:
            raise ValueError(f"production provider {provider_id!r} conflicts with its reviewed acquisition policy")

    for provider_id in provider_owners:
        if provider_id not in active_provider_ids:
            raise ValueError(
                f"active reviewed provider {provider_id!r} has no production provider file; "
                "remove/deactivate its registry claim with the source"
            )


def _parse_requirements(path: Path) -> list[dict[str, str]]:
    packages: list[dict[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            raise ValueError(f"Direct Python requirement must be exactly pinned with ==: {line}")
        name, version = (part.strip() for part in line.split("==", 1))
        if not name or not version:
            raise ValueError(f"Invalid direct Python requirement: {line}")
        packages.append({"name": name, "version": version})
    return packages


def _python_dependency_inventory(registry: Mapping[str, Any], repository_root: Path) -> list[dict[str, str]]:
    source = _source_by_id(registry).get("python-build-test-dependencies")
    if source is None:
        raise ValueError("Direct Python build/test dependencies lack a reviewed source registry entry")
    reviewed = source.get("packages")
    if not isinstance(reviewed, list):
        raise ValueError("python-build-test-dependencies requires a reviewed packages array")
    reviewed_by_key: dict[tuple[str, str], str] = {}
    for package in reviewed:
        if not isinstance(package, Mapping):
            raise ValueError("reviewed Python dependency entry must be an object")
        name = _require_string(package, "name", "reviewed Python dependency")
        version = _require_string(package, "version", f"reviewed Python dependency {name}")
        license_name = _require_string(package, "license", f"reviewed Python dependency {name}")
        reviewed_by_key[(name.lower(), version)] = license_name

    actual = _parse_requirements(repository_root / "requirements-dev.txt")
    actual_keys = {(item["name"].lower(), item["version"]) for item in actual}
    if actual_keys != set(reviewed_by_key):
        raise ValueError(
            "requirements-dev.txt differs from the reviewed Python dependency inventory; "
            "review dependency license metadata and update the source registry"
        )
    return [
        {
            "name": item["name"],
            "version": item["version"],
            "license": reviewed_by_key[(item["name"].lower(), item["version"])],
            "scope": "build/test-only",
        }
        for item in actual
    ]


def _node_dependency_inventory(repository_root: Path) -> list[dict[str, Any]]:
    lock = _read_json(repository_root / "package-lock.json")
    packages = lock.get("packages")
    if not isinstance(packages, Mapping):
        raise ValueError("package-lock.json packages must be an object")
    inventory: list[dict[str, Any]] = []
    for location, package in sorted(packages.items()):
        if not location or "node_modules/" not in location or not isinstance(package, Mapping):
            continue
        name = location.rsplit("node_modules/", 1)[-1]
        version = package.get("version")
        if not isinstance(version, str) or not version:
            raise ValueError(f"npm dependency {name!r} lacks an exact lockfile version")
        license_value = package.get("license")
        if isinstance(license_value, str) and license_value:
            license_name = license_value
        else:
            license_name = "not-declared-in-lockfile"
        inventory.append(
            {
                "name": name,
                "version": version,
                "license": license_name,
                "resolved": package.get("resolved"),
                "integrity": package.get("integrity"),
                "scope": "build/test-only",
            }
        )
    return inventory


def scan_runtime_external_assets(repository_root: Path) -> list[dict[str, str]]:
    """Find third-party resources loaded directly by source HTML/CSS at runtime."""
    findings: list[dict[str, str]] = []
    site_dir = repository_root / "site"
    for path in sorted(site_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".html", ".css"}:
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in _REMOTE_ASSET_PATTERNS:
            match = pattern.search(text)
            if match:
                findings.append(
                    {
                        "path": path.relative_to(repository_root).as_posix(),
                        "match": match.group(0),
                    }
                )
                break
    return findings


def validate_registry(registry: Mapping[str, Any], repository_root: Path) -> None:
    if registry.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        raise ValueError(f"source registry schema_version must be {REGISTRY_SCHEMA_VERSION}")
    _require_string(registry, "last_reviewed", "source registry")
    policy = registry.get("policy")
    if not isinstance(policy, Mapping):
        raise ValueError("source registry requires policy object")
    if policy.get("unregistered_production_external_input") != "fail-build":
        raise ValueError("source registry must fail builds for unregistered production external inputs")
    if policy.get("unreviewed_redistribution_required_input") != "fail-build":
        raise ValueError("source registry must fail builds for unreviewed redistribution-required inputs")

    by_id = _source_by_id(registry)
    for source in by_id.values():
        _validate_source_entry(source, repository_root)
    _validate_pvpoke_lock(registry, repository_root)
    _validate_provider_coverage(registry, repository_root)
    _python_dependency_inventory(registry, repository_root)

    remote_assets = scan_runtime_external_assets(repository_root)
    if remote_assets:
        first = remote_assets[0]
        raise ValueError(
            "Unreviewed remote runtime asset detected at "
            f"{first['path']}: {first['match']}. Register and explicitly permit it before production use."
        )


def _credits_html(registry: Mapping[str, Any], node_count: int, python_count: int) -> str:
    source_sections: list[str] = []
    for source in registry["sources"]:
        source_meta = source["source"]
        review = source["review"]
        attribution = source["attribution"]
        permissions = source["permissions"]
        acquisition = source["acquisition"]
        source_sections.append(
            "<section class=\"source\">"
            f"<h2>{html.escape(source_meta['project'])}</h2>"
            f"<p><strong>Registry ID:</strong> <code>{html.escape(source['id'])}</code></p>"
            f"<p><strong>Version/review target:</strong> {html.escape(source_meta['exact_version'])} "
            f"({html.escape(source_meta['version_date'])})</p>"
            f"<p><strong>Classification:</strong> {html.escape(source['classification'])}. "
            f"{html.escape(source['authority'])}</p>"
            f"<p><strong>License/terms basis:</strong> {html.escape(review['basis'])}</p>"
            f"<p><strong>Attribution:</strong> {html.escape(attribution['text'])}</p>"
            f"<p><strong>Redistribution boundary:</strong> {html.escape(permissions['redistribution_scope'])}</p>"
            f"<p><strong>Acquisition:</strong> {html.escape(acquisition['method'])}</p>"
            f"<p><strong>If terms change:</strong> {html.escape(source['replacement']['remove_or_replace'])}</p>"
            f"<p><a href=\"{html.escape(source_meta['url'], quote=True)}\" rel=\"noreferrer\">Source project</a> · "
            f"<a href=\"{html.escape(review['reference'], quote=True)}\" rel=\"noreferrer\">Reviewed terms/license reference</a></p>"
            "</section>"
        )
    sections = "\n".join(source_sections)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Credits &amp; Data Sources</title>
  <style>
    :root {{ color-scheme: light dark; font-family: system-ui, sans-serif; line-height: 1.5; }}
    body {{ max-width: 72rem; margin: 0 auto; padding: 1.5rem; }}
    a {{ color: LinkText; }}
    code {{ overflow-wrap: anywhere; }}
    .source {{ border-top: 1px solid GrayText; padding-block: 1rem; }}
    .notice {{ padding: 1rem; border: 1px solid GrayText; border-radius: .5rem; }}
  </style>
</head>
<body>
  <main>
    <h1>Credits &amp; Data Sources</h1>
    <p class="notice">This is an unofficial fan-maintained collection project. Source names and identifiers document provenance and do not imply endorsement. The repository excludes official article prose, artwork, sprites, icons, logos, and screenshots from its external-data pipeline.</p>
    <p>Registry review date: {html.escape(str(registry['last_reviewed']))}. Machine-readable provenance: <a href="data/provenance/index.json"><code>data/provenance/index.json</code></a>.</p>
    <p>Build/test dependency inventory: {node_count} locked npm packages and {python_count} pinned direct Python packages. These tools are not loaded from third-party origins by the static site at runtime.</p>
    {sections}
  </main>
</body>
</html>
"""


def _inject_credits_link(output_dir: Path) -> None:
    index_path = output_dir / "index.html"
    if not index_path.is_file():
        raise ValueError("Generated index.html is missing before source-registry publication")
    source = index_path.read_text(encoding="utf-8")
    if "credits.html" in source:
        return
    marker = "</footer>"
    if marker not in source:
        raise ValueError("Generated index.html has no footer for Credits/Data Sources link")
    link = '      <p><a href="credits.html">Credits &amp; Data Sources</a></p>\n    '
    index_path.write_text(source.replace(marker, link + marker, 1), encoding="utf-8", newline="\n")


def publish_source_registry(repository_root: Path, output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Validate all reviewed external inputs and publish credits/provenance artifacts."""
    registry = load_registry(repository_root)
    validate_registry(registry, repository_root)
    node_dependencies = _node_dependency_inventory(repository_root)
    python_dependencies = _python_dependency_inventory(registry, repository_root)
    remote_assets = scan_runtime_external_assets(repository_root)

    provenance = {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "build_id": manifest.get("build_id"),
        "generated_at": manifest.get("generated_at_utc"),
        "registry_reviewed_at": registry["last_reviewed"],
        "policy": registry["policy"],
        "inventory_status": registry.get("inventory_status", {}),
        "source_count": len(registry["sources"]),
        "sources": registry["sources"],
        "dependencies": {
            "npm_lockfile": {
                "path": "package-lock.json",
                "package_count": len(node_dependencies),
                "packages": node_dependencies,
            },
            "python_direct": {
                "path": "requirements-dev.txt",
                "package_count": len(python_dependencies),
                "packages": python_dependencies,
            },
        },
        "runtime_external_asset_audit": {
            "status": "clear" if not remote_assets else "blocked",
            "finding_count": len(remote_assets),
            "findings": remote_assets,
        },
        "human_readable": CREDITS_PATH.as_posix(),
        "registry_source": REGISTRY_PATH.as_posix(),
    }
    _write_json(output_dir / PROVENANCE_PATH, provenance)
    (output_dir / CREDITS_PATH).write_text(
        _credits_html(registry, len(node_dependencies), len(python_dependencies)),
        encoding="utf-8",
        newline="\n",
    )
    _inject_credits_link(output_dir)
    return provenance
