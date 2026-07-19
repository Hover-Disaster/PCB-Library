"""
Convert KiCad .pos / CSV pick-and-place files to JLC PCB format.

Input columns  : Ref, Val, Package, PosX, PosY, Rot, Side
Output columns : Designator, Val, Package, Mid X, Mid Y, Rotation, Layer

Side values "Top"/"Bottom" (case-insensitive) are mapped to "T"/"B".
"""

import csv
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Column mapping
# ---------------------------------------------------------------------------
COLUMN_RENAME = {
    "Ref": "Designator",
    "PosX": "Mid X",
    "PosY": "Mid Y",
    "Rot": "Rotation",
    "Side": "Layer",
}

SIDE_MAP = {
    "top": "T",
    "bottom": "B",
}


def remap_row(row: dict) -> dict:
    """Rename keys and normalise the Layer/Side value."""
    new_row = {}
    for key, value in row.items():
        new_key = COLUMN_RENAME.get(key, key)
        # Normalise side → layer
        if new_key == "Layer":
            value = SIDE_MAP.get(value.strip().lower(), value)
        new_row[new_key] = value
    return new_row


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def parse_csv(path: Path) -> list[dict]:
    """Parse a comma-separated .csv or .pos file with a header row."""
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        return [dict(row) for row in reader]


def parse_pos(path: Path) -> list[dict]:
    """
    Parse a KiCad space/tab-delimited .pos file.

    Lines beginning with '#' are comments; the last comment line that starts
    with '# Ref' (or similar) is treated as the header.
    Data lines are split on whitespace into exactly as many fields as headers.
    """
    lines = path.read_text(encoding="utf-8-sig").splitlines()

    header = None
    rows = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("#"):
            # KiCad puts the header as a commented line like:
            #   ## Ref  Val  Package  PosX  PosY  Rot  Side
            candidate = stripped.lstrip("#").strip()
            fields = candidate.split()
            # Accept it as header if the first field looks like "Ref"
            if fields and fields[0] in ("Ref", "Designator"):
                header = fields
            continue

        if header is None:
            continue

        parts = stripped.split()
        # Pad or truncate to match header length
        if len(parts) < len(header):
            parts += [""] * (len(header) - len(parts))
        rows.append(dict(zip(header, parts[: len(header)])))

    if header is None:
        raise ValueError(
            "Could not find a header line in the .pos file. "
            "Expected a comment line starting with '# Ref ...'."
        )

    return rows


def detect_and_parse(path: Path) -> list[dict]:
    """Choose parser based on file extension or content sniffing."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return parse_csv(path)
    if suffix == ".pos":
        # Peek at the file to decide: if there are '#' comment lines → KiCad
        # space-delimited format; otherwise treat as CSV.
        text = path.read_text(encoding="utf-8-sig")
        if any(line.startswith("#") for line in text.splitlines()):
            return parse_pos(path)
        return parse_csv(path)
    # Fallback: try CSV first, then space-delimited
    try:
        return parse_csv(path)
    except Exception:
        return parse_pos(path)


# ---------------------------------------------------------------------------
# Output writer
# ---------------------------------------------------------------------------

OUTPUT_COLUMNS = ["Designator", "Val", "Package", "Mid X", "Mid Y", "Rotation", "Layer"]


def write_csv(rows: list[dict], out_path: Path) -> None:
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=OUTPUT_COLUMNS,
            extrasaction="ignore",  # drop any extra columns silently
        )
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def convert(input_path: Path, output_path: Path | None = None) -> Path:
    rows = detect_and_parse(input_path)
    remapped = [remap_row(row) for row in rows]

    if output_path is None:
        output_path = input_path.with_name(input_path.stem + "_jlc.csv")

    write_csv(remapped, output_path)
    return output_path


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python convert_pos_to_jlc.py <input.[csv|pos]> [output.csv]")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"Error: file not found: {input_path}")
        sys.exit(1)

    output_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else None

    result = convert(input_path, output_path)
    print(f"Converted: {input_path}  →  {result}")


if __name__ == "__main__":
    main()
