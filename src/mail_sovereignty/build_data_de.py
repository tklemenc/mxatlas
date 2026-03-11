from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LAND_MAP = {
    "01": "Schleswig-Holstein",
    "02": "Hamburg",
    "03": "Niedersachsen",
    "04": "Bremen",
    "05": "Nordrhein-Westfalen",
    "06": "Hessen",
    "07": "Rheinland-Pfalz",
    "08": "Baden-Wuerttemberg",
    "09": "Bayern",
    "10": "Saarland",
    "11": "Berlin",
    "12": "Brandenburg",
    "13": "Mecklenburg-Vorpommern",
    "14": "Sachsen",
    "15": "Sachsen-Anhalt",
    "16": "Thueringen",
}

PUBLIC_IT_PROVIDERS = {
    "agenturserver",
    "bayern",
    "civitec",
    "cm-system",
    "ekom21",
    "kdo",
    "kdvz-nrw",
    "kgrz-kassel",
    "kommunale.it",
    "krz",
    "kvnbw",
    "landsh",
    "nolis",
    "pzd-svn",
    "regioit",
    "rlp",
    "verwaltungsportal",
}

COMMERCIAL_HOSTERS = {
    "all-inkl",
    "godaddy",
    "hetzner",
    "ionos",
    "itebo",
    "jimdo",
    "next-go",
    "rackspace",
    "server-he",
    "strato",
    "t-online",
    "udag",
}

CANONICAL_PROVIDER_DETAIL = {
    "civitec": "regioit",
}


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_json_list(value: Any) -> list[Any]:
    text = clean(value)
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def parse_json_obj(value: Any) -> dict[str, Any]:
    text = clean(value)
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def gkz8(value: Any) -> str:
    text = clean(value)
    return text.zfill(8) if text else ""


def bundesland_from_gkz8(value: str) -> str:
    return LAND_MAP.get(value[:2], "")


def map_provider_bucket(provider: str, platform: str, classification: str) -> str:
    provider = CANONICAL_PROVIDER_DETAIL.get(clean(provider), clean(provider))
    platform = clean(platform)
    classification = clean(classification)

    if provider == "microsoft" or platform == "m365":
        return "microsoft"
    if provider == "google" or platform == "google_workspace":
        return "google"
    if provider == "aws":
        return "aws"
    if provider in PUBLIC_IT_PROVIDERS:
        return "public-it"
    if classification in {"gateway_only", "gateway_fronted", "relay_fronted"} or platform == "gateway":
        return "gateway"
    if classification == "self_hosted" or provider == "self_hosted":
        return "self-hosted"
    if classification == "relay_hosted" or platform == "relay_hosted":
        return "relay"
    if provider in COMMERCIAL_HOSTERS or platform in {"hosted_exchange", "hosted_mail"}:
        return "hosted-provider"
    if provider in {"no_mx", "unknown", ""} or platform in {"no_mx", "unknown", ""}:
        return "unknown"
    return "unknown"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_input_path() -> Path:
    candidates = [
        repo_root() / "kommunen_mail_provider_classification.csv",
        repo_root().parent / "kommunen_mail_provider_classification.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def build_entry(row: dict[str, str]) -> dict[str, Any]:
    key = gkz8(row.get("kennzahl"))
    provider = CANONICAL_PROVIDER_DETAIL.get(clean(row.get("mail_provider")), clean(row.get("mail_provider")))
    platform = clean(row.get("mail_platform"))
    classification = clean(row.get("classification"))
    domain = clean(row.get("domaene"))

    mx_records = parse_json_list(row.get("root_mx_json"))
    spf_records = parse_json_list(row.get("root_spf_json"))
    spf_resolved = parse_json_list(row.get("root_spf_resolved_json"))
    autodiscover = parse_json_obj(row.get("autodiscover_json"))
    mx_details = parse_json_list(row.get("mx_host_details_json"))

    mx_asns: list[int] = []
    seen_asns: set[int] = set()
    for item in mx_details:
        if not isinstance(item, dict):
            continue
        for asn in item.get("asns", []):
            try:
                asn_int = int(str(asn))
            except ValueError:
                continue
            if asn_int not in seen_asns:
                seen_asns.add(asn_int)
                mx_asns.append(asn_int)

    entry: dict[str, Any] = {
        "gkz8": key,
        "name": clean(row.get("name")),
        "art": clean(row.get("art")),
        "bundesland": bundesland_from_gkz8(key),
        "domain": domain,
        "provider": map_provider_bucket(provider, platform, classification),
        "provider_detail": provider or "unknown",
        "platform": platform or "unknown",
        "classification": classification or "unknown",
        "confidence": clean(row.get("confidence")) or "unknown",
        "mx": mx_records,
        "spf": spf_records[0] if spf_records else "",
        "spf_resolved": " ".join(str(part) for part in spf_resolved if clean(part)),
        "mx_asns": mx_asns,
    }

    if autodiscover:
        entry["autodiscover"] = autodiscover

    gateway_provider = clean(row.get("gateway_provider"))
    if gateway_provider:
        entry["gateway_provider"] = gateway_provider

    return entry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build mxatlas data.json from the Germany classification CSV.")
    parser.add_argument("--input", type=Path, default=default_input_path(), help="Path to kommunen_mail_provider_classification.csv")
    parser.add_argument("--output", type=Path, default=repo_root() / "data.json", help="Path to the output data.json")
    return parser.parse_args()


def run(input_path: Path, output_path: Path) -> None:
    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    with input_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        rows = list(reader)

    print(f"[start] rows={len(rows)} input={input_path}")

    municipalities: dict[str, dict[str, Any]] = {}
    counts: Counter[str] = Counter()
    detail_counts: Counter[str] = Counter()
    platform_counts: Counter[str] = Counter()

    for index, row in enumerate(rows, start=1):
        key = gkz8(row.get("kennzahl"))
        if index == 1 or index % 1000 == 0 or index == len(rows):
            print(f"[row {index}/{len(rows)}] {key} {clean(row.get('name'))}")
        entry = build_entry(row)
        municipalities[key] = entry
        counts[entry["provider"]] += 1
        detail_counts[entry["provider_detail"]] += 1
        platform_counts[entry["platform"]] += 1

    payload = {
        "generated": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "country": "DE",
        "total": len(municipalities),
        "counts": dict(sorted(counts.items())),
        "detail_counts": dict(sorted(detail_counts.items())),
        "platform_counts": dict(sorted(platform_counts.items())),
        "municipalities": municipalities,
    }

    output_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"[done] {output_path}")


def main() -> None:
    args = parse_args()
    run(args.input, args.output)


if __name__ == "__main__":
    main()
