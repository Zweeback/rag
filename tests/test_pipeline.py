"""Unit tests for the data ingestion pipeline helpers."""
from __future__ import annotations

import json
from pathlib import Path

from tools.dem.fetch_dem import download_dem
from tools.osm.fetch_osm import OSMDownloader, sanitize_layer_name
from tools.pipeline import DEFAULT_BBOX, parse_bbox, run_pipeline


class FakeResponse:
    def __init__(self, payload: dict | bytes) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:  # pragma: no cover - no-op
        return None

    def json(self) -> dict:
        assert isinstance(self._payload, dict)
        return self._payload

    @property
    def content(self) -> bytes:
        if isinstance(self._payload, bytes):
            return self._payload
        return json.dumps(self._payload).encode("utf-8")


class FakeSession:
    def __init__(self, response_payload: dict | bytes) -> None:
        self._payload = response_payload
        self.calls: list[tuple[str, dict, float]] = []

    def post(self, url: str, *, data: dict, timeout: float):
        self.calls.append((url, data, timeout))
        return FakeResponse(self._payload)

    def get(self, url: str, *, timeout: float):  # pragma: no cover - dem downloader uses this
        self.calls.append((url, {}, timeout))
        return FakeResponse(self._payload)


def test_sanitize_layer_name_removes_special_characters():
    assert sanitize_layer_name('way["highway"]') == "way_highway"
    assert sanitize_layer_name('node["amenity"="cafe"]') == "node_amenity_cafe"
    assert sanitize_layer_name("") == "layer"


def test_osm_downloader_fetch_layers_creates_files(tmp_path):
    payload = {"type": "FeatureCollection", "features": []}
    session = FakeSession(payload)
    downloader = OSMDownloader(DEFAULT_BBOX, tmp_path, session=session, timeout=5)

    layers = ['way["highway"]', 'node["amenity"]']
    produced = downloader.fetch_layers(layers)

    assert len(produced) == len(layers)
    assert all(path.exists() for path in produced)
    for layer, path in zip(layers, produced, strict=True):
        assert path.name == f"{sanitize_layer_name(layer)}.geojson"
        saved = json.loads(path.read_text())
        assert saved["type"] == "FeatureCollection"

    assert all(call[0].startswith("https://") for call in session.calls)
    assert all("data" in call[1] for call in session.calls)


def test_parse_bbox_prefers_environment(monkeypatch):
    monkeypatch.setenv("OSM_BBOX", "1,2,3,4")
    assert parse_bbox(None) == (1.0, 2.0, 3.0, 4.0)


def test_parse_bbox_defaults_when_not_provided(monkeypatch):
    monkeypatch.delenv("OSM_BBOX", raising=False)
    assert parse_bbox(None) == DEFAULT_BBOX


def test_run_pipeline_writes_manifest(tmp_path):
    osm_payload = {"type": "FeatureCollection", "features": []}
    session = FakeSession(osm_payload)

    def fake_dem_downloader(bbox, output: Path, *, session=None, timeout=600):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"DEM")
        return output

    manifest_path = run_pipeline(
        DEFAULT_BBOX,
        dem_source="copernicus",
        output_root=tmp_path,
        layers=['way["highway"]'],
        session=session,
        dem_downloader=fake_dem_downloader,
    )

    manifest = json.loads(manifest_path.read_text())
    assert manifest["bbox"] == list(DEFAULT_BBOX)
    assert manifest["dem_source"] == "copernicus"
    assert manifest["osm_files"]
    assert manifest["dem_file"].endswith("terrain.tif")


def test_download_dem_uses_provided_session(tmp_path):
    dem_bytes = b"DEM"
    session = FakeSession(dem_bytes)
    output = download_dem(DEFAULT_BBOX, tmp_path / "dem.tif", session=session, timeout=1)
    assert output.read_bytes() == dem_bytes

