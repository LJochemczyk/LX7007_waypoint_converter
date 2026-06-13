"""Converts SeeYou .cup waypoint file to LX Navigation binary .DA4 format.

DA4 record layout (31 bytes, fixed):
  [0]     marker   : 0x01 (normal), 0x02 (first record)
  [1:4]   index    : 3-digit ASCII, e.g. b"001"
  [4:9]   name     : 5-char ASCII, null-padded to exactly 5 bytes
  [9]     0x00     : null terminator for name
  [10:14] lat      : float32 little-endian, decimal degrees (north = positive)
  [14:18] lon      : float32 little-endian, decimal degrees (east  = positive)
  [18:20] alt      : uint16 big-endian, altitude in feet
  [20:27] reserved : 0x00
  [27]    flag     : ASCII symbol: 'G' = glider turnpoint, 'A' = airfield
  [28:31] 0x00     : padding
"""

import csv
import struct
from pathlib import Path

CUP_FILE = Path("source_data/TP_WGC2026_V1.cup")
DA4_OUT  = Path("LX/TPS/WGC2026.DA4")

RECORD_SIZE = 31

# SeeYou CUP style number → LX DA4 flag byte
STYLE_FLAG: dict[int, int] = {
    1:  ord('G'),  # turnpoint
    2:  ord('A'),  # airfield (grass runway)
    3:  ord('G'),  # outlanding field
    4:  ord('A'),  # glider site / aerodrome
    5:  ord('A'),  # military airfield
    6:  ord('G'),  # mountain pass
    7:  ord('G'),  # mountain top
    8:  ord('G'),  # transmitter mast
    9:  ord('G'),  # VOR
    10: ord('G'),  # NDB
    11: ord('G'),  # waypoint
    12: ord('G'),  # thermal hotspot
}


def parse_cup_lat(lat_str: str) -> float:
    """DDMM.mmmN/S  →  decimal degrees, north positive."""
    hem = lat_str[-1]
    dd  = int(lat_str[:2])
    mm  = float(lat_str[2:-1])
    deg = dd + mm / 60.0
    return deg if hem == 'N' else -deg


def parse_cup_lon(lon_str: str) -> float:
    """DDDMM.mmmE/W  →  decimal degrees, east positive."""
    hem = lon_str[-1]
    ddd = int(lon_str[:3])
    mm  = float(lon_str[3:-1])
    deg = ddd + mm / 60.0
    return deg if hem == 'E' else -deg


def parse_cup_elev(elev_str: str) -> float:
    """'255.0m' or '835.0ft'  →  metres."""
    s = elev_str.strip()
    if s.endswith('ft'):
        return float(s[:-2]) * 0.3048
    if s.endswith('m'):
        return float(s[:-1])
    return 0.0


def extract_index_and_name(name_field: str) -> tuple[str, str]:
    """'001EPRU' → ('001', 'EPRU').  Falls back gracefully for non-standard names."""
    s = name_field.strip()
    if len(s) >= 3 and s[:3].isdigit():
        return s[:3], s[3:]
    return '000', s


def make_record(index: str, name: str, lat: float, lon: float,
                alt_m: float, style: int, first: bool = False) -> bytes:
    rec = bytearray(RECORD_SIZE)

    rec[0] = 0x02 if first else 0x01

    rec[1:4] = index.zfill(3)[:3].encode('ascii')

    # Name: exactly 5 bytes, null-padded, uppercase
    name5 = name.upper()[:5].encode('ascii', errors='replace').ljust(5, b'\x00')
    rec[4:9] = name5
    rec[9]   = 0x00  # null terminator

    rec[10:14] = struct.pack('<f', lat)
    rec[14:18] = struct.pack('<f', lon)

    alt_ft = max(0, round(alt_m / 0.3048))
    rec[18:20] = struct.pack('>H', min(alt_ft, 0xFFFF))

    # bytes 20–26: reserved zeros
    rec[27] = STYLE_FLAG.get(style, ord('G'))
    # bytes 28–30: padding zeros

    return bytes(rec)


def read_cup(path: Path) -> list[dict]:
    waypoints: list[dict] = []
    with path.open(encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name_raw = row.get('name', '').strip()
            # skip blank lines and the "-----Related Tasks-----" separator
            if not name_raw or name_raw.startswith('-'):
                continue
            waypoints.append(row)
    return waypoints


def convert(cup_path: Path, da4_path: Path) -> None:
    waypoints = read_cup(cup_path)
    print(f"Read {len(waypoints)} waypoints from {cup_path}")

    da4_path.parent.mkdir(parents=True, exist_ok=True)
    with da4_path.open('wb') as f:
        for i, row in enumerate(waypoints):
            name_raw = row.get('name', '').strip()
            index, wpname = extract_index_and_name(name_raw)

            lat_str  = row.get('lat',  '').strip()
            lon_str  = row.get('lon',  '').strip()
            elev_str = row.get('elev', '0m').strip() or '0m'
            style    = int(row.get('style', '1').strip() or '1')

            lat = parse_cup_lat(lat_str)
            lon = parse_cup_lon(lon_str)
            alt = parse_cup_elev(elev_str)

            record = make_record(index, wpname, lat, lon, alt, style, first=(i == 0))
            f.write(record)

    count = da4_path.stat().st_size // RECORD_SIZE
    print(f"Written {count} records ({da4_path.stat().st_size} bytes) → {da4_path}")
    print()
    print("Preview (first 10 records):")
    preview(da4_path)


def preview(da4_path: Path) -> None:
    """Read back the output and print it in human-readable form."""
    import sys
    sys.path.insert(0, str(da4_path.parent.parent.parent))
    data = da4_path.read_bytes()
    pos  = 0
    shown = 0
    while pos + RECORD_SIZE <= len(data) and shown < 10:
        rec   = data[pos:pos + RECORD_SIZE]
        idx   = rec[1:4].decode('ascii')
        name  = rec[4:9].rstrip(b'\x00').decode('ascii', errors='replace')
        lat,  = struct.unpack('<f', rec[10:14])
        lon,  = struct.unpack('<f', rec[14:18])
        alt_ft, = struct.unpack('>H', rec[18:20])
        alt_m = round(alt_ft * 0.3048)
        flag  = chr(rec[27]) if 0x20 <= rec[27] <= 0x7E else '?'
        print(f"  {idx},{name},{lat:.5f}N,{lon:.5f}E,{alt_m}m,{flag}")
        pos  += RECORD_SIZE
        shown += 1


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert SeeYou .cup waypoint file to LX Navigation .DA4 binary format."
    )
    parser.add_argument(
        'cup_file',
        nargs='?',
        default=str(CUP_FILE),
        help=f"Path to source .cup file (default: {CUP_FILE})",
    )
    parser.add_argument(
        '-o', '--output',
        default=None,
        help="Output .DA4 file path. Defaults to LX/TPS/<stem>.DA4",
    )
    args = parser.parse_args()

    src = Path(args.cup_file)
    if not src.exists():
        parser.error(f"File not found: {src}")

    dst = Path(args.output) if args.output else Path("LX/TPS") / (src.stem + ".DA4")

    convert(src, dst)
