"""Download OpenStreetMap data for a given bounding box."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Iterable, Sequence, Tuple

try:  # pragma: no cover - fallback for test environments without requests
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def sanitize_layer_name(layer: str) -> str:
    """Return a filesystem friendly representation of a layer expression."""

    sanitized = re.sub(r"[^0-9A-Za-z]+", "_", layer).strip("_")
    return sanitized or "layer"


class OSMDownloader:
    """Simple Overpass API client that exports data to GeoJSON."""

    def __init__(
        self,
        bbox: Tuple[float, float, float, float],
        output_dir: Path,
        *,
        session: Any | None = None,
        timeout: float = 300.0,
    ) -> None:
        self.bbox = bbox
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._session = session
        self.timeout = timeout
        if self._session is None and requests is None:
            raise RuntimeError(
                "The requests library is required unless a custom session is supplied."
            )

    def fetch_layers(self, layers: Iterable[str]) -> Sequence[Path]:
        """Download each requested layer and return the produced file paths."""

        produced: list[Path] = []
        client = self._session or requests
        if client is None:  # pragma: no cover - guard for type checkers
            raise RuntimeError("No HTTP client available for OSM downloads")
        for layer in layers:
            logging.info("Fetching layer %s", layer)
            query = self._build_query(layer)
            response = client.post(OVERPASS_URL, data={"data": query}, timeout=self.timeout)
            response.raise_for_status()
            geojson = response.json()
            sanitized = sanitize_layer_name(layer)
            target = self.output_dir / f"{sanitized}.geojson"
            target.write_text(json.dumps(geojson, indent=2))
            produced.append(target)
            logging.info("Layer %s saved to %s", layer, target)
        return produced

    def _build_query(self, layer: str) -> str:
        west, south, east, north = self.bbox
        return f"[out:json];({layer}({south},{west},{north},{east}););out body;>;out skel qt;"


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Download OSM GeoJSON layers")
    parser.add_argument("bbox", nargs=4, type=float, help="Bounding box as west south east north")
    parser.add_argument(
        "--layers",
        nargs="*",
        default=[
            'way["highway"]',
            'way["building"]',
            'node["amenity"]',
        ],
    )
    parser.add_argument("--output", type=Path, default=Path("output/osm"))
    args = parser.parse_args()

    downloader = OSMDownloader(tuple(args.bbox), args.output)
    downloader.fetch_layers(args.layers)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
