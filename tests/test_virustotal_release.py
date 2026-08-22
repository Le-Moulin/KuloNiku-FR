from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys

import pytest


SCRIPT = Path(__file__).parents[1] / "packaging" / "virustotal_release.py"
SPEC = importlib.util.spec_from_file_location("kuloniku_virustotal_release", SCRIPT)
assert SPEC and SPEC.loader
virustotal = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = virustotal
SPEC.loader.exec_module(virustotal)


def response(status: int, payload: object, **headers: str):
    return virustotal.HttpResponse(status, headers, payload)


def file_report(*, malicious: int = 0, suspicious: int = 0):
    analysis_results = {}
    if malicious:
        analysis_results["ExampleAV"] = {
            "category": "malicious",
            "engine_name": "Example AV",
            "result": "Generic.Malware",
        }
    if suspicious:
        analysis_results["CautiousAV"] = {
            "category": "suspicious",
            "engine_name": "Cautious AV",
            "result": "Heuristic.Suspicious",
        }
    return {
        "data": {
            "attributes": {
                "last_analysis_date": 1_700_000_000,
                "last_analysis_results": analysis_results,
                "last_analysis_stats": {
                    "harmless": 3,
                    "undetected": 67,
                    "malicious": malicious,
                    "suspicious": suspicious,
                    "type-unsupported": 2,
                    "failure": 1,
                    "timeout": 1,
                },
            }
        }
    }


class QueuedTransport:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, headers, body))
        assert self.replies, f"appel HTTP inattendu : {method} {url}"
        return self.replies.pop(0)


def make_client(transport, **kwargs):
    return virustotal.VirusTotalClient(
        "secret-de-test",
        transport=transport,
        min_request_interval=0,
        sleep=lambda _seconds: None,
        **kwargs,
    )


def test_release_assets_must_match_the_published_checksums(tmp_path: Path):
    first = tmp_path / "KuloNiku-FR-Windows-x64.zip"
    second = tmp_path / "KuloNiku-FR-macOS-Universal.dmg"
    third = tmp_path / "KuloNiku-FR-Steam-Deck-x86_64.AppImage"
    first.write_bytes(b"windows")
    second.write_bytes(b"macos")
    third.write_bytes(b"steam deck")
    checksums = tmp_path / "SHA256SUMS.txt"
    checksums.write_text(
        f"{hashlib.sha256(first.read_bytes()).hexdigest()}  {first.name}\n"
        f"{hashlib.sha256(second.read_bytes()).hexdigest()}  {second.name}\n"
        f"{hashlib.sha256(third.read_bytes()).hexdigest()}  {third.name}\n",
        encoding="utf-8",
    )

    virustotal.verify_release_assets(checksums, [first, second, third])
    second.write_bytes("paquet modifié".encode())

    with pytest.raises(virustotal.VirusTotalError, match="SHA-256 incorrect"):
        virustotal.verify_release_assets(checksums, [first, second, third])


