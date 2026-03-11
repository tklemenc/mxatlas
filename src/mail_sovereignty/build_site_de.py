from __future__ import annotations

from pathlib import Path

from mail_sovereignty.build_data_de import run


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    input_path = repo_root.parent / "kommunen_mail_provider_classification.csv"
    output_path = repo_root / "data.json"
    run(input_path, output_path)
    print("[note] municipalities.topo.json is treated as a checked-in static asset and is not rebuilt by this command.")
