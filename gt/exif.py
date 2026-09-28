"""EXIF extraction with Pillow: capture time, GPS and a small, JSON-safe subset of tags."""
from __future__ import annotations

from datetime import datetime
from typing import IO

from PIL import ExifTags, Image

EXIF_IFD = 0x8769
GPS_IFD = 0x8825
KEEP = {"Make", "Model", "Software", "DateTime", "DateTimeOriginal", "Orientation", "LensModel"}


def _to_float(x) -> float:
    try:
        return float(x)
    except TypeError:  # older Pillow tuples
        return x[0] / x[1]


def _dms(values, ref) -> float | None:
    try:
        d, m, s = (_to_float(v) for v in values)
    except Exception:
        return None
    dec = d + m / 60 + s / 3600
    return -dec if ref in ("S", "W") else dec


def _parse_dt(s: str | None) -> str | None:
    if not s:
        return None
    try:
        return datetime.strptime(s.strip("\x00 "), "%Y:%m:%d %H:%M:%S").isoformat()
    except ValueError:
        return None


def extract(fp: str | IO[bytes]) -> dict:
    """Return {captured_at, lat, lng, width, height, exif}. Missing values are None."""
    with Image.open(fp) as img:
        width, height = img.size
        raw = img.getexif()
        exif_ifd = raw.get_ifd(EXIF_IFD)
        gps_ifd = raw.get_ifd(GPS_IFD)

    tags: dict[str, str] = {}
    for k, v in list(raw.items()) + list(exif_ifd.items()):
        name = ExifTags.TAGS.get(k)
        if name in KEEP:
            tags[name] = str(v).strip("\x00 ")

    lat = lng = None
    if gps_ifd:
        g = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
        if "GPSLatitude" in g and "GPSLongitude" in g:
            lat = _dms(g["GPSLatitude"], g.get("GPSLatitudeRef", "N"))
            lng = _dms(g["GPSLongitude"], g.get("GPSLongitudeRef", "E"))
        if lat is not None:
            tags["GPS"] = f"{lat:.6f}, {lng:.6f}"

    captured = _parse_dt(tags.get("DateTimeOriginal") or tags.get("DateTime"))
    return {"captured_at": captured, "lat": lat, "lng": lng, "width": width, "height": height, "exif": tags}