def test_release_asset_requires_a_published_checksum(tmp_path: Path):
    assets = [tmp_path / name for name in virustotal.EXPECTED_ASSET_NAMES]
    for asset in assets:
        asset.write_bytes(asset.name.encode())
    checksums = tmp_path / "SHA256SUMS.txt"
    checksums.write_text(
        "\n".join(
            f"{hashlib.sha256(asset.read_bytes()).hexdigest()}  {asset.name}"
            for asset in assets[:2]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(virustotal.VirusTotalError, match="Aucune empreinte publiée"):
        virustotal.verify_release_assets(checksums, assets)


def test_known_hash_reuses_the_existing_report_without_upload(tmp_path: Path):
    asset = tmp_path / "Windows.zip"
    asset.write_bytes(b"already known")
    transport = QueuedTransport([response(200, file_report())])

    result = make_client(transport).scan(asset)

    assert result.name == asset.name
    assert result.without_detection == 70
    assert [call[0] for call in transport.calls] == ["GET"]


def test_known_hash_can_request_a_fresh_analysis(tmp_path: Path):
    asset = tmp_path / "Windows.zip"
    asset.write_bytes(b"already known")
    transport = QueuedTransport(
        [
            response(200, file_report(malicious=1)),
            response(200, {"data": {"id": "fresh-analysis"}}),
            response(200, {"data": {"attributes": {"status": "completed"}}}),
            response(200, file_report()),
        ]
    )

    result = make_client(transport).scan(asset, reanalyze=True)

    assert result.malicious == 0
    assert transport.calls[1][0:2] == (
        "POST",
        f"{virustotal.API_BASE}/files/{result.sha256}/analyse",
    )


def test_new_small_file_is_uploaded_and_polled_until_completed(tmp_path: Path):
    asset = tmp_path / "Windows.zip"
    asset.write_bytes(b"new file")
    transport = QueuedTransport(
        [
            response(404, {}),
            response(200, {"data": {"id": "analysis-id"}}),
            response(200, {"data": {"attributes": {"status": "queued"}}}),
            response(200, {"data": {"attributes": {"status": "completed"}}}),
            response(200, file_report()),
        ]
    )

    result = make_client(transport).scan(asset)

    assert result.sha256 == hashlib.sha256(asset.read_bytes()).hexdigest()
    assert transport.calls[1][0:2] == ("POST", f"{virustotal.API_BASE}/files")
    assert b'filename="Windows.zip"' in transport.calls[1][3]
    assert not transport.replies


def test_large_file_requests_a_single_use_upload_url(monkeypatch, tmp_path: Path):
    asset = tmp_path / "Steam-Deck.AppImage"
    asset.write_bytes(b"large for this test")
    monkeypatch.setattr(virustotal, "DIRECT_UPLOAD_LIMIT", 1)
    upload_url = "https://uploads.virustotal.example/single-use"
    transport = QueuedTransport(
        [
            response(404, {}),
            response(200, {"data": upload_url}),
            response(200, {"data": {"id": "analysis-id"}}),
            response(200, {"data": {"attributes": {"status": "completed"}}}),
            response(200, file_report()),
        ]
    )

    make_client(transport).scan(asset)

    assert transport.calls[1][0:2] == (
        "GET",
        f"{virustotal.API_BASE}/files/upload_url",
    )
    assert transport.calls[2][0:2] == ("POST", upload_url)


def test_rate_limit_retries_after_the_requested_delay(tmp_path: Path):
    asset = tmp_path / "macOS.dmg"
    asset.write_bytes(b"known")
    transport = QueuedTransport(
        [response(429, {}, **{"Retry-After": "2"}), response(200, file_report())]
    )
    sleeps = []
    client = virustotal.VirusTotalClient(
        "secret-de-test",
        transport=transport,
        min_request_interval=0,
        sleep=sleeps.append,
    )

    client.scan(asset)

    assert sleeps == [2.0]
    assert len(transport.calls) == 2


def test_queued_analysis_stops_after_the_timeout(tmp_path: Path):
    asset = tmp_path / "Windows.zip"
    asset.write_bytes(b"new file")
    transport = QueuedTransport(
        [
            response(404, {}),
            response(200, {"data": {"id": "analysis-id"}}),
            response(200, {"data": {"attributes": {"status": "queued"}}}),
        ]
    )
    client = make_client(transport, poll_timeout=0)

    with pytest.raises(virustotal.VirusTotalError, match="Délai d'analyse"):
        client.scan(asset)


def test_malformed_report_is_rejected(tmp_path: Path):
    asset = tmp_path / "Windows.zip"
    asset.write_bytes(b"known")
    transport = QueuedTransport([response(200, {"data": {"attributes": {}}})])

    with pytest.raises(virustotal.VirusTotalError, match="incomplet"):
        make_client(transport).scan(asset)


def test_report_is_factual_warns_and_is_replaced_idempotently():
    clean = virustotal.ScanResult(
        "macOS.dmg",
        "a" * 64,
        file_report()["data"]["attributes"]["last_analysis_stats"],
        1_700_000_000,
    )
    flagged = virustotal.ScanResult(
        "Windows.zip",
        "b" * 64,
        file_report(malicious=1)["data"]["attributes"]["last_analysis_stats"],
        1_700_000_000,
        (("Example AV", "Generic.Malware"),),
    )
    report = virustotal.render_report([clean, flagged])

    assert "[Windows]" in report
    assert "⚠️ 1/75" in report
    assert "pas une garantie de sécurité" in report
    assert "SHA-256" not in report
    assert "| Paquet |" not in report
    first_body = virustotal.replace_report_section("Notes initiales\n", report)
    replacement = virustotal.render_report([clean])
    second_body = virustotal.replace_report_section(first_body, replacement)

    assert second_body.startswith("Notes initiales\n")
    assert second_body.count(virustotal.REPORT_START) == 1
    assert "Windows.zip" not in second_body
    assert virustotal.replace_report_section(second_body, replacement) == second_body


def test_flagged_engines_are_kept_for_maintainer_feedback(tmp_path: Path):
    asset = tmp_path / "Windows.zip"
    asset.write_bytes(b"known")
    transport = QueuedTransport([response(200, file_report(malicious=1, suspicious=1))])

    result = make_client(transport).scan(asset)

    assert result.detections == (
        ("Cautious AV", "Heuristic.Suspicious"),
        ("Example AV", "Generic.Malware"),
    )
