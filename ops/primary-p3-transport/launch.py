"""Preserve retained namespaces and presentation; select only transport entry."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from hashlib import sha256
from pathlib import Path

PRESENTATION = Path("/opt/dehps/releases/primary-p3-style-850")
PRESENTATION_LAUNCHER_SHA = (
    "8be9e90531836fb8dd78d06e0a2047299e052495b88bc69f17b4b9b7bff70ea6"
)


def command(bundle: Path, mode: str, deliver: bool) -> list[str]:
    path = PRESENTATION / "launch.py"
    if sha256(path.read_bytes()).hexdigest() != PRESENTATION_LAUNCHER_SHA:
        raise ValueError("retained presentation launcher differs")
    spec = importlib.util.spec_from_file_location("retained_presentation", path)
    presentation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(presentation)
    # Reuse its exact root-owned namespace/dependency and file-hash checks.
    packet_raw = (bundle / "package.json").read_bytes()
    packet = json.loads(packet_raw)
    spec2 = importlib.util.spec_from_file_location(
        "retained_namespace", presentation.RETAINED / "legacy_p3_namespace.py"
    )
    legacy = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(legacy)
    if (
        sha256(
            (presentation.RETAINED / "legacy_p3_namespace.py").read_bytes()
        ).hexdigest()
        != presentation.LAUNCHER_SHA
    ):
        raise ValueError("retained namespace launcher differs")
    legacy.canonical(bundle)
    legacy.protected_package(bundle)
    for name, expected in packet["files"].items():
        item = bundle / name
        if (
            not item.resolve().is_relative_to(bundle)
            or sha256(item.read_bytes()).hexdigest() != expected
        ):
            raise ValueError("primary transport package differs: " + name)
    release = json.loads((bundle / "release.json").read_bytes())
    template = json.loads((bundle / "release-template.json").read_bytes())
    if (
        release.pop("package_sha256", None) != sha256(packet_raw).hexdigest()
        or release["operator"]["key"] != template["operator"]["key"]
    ):
        raise ValueError("primary transport package admission differs")
    release["operator"] = template["operator"]
    if release != template:
        raise ValueError("primary transport release template differs")
    argv = presentation.command(PRESENTATION, mode, deliver)
    index = argv.index(legacy.BOOTSTRAP)
    argv[index + 2] = str(
        bundle / "source/apps/worker-python/scripts/run_primary_p3_transport.py"
    )
    argv[index + 4 : index + 4] = ["--transport-release", str(bundle / "release.json")]
    return argv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument(
        "--mode", required=True, choices=("pre", "post", "acceptance", "replay")
    )
    parser.add_argument("--deliver", action="store_true")
    args = parser.parse_args()
    if args.deliver and args.mode not in ("pre", "post"):
        raise ValueError("primary transport acceptance/replay cannot send")
    argv = command(args.bundle, args.mode, args.deliver)
    os.execv(argv[0], argv)


if __name__ == "__main__":
    main()
