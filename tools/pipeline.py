"""Run the full OSM + DEM data preparation pipeline."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Sequence, Tuple

if __package__ is None or __package__ == "":
    import sys
    sys.path.append(str(Path(__file__).resolve().parent))
    from osm.fetch_osm import OSMDownloader
    from dem.fetch_dem import download_dem
else:
    from .osm.fetch_osm import OSMDownloader
    from .dem.fetch_dem import download_dem

DEFAULT_BBOX = (7.46, 51.49, 7.53, 51.52)


def parse_bbox(values: Tuple[float, float, float, float] | None) -> Tuple[float, float, float, float]:
    if values is not None:
        return values

    env_bbox = os.getenv("OSM_BBOX")
    if env_bbox:
        parts = tuple(float(part) for part in env_bbox.split(","))
        if len(parts) == 4:
            return parts

    return DEFAULT_BBOX


def run_pipeline(
    bbox: Tuple[float, float, float, float],
    *,
    dem_source: str,
    output_root: Path,
    layers: Sequence[str],
    session=None,
    dem_downloader=download_dem,
) -> Path:
    """Execute the data download pipeline and return the manifest path."""

    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    osm_dir = output_root / "osm"
    dem_path = output_root / "dem" / "terrain.tif"

    downloader = OSMDownloader(bbox, osm_dir, session=session)
    osm_files = downloader.fetch_layers(layers)

    dem_file = ""
    if dem_source.lower() == "copernicus":
        dem_file = str(dem_downloader(bbox, dem_path, session=session))
    else:
        logging.warning("DEM source %s not implemented; skipping DEM download", dem_source)

    manifest = {
        "bbox": bbox,
        "layers": list(layers),
        "dem_source": dem_source,
        "osm_files": [str(path) for path in sorted(osm_files)],
        "dem_file": dem_file,
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    logging.info("Pipeline completed. Manifest written to %s", manifest_path)
    return manifest_path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate city tiles from OSM + DEM")
    parser.add_argument("--bbox", nargs=4, type=float, help="West South East North", default=None)
    parser.add_argument("--dem-source", default=os.getenv("DEM_SOURCE", "copernicus"))
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--layers", nargs="*", default=[
        'way["highway"]',
        'way["building"]',
        'node["amenity"]',
    ])
    args = parser.parse_args()

    bbox = parse_bbox(tuple(args.bbox) if args.bbox else None)
    logging.info("Using bounding box %s", bbox)

    run_pipeline(
        bbox,
        dem_source=args.dem_source,
        output_root=args.output,
        layers=args.layers,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
