"""Download DEM tiles from the Copernicus EU-DEM service."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Tuple

try:  # pragma: no cover - fallback for environments without requests
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]

COPERNICUS_TEMPLATE = (
    "https://land.copernicus.eu/imagery-in-situ/eu-dem/v1.1?bbox={west},{south},{east},{north}&format=GeoTIFF"
)


def download_dem(
    bbox: Tuple[float, float, float, float],
    output: Path,
    *,
    session: Any | None = None,
    timeout: float = 600.0,
) -> Path:
    west, south, east, north = bbox
    url = COPERNICUS_TEMPLATE.format(west=west, south=south, east=east, north=north)
    logging.info("Downloading DEM from %s", url)
    client = session or requests
    if client is None:  # pragma: no cover - guard for type checkers
        raise RuntimeError("No HTTP client available for DEM download")
    response = client.get(url, timeout=timeout)
    response.raise_for_status()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(response.content)
    logging.info("DEM saved to %s", output)
    return output


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Download DEM tiles")
    parser.add_argument("bbox", nargs=4, type=float, help="Bounding box as west south east north")
    parser.add_argument("--output", type=Path, default=Path("output/dem/eu_dem.tif"))
    args = parser.parse_args()

    download_dem(tuple(args.bbox), args.output)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
