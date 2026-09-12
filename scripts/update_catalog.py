#!/usr/bin/env python3
"""Build live ramdisk catalog for README.md + catalog/catalog.json from GitHub Releases."""
from __future__ import annotations

import json
import os
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = os.environ.get("GITHUB_REPOSITORY", "smartmaster35rus-dev/ramdisk-A12-13")
ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
CATALOG_JSON = ROOT / "catalog" / "catalog.json"
MARK_START = "<!-- catalog:start -->"
MARK_END = "<!-- catalog:end -->"

TAG_RE = re.compile(r"^(i(?:Phone|Pad)\d+\.\d+)-iOS(\d+)$")
ASSET_RE = re.compile(
    r"^(i(?:Phone|Pad)\d+\.\d+)-([\d.]+(?:beta\d*)?)-ramdisk\.tar\.zip$"
)

DEVICE_META: dict[str, tuple[str, str, str]] = {
    "iPhone11,2": ("iPhone XS", "A12", "📱"),
    "iPhone11,4": ("iPhone XS Max", "A12", "📱"),
    "iPhone11,6": ("iPhone 11 (A12)", "A12", "📱"),
    "iPhone11,8": ("iPhone XR", "A12", "📱"),
    "iPhone12,1": ("iPhone 11", "A13", "📱"),
    "iPhone12,3": ("iPhone 11 Pro", "A13", "📱"),
    "iPhone12,5": ("iPhone 11 Pro Max", "A13", "📱"),
    "iPhone12,8": ("iPhone SE (2nd gen)", "A13", "📱"),
    "iPad11,1": ("iPad mini 5 (Wi‑Fi)", "A12", "📲"),
    "iPad11,2": ("iPad mini 5 (Cellular)", "A12", "📲"),
    "iPad11,3": ("iPad Air 3 (Wi‑Fi)", "A12", "📲"),
    "iPad11,4": ("iPad Air 3 (Cellular)", "A12", "📲"),
    "iPad11,6": ("iPad 8 (Wi‑Fi)", "A12", "📲"),
    "iPad11,7": ("iPad 8 (Cellular)", "A12", "📲"),
    "iPad12,1": ("iPad 9 (Wi‑Fi)", "A13", "📲"),
    "iPad12,2": ("iPad 9 (Cellular)", "A13", "📲"),
}

IOS_COLORS = {
    "12": "6e6e73",
    "13": "8e8e93",
    "14": "aeaeb2",
    "18": "007AFF",
    "26": "BF5AF2",
    "27": "FF9500",
}


def _sort_key(ver: str) -> tuple:
    parts = []
    for p in ver.replace("beta", ".beta.").split("."):
        if p == "beta":
            parts.append(-1)
        elif p.isdigit():
            parts.append(int(p))
        else:
            parts.append(p)
    return tuple(parts)


def _dotted_to_product(dotted: str) -> str:
    m = re.match(r"^(i(?:Phone|Pad)\d+)\.(\d+)$", dotted)
    return f"{m.group(1)},{m.group(2)}" if m else dotted.replace(".", ",", 1)


def _product_to_dotted(product: str) -> str:
    return product.replace(",", ".")


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl._create_unverified_context()


def _fetch_releases_gh_cli() -> list[dict]:
    out = subprocess.check_output(
        ["gh", "api", f"repos/{REPO}/releases", "--paginate"],
        text=True,
    )
    return json.loads(out)


def _fetch_releases() -> list[dict]:
    if os.environ.get("USE_GH_CLI", "1") == "1":
        try:
            return _fetch_releases_gh_cli()
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ramdisk-catalog-updater/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    releases: list[dict] = []
    page = 1
    ctx = _ssl_context()
    while True:
        url = f"https://api.github.com/repos/{REPO}/releases?per_page=100&page={page}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
                batch = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            print(f"GitHub API error: {e}", file=sys.stderr)
            raise
        if not batch:
            break
        releases.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return releases


def _build_catalog(releases: list[dict]) -> dict[str, dict[str, list[str]]]:
    """model (ProductType) -> major -> sorted versions."""
    catalog: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    for rel in releases:
        if rel.get("is_draft"):
            continue
        assets = rel.get("assets") or []
        if not assets:
            continue
        tag = rel.get("tag_name") or ""
        m = TAG_RE.match(tag)
        if not m:
            continue
        dotted, major = m.group(1), m.group(2)
        model = _dotted_to_product(dotted)

        for asset in assets:
            name = asset.get("name") or ""
            am = ASSET_RE.match(name)
            if am and am.group(1) == dotted:
                catalog[model][major].add(am.group(2))

    return {
        model: {
            major: sorted(vers, key=_sort_key, reverse=True)
            for major, vers in sorted(majors.items(), key=lambda x: int(x[0]))
        }
        for model, majors in sorted(catalog.items())
    }


