import struct
import re
from pathlib import Path

DA4_FILE = "LX/TPS/13060959.DA4"

# Binary record layout (31 bytes each):
#   1 byte  : marker (0x01 / 0x02)
#   3 bytes : index  (ASCII, e.g. "001")
#   N bytes : name   (null-terminated ASCII, up to 6 chars)
#   4 bytes : latitude  (float32 LE, decimal degrees)
#   4 bytes : longitude (float32 LE, decimal degrees)
#   2 bytes : altitude  (uint16 BE, feet — 0 = unknown)
#   ...
#   1 byte  : flag/symbol (ASCII, e.g. 'G' = glider turnpoint)
#   ...


def deg_to_lx(deg: float, is_lon: bool) -> str:
    """Convert decimal degrees to LX integer format (DDMMSSS / DDDMMSSS)."""
    d = int(abs(deg))
    m = (abs(deg) - d) * 60
    m_int = int(m)
    m_dec = round((m - m_int) * 1000)
    if m_dec >= 1000:
        m_dec -= 1000
        m_int += 1
    val = d * 100000 + m_int * 1000 + m_dec
    if is_lon:
        return f"{val:08d}{'E' if deg >= 0 else 'W'}"
    else:
        return f"{val:07d}{'N' if deg >= 0 else 'S'}"


def parse_records(data: bytes) -> list[dict]:
    records = []
    pos = 0
    while pos < len(data) - 10:
        marker = data[pos]
        if marker not in (0x01, 0x02):
            pos += 1
            continue

        # 3-byte ASCII index
        idx_bytes = data[pos + 1 : pos + 4]
        if not idx_bytes.isdigit():
            pos += 1
            continue

        # null-terminated name
        name_start = pos + 4
        null_pos = data.find(b'\x00', name_start)
        if null_pos == -1 or null_pos - name_start > 6:
            pos += 1
            continue
        name = data[name_start:null_pos].decode('ascii', errors='replace')
        if not name.isalnum():
            pos += 1
            continue

        binary_start = null_pos + 1
        binary = data[binary_start : binary_start + 21]
        if len(binary) < 18:
            pos += 1
            continue

        lat = struct.unpack('<f', binary[0:4])[0]
        lon = struct.unpack('<f', binary[4:8])[0]
        alt_ft = struct.unpack('>H', binary[8:10])[0]   # uint16 big-endian
        alt_m = round(alt_ft * 0.3048) if alt_ft else 0
        flag = chr(binary[17]) if 0x20 <= binary[17] <= 0x7E else '?'

        records.append({
            'index': idx_bytes.decode('ascii'),
            'name':  name,
            'lat':   lat,
            'lon':   lon,
            'alt_ft': alt_ft,
            'alt_m':  alt_m,
            'flag':  flag,
            'raw8_17': binary[8:18].hex(' '),
        })
        pos = binary_start + 21

    return records


def main():
    data = Path(DA4_FILE).read_bytes()
    records = parse_records(data)
    print(f"# {DA4_FILE}  ({len(data)} bytes, {len(records)} records)\n")
    print(f"# {'INDEX':<5} {'NAME':<7} {'LAT':>10} {'LON':>11} {'ALT_FT':>7} {'ALT_M':>6} {'FLAG'}")
    print(f"# {'-'*5} {'-'*6} {'-'*10} {'-'*11} {'-'*7} {'-'*6} {'-'*4}")
    for r in records:
        lat_str = deg_to_lx(r['lat'], is_lon=False)
        lon_str = deg_to_lx(r['lon'], is_lon=True)
        alt = r['alt_m'] if r['alt_m'] else 0
        print(f"{r['index']},{r['name']},{lat_str},{lon_str},{alt},{r['flag']},{r['name']}"
              f"   # raw[8:18]={r['raw8_17']}")


if __name__ == "__main__":
    main()


DA4_FILE = "LX/TPS/13060959.DA4"

# Expected text format (for reference):
# 001,WIEN,4808500N,01625600E,212,A,WIEN
# Latitude:  DDMMSSS  (DD=degrees, MM=minutes, SSS=decimal minutes*1000)
# Longitude: DDDMMSSS


