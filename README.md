# LX7007 Waypoint Converter

Converts [SeeYou `.cup`](https://www.naviter.com/products/seeyou/) waypoint files to the binary **LX Navigation `.DA4`** format used by the LX7007 flight computer.

## License

This project is licensed under the **GNU General Public License v3.0** — see [LICENSE](LICENSE) for details.  
You are free to use, study, and modify this software. You may **not** sell it or incorporate it into proprietary (closed-source) products.

---

## Requirements

- Python **3.13** or newer
- [Poetry](https://python-poetry.org/) (dependency manager)

---

## Installation

```bash
git clone https://github.com/LJochemczyk/LX7007_waypoint_converter.git
cd LX7007_waypoint_converter
poetry install
```

---

## Usage

### Convert a `.cup` file to `.DA4`

```bash
poetry run python cup_to_da4.py <path/to/file.cup>
```

The output `.DA4` file is placed in `LX/TPS/<filename>.DA4` by default.

**Examples:**

```bash
# Convert a specific file (output: LX/TPS/TP_WGC2026_V1.DA4)
poetry run python cup_to_da4.py source_data/TP_WGC2026_V1.cup

# Specify a custom output path
poetry run python cup_to_da4.py source_data/TP_WGC2026_V1.cup -o LX/TPS/WGC2026.DA4
```

### Options

| Argument | Description |
|---|---|
| `cup_file` | Path to the source `.cup` file (positional, optional — falls back to built-in default) |
| `-o`, `--output` | Custom output path for the `.DA4` file |
| `-h`, `--help` | Show help message |

---

## Uploading to the LX7007

1. Copy the generated `.DA4` file to the `TPS/` directory on the LX7007 SD card.
2. The device will load the new waypoints automatically on next startup.

---

## File Format Details

### Input — SeeYou `.cup`

Standard comma-separated format:

```
name,code,country,lat,lon,elev,style,...
"001EPRU",001,,5053.094N,01912.187E,255.0m,2,...
```

- Latitude: `DDMM.mmmN/S`
- Longitude: `DDDMM.mmmE/W`
- Elevation: metres (`m`) or feet (`ft`)
- Style: `1` = turnpoint, `2` = airfield, etc.

### Output — LX Navigation `.DA4` (binary, 31 bytes/record)

| Offset | Size | Type | Content |
|--------|------|------|---------|
| 0 | 1 | uint8 | Record marker (`0x02` first, `0x01` rest) |
| 1–3 | 3 | ASCII | 3-digit index (e.g. `001`) |
| 4–8 | 5 | ASCII | Waypoint name (max 5 chars, null-padded) |
| 9 | 1 | `0x00` | Name null terminator |
| 10–13 | 4 | float32 LE | Latitude (decimal degrees, N positive) |
| 14–17 | 4 | float32 LE | Longitude (decimal degrees, E positive) |
| 18–19 | 2 | uint16 BE | Altitude (feet) |
| 20–26 | 7 | `0x00` | Reserved |
| 27 | 1 | ASCII | Flag: `G` = glider turnpoint, `A` = airfield |
| 28–30 | 3 | `0x00` | Padding |

---

## Project Structure

```
.
├── cup_to_da4.py        # Main converter script
├── waypoint_reader.py   # DA4 binary reader / debug tool
├── pyproject.toml       # Poetry project config
├── source_data/         # Place your .cup input files here (gitignored)
└── LX/                  # LX7007 output directories (gitignored)
    └── TPS/             # Generated .DA4 files go here
```
