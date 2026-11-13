"""Refresh the test logs and build the report .docx with pandoc.

Run from the repo root or report/ with the backend venv active:
    python report/build_report.py
    python report/build_report.py --skip-tests   only rebuild the .docx
"""

from __future__ import annotations

import argparse
import io
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent / "backend"
LOGS = HERE / "logs"
SOURCE = HERE / "CarSense_Milestone3_Report.md"
OUTPUT = HERE / "CarSense_Milestone3_Report.docx"
REFERENCE = HERE / "reference.docx"


def tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        sys.exit(f"{name} not found on PATH")
    return path


def refresh_logs() -> None:
    LOGS.mkdir(exist_ok=True)
    runs = {
        "test_results.txt": ["-m", "pytest", "-v", "--no-header", "-p", "no:cacheprovider"],
        "engine_tests.txt": ["-m", "pytest", "tests/test_engine.py", "-v", "--no-header",
                             "-p", "no:cacheprovider"],
    }
    for name, args in runs.items():
        result = subprocess.run([sys.executable, *args], cwd=BACKEND, capture_output=True, text=True)
        (LOGS / name).write_text(result.stdout, encoding="utf-8")
        print(f"{name}: {result.stdout.strip().splitlines()[-1]}")
    subprocess.run([sys.executable, "tests/bench_engine.py"], cwd=BACKEND, check=True,
                   stdout=subprocess.DEVNULL)
    print("engine_timing.txt updated")


def make_reference() -> None:
    """Pandoc's default styles with Calibri 11 pt body text and smaller code."""
    data = subprocess.run([tool("pandoc"), "--print-default-data-file", "reference.docx"],
                          capture_output=True, check=True).stdout
    edits = {
        "word/theme/theme1.xml": [(r'typeface="Aptos Display"', 'typeface="Calibri Light"'),
                                  (r'typeface="Aptos"', 'typeface="Calibri"')],
        "word/styles.xml": [(r'(<w:rPrDefault>\s*<w:rPr>.*?<w:sz w:val=")24(" />\s*<w:szCs w:val=")24',
                             r"\g<1>22\g<2>22"),
                            (r'(w:styleId="VerbatimChar">.*?<w:sz w:val=")22', r"\g<1>17")],
    }
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            content = src.read(item.filename)
            for pattern, new in edits.get(item.filename, []):
                text, count = re.subn(pattern, new, content.decode("utf-8"), count=1, flags=re.S)
                if not count:
                    sys.exit(f"reference.docx: could not find {pattern!r} in {item.filename}")
                content = text.encode("utf-8")
            dst.writestr(item, content)
    REFERENCE.write_bytes(out.getvalue())
    print("reference.docx created")


def build_docx() -> None:
    if not REFERENCE.exists():
        make_reference()
    subprocess.run([tool("pandoc"), SOURCE.name, "-o", OUTPUT.name, "--number-sections",
                    f"--reference-doc={REFERENCE.name}", "--resource-path=.:figures:screenshots"],
                   cwd=HERE, check=True)
    print(f"built {OUTPUT.name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()
    if not args.skip_tests:
        refresh_logs()
    build_docx()


if __name__ == "__main__":
    main()
