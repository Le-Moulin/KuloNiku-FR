"""Analyse les paquets publics d'une release avec l'API VirusTotal v3."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Callable, Mapping, Sequence
import urllib.error
import urllib.request
import uuid


API_BASE = "https://www.virustotal.com/api/v3"
PUBLIC_REPORT_BASE = "https://www.virustotal.com/gui/file"
DIRECT_UPLOAD_LIMIT = 32 * 1024 * 1024
MIN_REQUEST_INTERVAL = 16.0
MAX_RETRIES = 5
REPORT_START = "<!-- virustotal-report:start -->"
REPORT_END = "<!-- virustotal-report:end -->"
CHECKSUM_LINE = re.compile(r"^([0-9a-fA-F]{64}) [ *](.+)$")
EXPECTED_ASSET_NAMES = (
    "KuloNiku-FR-Windows-x64.zip",
    "KuloNiku-FR-macOS-Universal.dmg",
    "KuloNiku-FR-Steam-Deck-x86_64.AppImage",
)


class VirusTotalError(RuntimeError):
    """Erreur exploitable et sans secret provenant du contrôle VirusTotal."""


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    payload: object


@dataclass(frozen=True)
class ScanResult:
    name: str
    sha256: str
    stats: Mapping[str, int]
    analysis_date: int | None
    detections: tuple[tuple[str, str], ...] = ()

    @property
    def malicious(self) -> int:
        return self.stats.get("malicious", 0)

    @property
    def suspicious(self) -> int:
        return self.stats.get("suspicious", 0)

    @property
    def without_detection(self) -> int:
        return self.stats.get("harmless", 0) + self.stats.get("undetected", 0)

    @property
    def unsupported(self) -> int:
        return self.stats.get("type-unsupported", 0)

    @property
    def incomplete(self) -> int:
        return self.stats.get("failure", 0) + self.stats.get("timeout", 0)

    @property
    def needs_review(self) -> bool:
        return self.malicious > 0 or self.suspicious > 0

    @property
    def detection_count(self) -> int:
        return self.malicious + self.suspicious

    @property
    def total_results(self) -> int:
        return sum(self.stats.values())


Transport = Callable[[str, str, Mapping[str, str], bytes | None], HttpResponse]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_checksums(path: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise VirusTotalError(f"Impossible de lire {path.name} : {error}") from error
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        match = CHECKSUM_LINE.fullmatch(line)
        if not match:
            raise VirusTotalError(
                f"Ligne {line_number} invalide dans {path.name}."
            )
        expected, name = match.groups()
        if name in checksums:
            raise VirusTotalError(f"Empreinte dupliquée pour {name}.")
        checksums[name] = expected.lower()
    return checksums


def validate_asset_names(assets: Sequence[Path]) -> None:
    names = [asset.name for asset in assets]
    missing = sorted(set(EXPECTED_ASSET_NAMES) - set(names))
    unexpected = sorted(set(names) - set(EXPECTED_ASSET_NAMES))
    duplicated = sorted(name for name in set(names) if names.count(name) > 1)
    if missing or unexpected or duplicated:
        details = []
        if missing:
            details.append(f"absents : {', '.join(missing)}")
        if unexpected:
            details.append(f"inattendus : {', '.join(unexpected)}")
        if duplicated:
            details.append(f"dupliqués : {', '.join(duplicated)}")
        raise VirusTotalError("Liste des paquets incorrecte (" + "; ".join(details) + ").")


def verify_release_assets(checksum_path: Path, assets: Sequence[Path]) -> None:
    validate_asset_names(assets)
    checksums = parse_checksums(checksum_path)
    for asset in assets:
        expected = checksums.get(asset.name)
        if expected is None:
            raise VirusTotalError(
                f"Aucune empreinte publiée pour {asset.name} dans {checksum_path.name}."
            )
        actual = sha256_file(asset)
        if actual != expected:
            raise VirusTotalError(
                f"SHA-256 incorrect pour {asset.name} : attendu {expected}, obtenu {actual}."
            )


def default_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: bytes | None,
) -> HttpResponse:
    request = urllib.request.Request(
        url,
        data=body,
        headers=dict(headers),
        method=method,
    )
    try:
        response = urllib.request.urlopen(request, timeout=120)
    except urllib.error.HTTPError as error:
        response = error
    except urllib.error.URLError as error:
        raise VirusTotalError(f"VirusTotal est inaccessible : {error.reason}") from error
    try:
        raw = response.read()
        payload: object = json.loads(raw) if raw else {}
    except (UnicodeError, json.JSONDecodeError) as error:
        raise VirusTotalError(
            f"Réponse JSON VirusTotal invalide (HTTP {response.status})."
        ) from error
    finally:
        response.close()
    return HttpResponse(response.status, dict(response.headers.items()), payload)


class VirusTotalClient:
    def __init__(
        self,
        api_key: str,
        *,
        transport: Transport = default_transport,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        min_request_interval: float = MIN_REQUEST_INTERVAL,
        poll_timeout: float = 20 * 60,
    ) -> None:
        if not api_key:
            raise VirusTotalError("Le secret VT_API_KEY est absent.")
        self.api_key = api_key
        self.transport = transport
        self.sleep = sleep
        self.clock = clock
        self.min_request_interval = min_request_interval
        self.poll_timeout = poll_timeout
        self.last_request_at: float | None = None

    def _throttle(self) -> None:
        if self.last_request_at is None:
            return
        remaining = self.min_request_interval - (self.clock() - self.last_request_at)
        if remaining > 0:
            self.sleep(remaining)

    def _request(
        self,
        method: str,
        url: str,
        *,
        body: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        allow_not_found: bool = False,
    ) -> HttpResponse:
        request_headers = {
            "Accept": "application/json",
            "x-apikey": self.api_key,
            **(headers or {}),
        }
        for attempt in range(MAX_RETRIES):
            self._throttle()
            response = self.transport(method, url, request_headers, body)
            self.last_request_at = self.clock()
            if response.status == 429:
                if attempt == MAX_RETRIES - 1:
                    break
                try:
                    retry_after = float(response.headers.get("Retry-After", "60"))
                except ValueError:
                    retry_after = 60.0
                self.sleep(max(retry_after, self.min_request_interval))
                continue
            if response.status == 404 and allow_not_found:
                return response
            if not 200 <= response.status < 300:
                raise VirusTotalError(
                    f"VirusTotal a répondu HTTP {response.status} pendant une requête {method}."
                )
            if not isinstance(response.payload, dict):
                raise VirusTotalError("La réponse VirusTotal n'est pas un objet JSON.")
            return response
        raise VirusTotalError("Quota VirusTotal toujours dépassé après plusieurs tentatives.")

    def _file_report(self, sha256: str) -> ScanResult | None:
        response = self._request(
            "GET",
            f"{API_BASE}/files/{sha256}",
            allow_not_found=True,
        )
        if response.status == 404:
            return None
        try:
            data = response.payload["data"]  # type: ignore[index]
            attributes = data["attributes"]
            raw_stats = attributes["last_analysis_stats"]
        except (KeyError, TypeError) as error:
            raise VirusTotalError("Rapport VirusTotal incomplet ou mal formé.") from error
        if not isinstance(raw_stats, dict) or not all(
            isinstance(key, str) and isinstance(value, int)
            for key, value in raw_stats.items()
        ):
            raise VirusTotalError("Statistiques VirusTotal invalides.")
        analysis_date = attributes.get("last_analysis_date")
        if analysis_date is not None and not isinstance(analysis_date, int):
            raise VirusTotalError("Date d'analyse VirusTotal invalide.")
        raw_results = attributes.get("last_analysis_results", {})
        if not isinstance(raw_results, dict):
            raise VirusTotalError("Détails VirusTotal invalides.")
        detections: list[tuple[str, str]] = []
        for fallback_name, details in raw_results.items():
            if not isinstance(fallback_name, str) or not isinstance(details, dict):
                raise VirusTotalError("Détail de moteur VirusTotal invalide.")
            if details.get("category") not in {"malicious", "suspicious"}:
                continue
            engine = details.get("engine_name", fallback_name)
            result = details.get("result", details["category"])
            if not isinstance(engine, str) or not isinstance(result, str):
                raise VirusTotalError("Verdict de moteur VirusTotal invalide.")
            detections.append((engine, result))
        detections.sort(key=lambda item: item[0].casefold())
        return ScanResult("", sha256, raw_stats, analysis_date, tuple(detections))

    def _multipart(self, path: Path) -> tuple[bytes, str]:
        boundary = f"----KuloNikuFR{uuid.uuid4().hex}"
        safe_name = path.name.replace("\\", "_").replace('"', "_")
        prefix = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{safe_name}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8")
        suffix = f"\r\n--{boundary}--\r\n".encode("ascii")
        try:
            body = prefix + path.read_bytes() + suffix
        except OSError as error:
            raise VirusTotalError(f"Impossible de lire {path.name} : {error}") from error
        return body, f"multipart/form-data; boundary={boundary}"

    def _upload(self, path: Path) -> str:
        upload_url = f"{API_BASE}/files"
        if path.stat().st_size > DIRECT_UPLOAD_LIMIT:
            response = self._request("GET", f"{API_BASE}/files/upload_url")
            try:
                upload_url = response.payload["data"]  # type: ignore[index]
            except (KeyError, TypeError) as error:
                raise VirusTotalError("URL d'envoi VirusTotal absente.") from error
            if not isinstance(upload_url, str) or not upload_url.startswith("https://"):
                raise VirusTotalError("URL d'envoi VirusTotal invalide.")
        body, content_type = self._multipart(path)
        response = self._request(
            "POST",
            upload_url,
            body=body,
            headers={"Content-Type": content_type},
        )
        try:
            analysis_id = response.payload["data"]["id"]  # type: ignore[index]
        except (KeyError, TypeError) as error:
            raise VirusTotalError("Identifiant d'analyse VirusTotal absent.") from error
        if not isinstance(analysis_id, str) or not analysis_id:
            raise VirusTotalError("Identifiant d'analyse VirusTotal invalide.")
        return analysis_id

    def _reanalyze(self, sha256: str) -> str:
        response = self._request("POST", f"{API_BASE}/files/{sha256}/analyse")
        try:
            analysis_id = response.payload["data"]["id"]  # type: ignore[index]
        except (KeyError, TypeError) as error:
            raise VirusTotalError("Identifiant de réanalyse VirusTotal absent.") from error
        if not isinstance(analysis_id, str) or not analysis_id:
            raise VirusTotalError("Identifiant de réanalyse VirusTotal invalide.")
        return analysis_id

    def _wait_for_analysis(self, analysis_id: str) -> None:
        deadline = self.clock() + self.poll_timeout
        while True:
            response = self._request("GET", f"{API_BASE}/analyses/{analysis_id}")
            try:
                status = response.payload["data"]["attributes"]["status"]  # type: ignore[index]
            except (KeyError, TypeError) as error:
                raise VirusTotalError("État d'analyse VirusTotal absent.") from error
            if status == "completed":
                return
            if status not in {"queued", "in-progress"}:
                raise VirusTotalError(f"État d'analyse VirusTotal inattendu : {status!r}.")
            if self.clock() >= deadline:
                raise VirusTotalError("Délai d'analyse VirusTotal dépassé.")
            self.sleep(self.min_request_interval)

    def scan(self, path: Path, *, reanalyze: bool = False) -> ScanResult:
        digest = sha256_file(path)
        existing = self._file_report(digest)
        if existing is None:
            analysis_id = self._upload(path)
            self._wait_for_analysis(analysis_id)
            existing = self._file_report(digest)
        elif reanalyze:
            analysis_id = self._reanalyze(digest)
            self._wait_for_analysis(analysis_id)
            existing = self._file_report(digest)
        if existing is None:
            raise VirusTotalError(
                f"Rapport VirusTotal introuvable après l'analyse de {path.name}."
            )
        return ScanResult(
            path.name,
            digest,
            existing.stats,
            existing.analysis_date,
            existing.detections,
        )


def platform_name(filename: str) -> str:
    if "Windows" in filename:
        return "Windows"
    if "macOS" in filename:
        return "macOS"
    if "Steam-Deck" in filename:
        return "Steam Deck"
    return filename


def render_report(results: Sequence[ScanResult]) -> str:
    if not results:
        raise VirusTotalError("Aucun résultat VirusTotal à publier.")
    lines = [
        REPORT_START,
        "## Analyse antivirus VirusTotal",
        "",
    ]
    summaries = []
    for result in results:
        report_url = f"{PUBLIC_REPORT_BASE}/{result.sha256}/detection"
        status = "⚠️" if result.needs_review else "✅"
        summaries.append(
            f"[{platform_name(result.name)}]({report_url}) {status} "
            f"{result.detection_count}/{result.total_results}"
        )
    lines.append(" · ".join(summaries))
    lines.extend(["", "Résultats indicatifs, pas une garantie de sécurité."])
    lines.extend([REPORT_END, ""])
    return "\n".join(lines)


def replace_report_section(body: str, report: str) -> str:
    if report.count(REPORT_START) != 1 or report.count(REPORT_END) != 1:
        raise VirusTotalError("La section VirusTotal générée est invalide.")
    starts = body.count(REPORT_START)
    ends = body.count(REPORT_END)
    if starts != ends or starts > 1:
        raise VirusTotalError("Les marqueurs VirusTotal existants sont incohérents.")
    if starts == 1:
        pattern = re.compile(
            re.escape(REPORT_START) + r".*?" + re.escape(REPORT_END),
            re.DOTALL,
        )
        return pattern.sub(report.strip(), body, count=1).rstrip() + "\n"
    base = body.rstrip()
    separator = "\n\n" if base else ""
    return f"{base}{separator}{report.strip()}\n"


def write_action_feedback(results: Sequence[ScanResult], report: str) -> None:
    for result in results:
        if result.needs_review:
            details = "; ".join(
                f"{engine}: {verdict}" for engine, verdict in result.detections
            ) or "moteurs non détaillés par l'API"
            print(
                f"::warning title=Détection VirusTotal::{result.name} : "
                f"{result.malicious} malveillant(s), {result.suspicious} suspect(s). "
                f"{details}. Une revue humaine est nécessaire."
            )
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        try:
            with Path(summary_path).open("a", encoding="utf-8") as stream:
                stream.write(report.replace(REPORT_START, "").replace(REPORT_END, ""))
                for result in results:
                    if result.needs_review and result.detections:
                        stream.write(f"\n**Détails {platform_name(result.name)} :** ")
                        stream.write(
                            "; ".join(
                                f"{engine}: `{verdict}`"
                                for engine, verdict in result.detections
                            )
                        )
                        stream.write("\n")
        except OSError as error:
            raise VirusTotalError(
                f"Impossible d'écrire le résumé GitHub Actions : {error}"
            ) from error


def command_verify(arguments: argparse.Namespace) -> None:
    verify_release_assets(arguments.checksums, arguments.assets)
    print("SHA-256 vérifiés pour les trois paquets publics.")


def command_scan(arguments: argparse.Namespace) -> None:
    validate_asset_names(arguments.assets)
    api_key = os.environ.get("VT_API_KEY", "")
    client = VirusTotalClient(api_key)
    results = [client.scan(path, reanalyze=arguments.reanalyze) for path in arguments.assets]
    report = render_report(results)
    arguments.output.write_text(report, encoding="utf-8")
    write_action_feedback(results, report)
    print(f"Rapport VirusTotal écrit dans {arguments.output}.")


def command_merge(arguments: argparse.Namespace) -> None:
    body = arguments.body.read_text(encoding="utf-8")
    report = arguments.report.read_text(encoding="utf-8")
    merged = replace_report_section(body, report)
    arguments.output.write_text(merged, encoding="utf-8")
    print(f"Notes de release mises à jour dans {arguments.output}.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(required=True)

    verify = subparsers.add_parser("verify", help="vérifier SHA256SUMS.txt")
    verify.add_argument("checksums", type=Path)
    verify.add_argument("assets", nargs="+", type=Path)
    verify.set_defaults(handler=command_verify)

    scan = subparsers.add_parser("scan", help="analyser les paquets")
    scan.add_argument("--output", required=True, type=Path)
    scan.add_argument(
        "--reanalyze",
        action="store_true",
        help="forcer une nouvelle analyse des SHA-256 déjà connus",
    )
    scan.add_argument("assets", nargs="+", type=Path)
    scan.set_defaults(handler=command_scan)

    merge = subparsers.add_parser("merge", help="mettre à jour les notes")
    merge.add_argument("--body", required=True, type=Path)
    merge.add_argument("--report", required=True, type=Path)
    merge.add_argument("--output", required=True, type=Path)
    merge.set_defaults(handler=command_merge)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        arguments.handler(arguments)
    except (OSError, VirusTotalError) as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