def find_records(data: bytes) -> list[int]:
    """Find offsets of records by scanning for 3-ASCII-digit index pattern."""
    offsets = []
    # Pattern: 3 digits followed by 1-6 alphanumeric chars followed by null byte
    pattern = re.compile(rb'\d{3}[A-Z0-9]{1,6}\x00')
    for m in pattern.finditer(data):
        # The index starts 1 byte before if there's a type marker, or directly
        pos = m.start()
        # Check if there's a non-ASCII byte just before (record marker)
        if pos > 0 and data[pos - 1] < 0x20:
            offsets.append(pos - 1)
        else:
            offsets.append(pos)
    return offsets


def decode_lx_coord(raw_int: int) -> float:
    """
    LX Navigation stores coords as DDDMMMMM (integer).
    DD or DDD = degrees, MMMMM = minutes * 1000 (5 decimal digits).
    E.g. 4808500 = 48 deg 08.500 min = 48 + 8.5/60 = 48.14167 deg
    """
    degrees = raw_int // 100000
    minutes_scaled = raw_int % 100000  # minutes * 1000
    return degrees + minutes_scaled / 1000.0 / 60.0


def try_parse_record(record: bytes, record_size: int) -> None:
    """Try several interpretations of the binary portion of a record."""
    # Detect leading marker byte
    offset = 0
    if record[0] < 0x20:
        marker = record[0]
        offset = 1
    else:
        marker = None

    index = record[offset:offset + 3].decode('ascii', errors='replace')
    offset += 3

    # Name: null-terminated, up to 6 chars
    name_end = record.index(b'\x00', offset)
    name = record[offset:name_end].decode('ascii', errors='replace')
    offset = name_end + 1

    binary = record[offset:]

    print(f"  marker=0x{marker:02X}" if marker is not None else "  marker=none", end="  ")
    print(f"index={index!r}  name={name!r}")
    print(f"  binary ({len(binary)} bytes): {binary.hex(' ')}")

    if len(binary) >= 8:
        lat_f = struct.unpack('<f', binary[0:4])[0]
        lon_f = struct.unpack('<f', binary[4:8])[0]
        lat_i = struct.unpack('<I', binary[0:4])[0]
        lon_i = struct.unpack('<I', binary[4:8])[0]
        print(f"  float32 LE:  lat={lat_f:.5f}  lon={lon_f:.5f}")
        print(f"  uint32  LE:  lat={lat_i}  lon={lon_i}")
        # Try LX integer coord format
        lat_lx = decode_lx_coord(lat_i)
        lon_lx = decode_lx_coord(lon_i)
        print(f"  LX-int coord: lat={lat_lx:.5f}  lon={lon_lx:.5f}")

    if len(binary) >= 12:
        alt_f = struct.unpack('<f', binary[8:12])[0]
        alt_i = struct.unpack('<I', binary[8:12])[0]
        print(f"  alt float32={alt_f:.1f}  alt uint32={alt_i}")

    if len(binary) >= 14:
        alt_i16 = struct.unpack('<H', binary[8:10])[0]
        print(f"  alt uint16={alt_i16}")


def main():
    data = Path(DA4_FILE).read_bytes()
    print(f"File: {DA4_FILE}")
    print(f"Size: {len(data)} bytes")
    print(f"First 32 bytes: {data[:32].hex(' ')}")
    print()

    offsets = find_records(data)
    record_sizes = [offsets[i+1] - offsets[i] for i in range(len(offsets)-1)]
    if record_sizes:
        most_common = max(set(record_sizes), key=record_sizes.count)
        print(f"Detected {len(offsets)} records, most common size: {most_common} bytes")
        print(f"Record sizes seen: {sorted(set(record_sizes))}")
        print()

    print("=== First 10 records ===\n")
    for i, off in enumerate(offsets[:10]):
        next_off = offsets[i + 1] if i + 1 < len(offsets) else off + most_common
        record = data[off:next_off]
        print(f"[{i:03d}] offset=0x{off:04X}  record_size={len(record)}")
        try:
            try_parse_record(record, len(record))
        except Exception as e:
            print(f"  ERROR: {e}  raw: {record.hex()}")
        print()


if __name__ == "__main__":
    main()