def _badge(ver: str, major: str) -> str:
    color = IOS_COLORS.get(major, "555555")
    label = ver.replace(" ", "%20")
    return (
        f'<img alt="{ver}" title="iOS {ver}" '
        f'src="https://img.shields.io/badge/{label}-{color}?style=flat-square">'
    )


def _chip_badge(chip: str) -> str:
    color = "007AFF" if chip == "A12" else "BF5AF2"
    return f'<img alt="{chip}" src="https://img.shields.io/badge/{chip}-{color}?style=for-the-badge&logo=apple&logoColor=white">'


def _shields_badge(label: str, message: str, color: str, style: str = "flat-square") -> str:
    """shields.io path badges — dashes in message must be doubled."""
    safe_msg = message.replace("-", "--")
    return (
        f"https://img.shields.io/badge/{label}-{safe_msg}-{color}"
        f"?style={style}"
    )


def _render_catalog(catalog: dict[str, dict[str, list[str]]], stats: dict) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    date_badge = datetime.now(timezone.utc).strftime("%Y.%m.%d")
    lines: list[str] = []

    lines.append(
        f'<p align="center">'
        f'<img alt="models" src="{_shields_badge("models", str(stats["models"]), "007AFF", "for-the-badge")}"> '
        f'<img alt="releases" src="{_shields_badge("release_groups", str(stats["groups"]), "BF5AF2", "for-the-badge")}"> '
        f'<img alt="versions" src="{_shields_badge("ramdisk_versions", str(stats["versions"]), "34C759", "for-the-badge")}"> '
        f'<img alt="updated" src="{_shields_badge("updated", date_badge, "555555")}">'
        f"</p>\n"
    )

    lines.append(
        "> **Live catalog** — auto-refreshed from published GitHub Releases. "
        "Upload a new release → this table updates within minutes.\n"
    )

    # Group by family
    families: dict[str, list[str]] = defaultdict(list)
    for model in catalog:
        if model.startswith("iPhone"):
            fam = "iPhone"
        elif model.startswith("iPad"):
            fam = "iPad"
        else:
            fam = "Other"
        families[fam].append(model)

    family_icons = {"iPhone": "📱 iPhone", "iPad": "📲 iPad", "Other": "🛠 Devices"}

    for fam in ("iPhone", "iPad", "Other"):
        models = families.get(fam) or []
        if not models:
            continue
        lines.append(f"### {family_icons.get(fam, fam)}\n")

        for model in sorted(models):
            name, chip, icon = DEVICE_META.get(
                model, (_product_to_dotted(model), "?", "🔹")
            )
            majors = catalog[model]
            total_v = sum(len(v) for v in majors.values())
            dotted = _product_to_dotted(model)
            lines.append(
                f"<details open>\n"
                f"<summary><b>{icon} {name}</b> "
                f'<code>{model}</code> {_chip_badge(chip)} '
                f'<img alt="{total_v} versions" '
                f'src="https://img.shields.io/badge/versions-{total_v}-34C759?style=flat-square"></summary>\n'
            )
            lines.append("")
            lines.append("| iOS line | Available builds | Download |")
            lines.append("|:--:|:--|:--:|")

            for major, vers in sorted(majors.items(), key=lambda x: int(x[0]), reverse=True):
                badges = " ".join(_badge(v, major) for v in vers)
                tag = f"{dotted}-iOS{major}"
                dl = f"[⬇ Release](https://github.com/{REPO}/releases/tag/{tag})"
                ios_label = f"**iOS {major}**"
                lines.append(f"| {ios_label} | {badges} | {dl} |")

            lines.append("")
            lines.append("</details>\n")

    lines.append(
        f"\n<sub>Catalog generated {now} · "
        f"[workflow](https://github.com/{REPO}/actions/workflows/update-catalog.yml)</sub>\n"
    )
    return "\n".join(lines)


def _stats(catalog: dict[str, dict[str, list[str]]]) -> dict[str, int]:
    versions = sum(len(v) for m in catalog.values() for v in m.values())
    groups = sum(len(m) for m in catalog.values())
    return {"models": len(catalog), "groups": groups, "versions": versions}


def _patch_readme(section: str) -> None:
    text = README.read_text(encoding="utf-8")
    if MARK_START not in text or MARK_END not in text:
        raise SystemExit(f"README missing {MARK_START} / {MARK_END} markers")
    before, rest = text.split(MARK_START, 1)
    _, after = rest.split(MARK_END, 1)
    README.write_text(
        f"{before.rstrip()}\n\n{MARK_START}\n{section.rstrip()}\n{MARK_END}\n{after.lstrip()}",
        encoding="utf-8",
    )


def main() -> int:
    releases = _fetch_releases()
    catalog = _build_catalog(releases)
    stats = _stats(catalog)

    meta = {
        "repo": REPO,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "models": catalog,
    }
    CATALOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_JSON.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    section = _render_catalog(catalog, stats)
    _patch_readme(section)

    print(f"OK catalog: {stats['models']} models, {stats['versions']} versions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
