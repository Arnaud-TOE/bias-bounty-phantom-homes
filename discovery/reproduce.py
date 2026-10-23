"""One command to rebuild every Bias Discovery number and figure.

    python -I discovery/reproduce.py

Requires the challenge data under data/raw/ (README.md) and the two external files listed in
discovery/external/SOURCES.md under discovery/external/raw/ (checked by SHA-256 here).
"""
import hashlib
import runpy
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPECTED = {
    "external/raw/cms_nh/NH_ProviderInfo_Sep2026_3.csv":
        "378d76a43f89c132e6796ea97530a004beabd2b0aa6516833c5734fd99d1e2b0",
    "external/raw/calfire_dins/dins.csv":
        "af01e965145420695504db3385782c6879dee00dc66586feec8a6bfc0938404f",
}
STEPS = ["phantom_homes.py", "phantom_maps.py", "cms_nursing_homes.py", "exposure.py"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    for rel, digest in EXPECTED.items():
        p = ROOT / rel
        if not p.exists():
            print(f"missing {rel}: download it from the URL in discovery/external/SOURCES.md")
            return 1
        if sha256(p) != digest:
            print(f"checksum mismatch for {rel}: the source file has changed since 2026-10-17")
            return 1
    for step in STEPS:
        t0 = time.time()
        print(f"== {step}", flush=True)
        runpy.run_path(str(ROOT / step), run_name="__main__")
        print(f"   done in {time.time() - t0:.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
