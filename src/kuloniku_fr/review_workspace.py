from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import re

from .batching import macro_group, semantic_group
from .i2_asset import LanguageSource
from .localization import source_limit
from .translation import lint_translation, source_character_limit


LANGUAGE_LABELS = {
    "en": "Anglais",
    "id": "Indonésien",
    "es": "Espagnol",
    "th": "Thaï",
    "zh-CN": "Chinois simplifié",
    "zh-TW": "Chinois traditionnel",
    "de": "Allemand",
    "pt": "Portugais",
    "fr": "Français",
}


def read_translation_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {"key", "fr"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"{path} doit contenir les colonnes key et fr.")
        return {
            row["key"]: {
                "fr": row.get("fr", ""),
                "status": row.get("status", ""),
                "notes": row.get("notes", ""),
            }
            for row in reader
            if row.get("key")
        }


def extract_markdown_section(markdown: str, heading: str) -> str:
    pattern = re.compile(
        rf"^## {re.escape(heading)}\s*$\n(?P<body>.*?)(?=^## |\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(markdown)
    return match.group("body").strip() if match else ""


def extract_character_notes(markdown: str) -> dict[str, str]:
    section = extract_markdown_section(markdown, "Voix récurrentes")
    notes: dict[str, str] = {}
    for line in section.splitlines():
        match = re.match(r"^- \*\*(.+?)\*\*\s*:\s*(.+)$", line.strip())
        if match:
            notes[match.group(1)] = match.group(2).strip()
    return notes


def key_category(key: str) -> str:
    if "/" in key:
        return key.split("/", 1)[0]
    if "_" in key:
        return key.split("_", 1)[0]
    return "Autre"


def source_fingerprint(source: LanguageSource) -> str:
    digest = hashlib.sha256()
    codes = [language.code for language in source.languages]
    digest.update("\0".join(codes).encode("utf-8"))
    digest.update(b"\0")
    for term in source.terms:
        digest.update(term.key.encode("utf-8"))
        digest.update(b"\0")
        for value in term.translations:
            digest.update(value.encode("utf-8"))
            digest.update(b"\0")
    return digest.hexdigest()


def merge_review_test_proposals(
    source: LanguageSource,
    base_translations: dict[str, str],
    proposals: list[dict[str, str]],
) -> tuple[dict[str, str], list[str], int]:
    """Merge a review export only when it matches this exact game text set."""
    ensure_unpatched_source(source)
    expected_fingerprint = source_fingerprint(source)
    by_key = {term.key: term for term in source.terms}
    merged = dict(base_translations)
    length_warnings: list[str] = []
    applied = 0
    seen: set[str] = set()
    for row in proposals:
        key = (row.get("key") or "").strip()
        french = row.get("fr") or ""
        fingerprint = (row.get("source_fingerprint") or "").strip()
        if not key or not french:
            continue
        if key in seen:
            raise ValueError(f"Clé présente plusieurs fois dans les propositions : {key}")
        seen.add(key)
        if fingerprint != expected_fingerprint:
            raise ValueError(
                "Ce fichier de propositions correspond à une autre version des textes. "
                "Recréez-le depuis l’espace de relecture actuel."
            )
        term = by_key.get(key)
        if term is None:
            raise ValueError(f"Clé de proposition absente du jeu : {key}")
        warnings = lint_translation(term, french, source=source)
        token_warning = next((warning for warning in warnings if warning.kind == "tokens"), None)
        if token_warning:
            raise ValueError(f"{key} : {token_warning.message}")
        if any(warning.kind == "length" for warning in warnings):
            length_warnings.append(key)
        merged[key] = french
        applied += 1
    if applied == 0:
        raise ValueError("Ce fichier ne contient aucune correction française à tester.")
    return merged, length_warnings, applied


def ensure_unpatched_source(source: LanguageSource) -> None:
    codes = [language.code for language in source.languages]
    selection = next(
        (term for term in source.terms if term.key == "SETTINGS_LANGUAGESELECTION"),
        None,
    )
    if not selection:
        return
    for code in ("de",):
        if code in codes:
            index = codes.index(code)
            if index < len(selection.translations) and selection.translations[index] == "Français":
                raise ValueError(
                    "Le fichier du jeu contient déjà KuloNiku FR. Restaurez d’abord "
                    "le fichier original, puis recréez l’espace de relecture."
                )


def infer_characters(key: str, character_notes: dict[str, str]) -> list[str]:
    normalized_key = re.sub(r"[^A-Z0-9]+", "_", key.upper())
    compact_key = normalized_key.replace("_", "")
    found = []
    for name in character_notes:
        normalized_name = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")
        compact_name = normalized_name.replace("_", "")
        if normalized_name and (
            re.search(rf"(?:^|_){re.escape(normalized_name)}(?:_|$)", normalized_key)
            or (len(compact_name) >= 5 and compact_name in compact_key)
        ):
            found.append(name)
    return found


def build_review_payload(
    source: LanguageSource,
    translations: dict[str, dict[str, str]],
    review_notes: dict[str, dict[str, str]],
    *,
    terminology_markdown: str,
    agent_brief_markdown: str,
    edition: str,
    asset_sha256: str,
) -> dict:
    ensure_unpatched_source(source)
    character_notes = extract_character_notes(agent_brief_markdown)
    languages = [
        {
            "code": language.code,
            "name": LANGUAGE_LABELS.get(language.code, language.name or language.code),
        }
        for language in source.languages if language.code
    ]
    rows = []
    for index, term in enumerate(source.terms):
        current = translations.get(term.key, {})
        decision = review_notes.get(term.key, {})
        notes = []
        for note in (current.get("notes", ""), decision.get("notes", "")):
            if note and note not in notes:
                notes.append(note)
        values = {
            language.code: term.translations[position]
            if position < len(term.translations)
            else ""
            for position, language in enumerate(source.languages) if language.code
        }
        if not current.get("fr") and not any(values.values()):
            continue
        group = semantic_group(term.key)
        rows.append(
            {
                "index": index,
                "key": term.key,
                "category": key_category(term.key),
                "group": group,
                "macro": macro_group(group),
                "max_source_chars": source_limit(source, term),
                "fr": current.get("fr", ""),
                "missing_fr": not current.get("fr", "").strip(),
                "translation_status": current.get("status", ""),
                "translation_notes": "\n".join(notes),
                "languages": values,
                "characters": infer_characters(term.key, character_notes),
            }
        )
    return {
        "schema": 1,
        "metadata": {
            "edition": edition,
            "asset_sha256": asset_sha256,
            "source_fingerprint": source_fingerprint(source),
            "rows": len(rows),
            "missing_french": sum(row["missing_fr"] for row in rows),
        },
        "languages": languages,
        "rows": rows,
        "references": {
            "universe": extract_markdown_section(agent_brief_markdown, "Univers et ton"),
            "characters": character_notes,
            "terminology": terminology_markdown.strip(),
        },
    }


def _json_for_script(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )


def write_review_workspace(payload: dict, output: Path) -> Path:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    html = REVIEW_HTML.replace("__REVIEW_DATA__", _json_for_script(payload))
    output.write_text(html, encoding="utf-8")
    return output


REVIEW_HTML = r'''<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; connect-src 'none'">
  <title>KuloNiku FR — Espace de relecture</title>
  <style>
    :root{color-scheme:light dark;--bg:#f5f1e8;--panel:#fffaf0;--text:#2a241f;--muted:#74695f;--line:#d8ccbd;--accent:#a3472b;--accent2:#256a63;--warn:#9a6519;--shadow:0 10px 30px #39291a18;--game-alert:#b83b25;--game-liked:#26734d;--game-disliked:#a52f54;--game-sour:#727d13;--game-skewer:#a45116;--game-drink:#2167a5;--game-spicy:#c23b24;--game-salty:#287485;--game-sweet:#a63d82}
    @media(prefers-color-scheme:dark){:root{--bg:#1c1917;--panel:#29231f;--text:#f5eee5;--muted:#b9ab9e;--line:#4c4038;--accent:#f08b68;--accent2:#69bdb3;--warn:#efb35e;--shadow:0 10px 30px #0005;--game-alert:#ff8b71;--game-liked:#78d5a7;--game-disliked:#f28cac;--game-sour:#ced76a;--game-skewer:#f0a15d;--game-drink:#79b8f2;--game-spicy:#ff8068;--game-salty:#75c5d2;--game-sweet:#ef91d0}}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}button,input,select,textarea{font:inherit}button{cursor:pointer}.shell{max-width:1500px;margin:auto;padding:24px}.top{display:flex;gap:20px;align-items:flex-start;justify-content:space-between;margin-bottom:18px}.top h1{font-size:clamp(25px,3vw,38px);margin:0 0 4px}.top p{margin:0;color:var(--muted)}.offline{padding:8px 12px;border:1px solid var(--accent2);border-radius:999px;color:var(--accent2);white-space:nowrap}.warning{background:color-mix(in srgb,var(--warn) 13%,var(--panel));border:1px solid color-mix(in srgb,var(--warn) 45%,var(--line));padding:12px 15px;border-radius:12px;margin-bottom:18px}.progress-wrap{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center;margin-bottom:18px}.bar{height:12px;background:var(--line);border-radius:10px;overflow:hidden}.bar span{display:block;height:100%;background:var(--accent2);width:0}.layout{display:grid;grid-template-columns:300px minmax(0,1fr);gap:18px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow)}.sidebar{padding:16px;position:sticky;top:16px;height:max-content}.field{margin-bottom:14px}.field label{display:block;font-weight:700;margin-bottom:5px}.field input,.field select{width:100%;padding:10px;border-radius:9px;border:1px solid var(--line);background:var(--bg);color:var(--text)}.counts{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:15px 0}.count{padding:10px;border:1px solid var(--line);border-radius:10px}.count b{display:block;font-size:20px}.actions{display:grid;gap:8px}.actions button,.nav button,.decision button,.raw-toggle{border:1px solid var(--line);border-radius:9px;padding:9px 11px;background:var(--bg);color:var(--text)}.actions button.primary{background:var(--accent2);color:white;border-color:var(--accent2)}.main{padding:20px;min-width:0}.nav{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:18px}.nav .position{color:var(--muted);text-align:center}.key{font:700 18px/1.4 ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere;margin:0}.meta{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 18px}.pill{border:1px solid var(--line);border-radius:999px;padding:4px 9px;color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;align-items:start}.lang{border:1px solid var(--line);border-radius:12px;min-width:0}.lang summary{cursor:pointer;padding:11px 12px;color:var(--muted);font-size:14px;font-weight:700}.lang summary:focus-visible{outline:2px solid var(--accent2);outline-offset:3px}.lang[open] summary{border-bottom:1px solid var(--line)}.language-hint{float:right;margin-left:12px;font-size:12px;font-weight:500}.lang-content{padding:11px 12px}.language-help{margin:0 0 10px;color:var(--muted);font-size:13px}.raw-toggle{width:100%;margin-bottom:14px}.raw-toggle[aria-pressed="true"]{border-color:var(--accent2);background:color-mix(in srgb,var(--accent2) 10%,var(--bg));color:var(--accent2);font-weight:700}.french{margin-top:14px;border:2px solid color-mix(in srgb,var(--accent) 65%,var(--line));border-radius:13px;padding:14px}.french h2,.section h2{font-size:18px;margin:0 0 9px}.french .value{font-size:20px;white-space:pre-wrap}.notes{color:var(--muted);white-space:pre-wrap;margin-top:8px}.length{margin-top:8px;color:var(--muted)}.decision{margin-top:18px;padding-top:18px;border-top:1px solid var(--line)}.decision-buttons{display:flex;flex-wrap:wrap;gap:8px}.decision button.active{background:var(--accent);color:white;border-color:var(--accent)}.proposal{display:none;margin-top:12px}.proposal.visible{display:block}.proposal label{display:block;font-weight:700;margin-top:9px}.proposal textarea{width:100%;min-height:90px;padding:10px;border-radius:9px;border:1px solid var(--line);background:var(--bg);color:var(--text)}.token-warning{display:none;color:var(--warn);font-weight:700;margin-top:7px}.token-warning.visible{display:block}.section{margin-top:18px;padding-top:18px;border-top:1px solid var(--line)}.neighbors{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.neighbor{border:1px solid var(--line);border-radius:10px;padding:10px}.neighbor button{all:unset;cursor:pointer;color:var(--accent2);font:700 13px/1.4 ui-monospace,SFMono-Regular,monospace;overflow-wrap:anywhere}.neighbor p{margin:5px 0 0;color:var(--muted);white-space:pre-wrap}.reference details{border:1px solid var(--line);border-radius:10px;padding:10px;margin-top:8px}.reference summary{cursor:pointer;font-weight:700}.reference pre{font:inherit;white-space:pre-wrap}.empty{padding:40px;text-align:center;color:var(--muted)}.file-input{display:none}@media(max-width:900px){.layout{grid-template-columns:1fr}.sidebar{position:static}.grid,.neighbors{grid-template-columns:1fr}.top{display:block}.offline{display:inline-block;margin-top:10px}}
    .top h1{font-size:2rem}.top p{max-width:70ch}.decision button.remove{color:var(--muted)}
    .game-text{white-space:pre-wrap;overflow-wrap:anywhere}.game-text.raw-text{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;color:var(--muted)}.game-color{font-weight:700;color:var(--accent2)}.game-color-alert{color:var(--game-alert)}.game-color-liked{color:var(--game-liked)}.game-color-disliked{color:var(--game-disliked)}.game-color-sour{color:var(--game-sour)}.game-color-skewer{color:var(--game-skewer)}.game-color-drink{color:var(--game-drink)}.game-color-spicy{color:var(--game-spicy)}.game-color-salty{color:var(--game-salty)}.game-color-sweet{color:var(--game-sweet)}.game-variable{display:inline-block;margin:0 1px;padding:0 5px;border:1px solid color-mix(in srgb,var(--accent2) 55%,var(--line));border-radius:5px;background:color-mix(in srgb,var(--accent2) 9%,transparent);color:var(--accent2);font:700 .88em/1.55 ui-monospace,SFMono-Regular,Consolas,monospace;vertical-align:.05em}.game-color .game-variable{border-color:currentColor;background:color-mix(in srgb,currentColor 11%,transparent);color:inherit}.game-nowrap{white-space:nowrap}.game-sprite{display:inline-flex;width:1.25em;height:1.25em;align-items:center;justify-content:center;margin:0 3px;border-radius:50%;background:color-mix(in srgb,var(--warn) 14%,transparent);color:var(--warn);font-size:.9em;font-weight:800;line-height:1;vertical-align:-.12em}.hidden-languages{display:flex;align-items:center;gap:10px;margin-top:10px;flex-wrap:wrap}.hidden-languages strong{color:var(--muted);font-size:13px}.hidden-language-list{display:flex;gap:6px;flex-wrap:wrap}.hidden-language-list button{border:1px solid var(--line);border-radius:999px;padding:5px 9px;background:transparent;color:var(--muted);font-size:12px}.hidden-language-list button:hover,.hidden-language-list button:focus-visible{border-color:var(--accent2);color:var(--accent2);outline:none}.clear-filters{width:100%;margin:-4px 0 14px;border:0;background:transparent;color:var(--accent2);font-weight:700;text-align:left;padding:4px 0}.clear-filters:hover{text-decoration:underline}.clear-filters:focus-visible{outline:2px solid var(--accent2);outline-offset:3px;border-radius:3px}
    .markdown{max-width:75ch}.markdown h1,.markdown h2,.markdown h3{font-size:1rem;margin:18px 0 7px}.markdown p{margin:9px 0}.markdown ul{padding-left:22px}.markdown code{background:var(--bg);border:1px solid var(--line);border-radius:5px;padding:1px 4px}.markdown a{color:var(--accent2)}.markdown table{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px}.markdown th,.markdown td{border:1px solid var(--line);padding:7px;text-align:left;vertical-align:top}.markdown th{background:var(--bg)}
    .top-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}.project-link,.button-link{display:block;border:1px solid var(--line);border-radius:9px;padding:8px 11px;color:var(--accent2);text-decoration:none;text-align:center;background:var(--panel)}.missing-callout{display:flex;justify-content:space-between;align-items:center;gap:18px;border:1px solid var(--accent2);border-radius:14px;padding:14px 16px;margin-bottom:18px;background:color-mix(in srgb,var(--accent2) 8%,var(--panel))}.missing-callout p{margin:3px 0 0;color:var(--muted)}.missing-callout button{border:1px solid var(--accent2);border-radius:9px;padding:8px 11px;background:var(--accent2);color:var(--panel);white-space:nowrap}.view-switch{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-bottom:14px}.view-switch button{border:1px solid var(--line);padding:8px;background:var(--bg);color:var(--text)}.view-switch button:first-child{border-radius:9px 0 0 9px}.view-switch button:last-child{border-radius:0 9px 9px 0}.view-switch button.active{background:var(--accent2);border-color:var(--accent2);color:var(--panel)}.counts .count{background:transparent;color:var(--text);text-align:left;cursor:pointer}.counts .count:hover,.counts .count.active{border-color:var(--accent2);background:color-mix(in srgb,var(--accent2) 8%,transparent)}.counts .count:disabled{cursor:default;opacity:.6}.action-heading{margin:16px 0 7px;padding-top:14px;border-top:1px solid var(--line);font-size:14px}.action-help{margin:0 2px 5px;color:var(--muted);font-size:12px}.copy-status{min-height:1.5em;color:var(--accent2);font-size:13px}.table-wrap{overflow:auto}.review-table{width:100%;border-collapse:collapse;font-size:14px}.review-table th,.review-table td{padding:9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}.review-table th{position:sticky;top:0;background:var(--panel);z-index:1}.review-table tr:hover td{background:color-mix(in srgb,var(--accent2) 6%,transparent)}.review-table button{all:unset;cursor:pointer;color:var(--accent2);font:700 13px/1.4 ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere}.status{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:2px 7px;white-space:nowrap;color:var(--muted)}.status.missing{border-color:var(--warn);color:var(--warn)}.list-note{margin:0 0 14px;color:var(--muted)}@media(max-width:900px){.top-actions{justify-content:flex-start;margin-top:10px}.missing-callout{align-items:flex-start;flex-direction:column}.review-table{min-width:760px}}
  </style>
</head>
<body>
<div class="shell">
  <header class="top"><div><h1>Espace de relecture KuloNiku FR</h1><p>Explorez librement les textes et sélectionnez seulement ceux sur lesquels vous souhaitez intervenir.</p></div><div class="top-actions"><a class="project-link" href="https://github.com/Le-Moulin/KuloNiku-FR" target="_blank" rel="noreferrer">Projet GitHub ↗</a><span class="offline">100 % hors ligne</span></div></header>
  <div class="warning"><b>Document privé de travail.</b> Il contient des textes extraits de votre copie du jeu. Ne le publiez pas et ne l’ajoutez pas au dépôt.</div>
  <section class="missing-callout" id="missingCallout"><div><b id="missingTitle">Recherche des traductions manquantes…</b><p>L’analyse compare automatiquement les clés du jeu installé avec la traduction française. Elle repérera aussi les nouveaux textes ajoutés lors de futures mises à jour.</p></div><button id="showMissing">Afficher</button></section>
  <div class="layout">
    <aside class="panel sidebar">
      <div class="view-switch" aria-label="Mode d’affichage"><button id="viewCard" class="active">Fiche</button><button id="viewList">Liste</button></div>
      <button class="raw-toggle" id="toggleRaw" type="button" aria-pressed="false">Afficher le texte brut</button>
      <div class="field"><label for="search">Rechercher</label><input id="search" type="search" placeholder="Clé, français ou texte source"></div>
      <div class="field"><label for="macro">Ensemble</label><select id="macro"><option value="">Tous</option><option value="culinary">Cuisine</option><option value="interface-gameplay">Interface et jouabilité</option><option value="world">Monde et progression</option><option value="dialogue">Dialogues</option></select></div>
      <div class="field"><label for="category">Catégorie</label><select id="category"><option value="">Toutes</option></select></div>
      <div class="field"><label for="state">Afficher</label><select id="state"><option value="">Tous les textes</option><option value="missing">Traductions manquantes</option><option value="selected">Ma sélection</option><option value="proposals">Propositions renseignées</option><option value="change">Corrections à préparer</option><option value="ambiguous">Ambiguïtés</option><option value="in_game">À vérifier en jeu</option></select></div>
      <button class="clear-filters" id="clearFilters" type="button" hidden>× Effacer les filtres</button>
      <div class="counts"><button class="count" id="showSelectedCount"><b id="selectedCount">0</b><span>sélectionnés</span></button><button class="count" id="showProposalCount"><b id="proposalCount">0</b><span>propositions</span></button></div>
      <div class="actions">
        <button class="primary" id="exportProgress">Exporter ma sélection</button>
        <button id="exportCsv">Exporter les propositions</button>
        <p class="action-help">Pour les essayer en jeu, exportez-les puis ouvrez « Avancé » et choisissez « Importer mon fichier de correction » dans l’application KuloNiku FR.</p>
        <button id="importButton">Importer une sélection</button>
        <input class="file-input" id="importFile" type="file" accept="application/json,.json">
        <h2 class="action-heading">Partager le travail</h2>
        <button id="copyIssue">Copier le résumé pour GitHub</button>
        <a class="button-link" href="https://github.com/Le-Moulin/KuloNiku-FR/issues/new?template=review.yml" target="_blank" rel="noreferrer">Ouvrir une issue GitHub ↗</a>
        <div class="copy-status" id="copyStatus" role="status"></div>
      </div>
    </aside>
    <main class="panel main" id="main"></main>
  </div>
</div>
<script id="reviewData" type="application/json">__REVIEW_DATA__</script>
<script>
(() => {
  'use strict';
  const data=JSON.parse(document.getElementById('reviewData').textContent);
  const rows=data.rows, byKey=new Map(rows.map(r=>[r.key,r]));
  const storageKey='kuloniku-review-'+data.metadata.source_fingerprint;
  const uiStorageKey='kuloniku-review-ui-v1',defaultExpandedLanguages=['en','de','es','pt','id'];
  let progress={}; try{progress=JSON.parse(localStorage.getItem(storageKey)||'{}')}catch(_){progress={}}
  let uiPrefs={expandedLanguages:[...defaultExpandedLanguages],rawMode:false};
  try{const saved=JSON.parse(localStorage.getItem(uiStorageKey)||'{}');if(Array.isArray(saved.expandedLanguages))uiPrefs.expandedLanguages=saved.expandedLanguages;if(typeof saved.rawMode==='boolean')uiPrefs.rawMode=saved.rawMode}catch(_){}
  for(const key of Object.keys(progress)){if(progress[key]?.state==='approved')delete progress[key]}
  let filtered=[], cursor=0, listPage=0, view='card';
  const pageSize=100;
  const $=id=>document.getElementById(id), main=$('main');
  const escapeCsv=v=>'"'+String(v??'').replaceAll('"','""')+'"';
  const save=()=>{try{localStorage.setItem(storageKey,JSON.stringify(progress))}catch(_){}}
  const saveUi=()=>{try{localStorage.setItem(uiStorageKey,JSON.stringify(uiPrefs))}catch(_){}}
  const normalize=v=>String(v||'').toLocaleLowerCase('fr');
  const categoryValues=[...new Set(rows.map(r=>r.category))].sort((a,b)=>a.localeCompare(b,'fr'));
  for(const value of categoryValues){const option=document.createElement('option');option.value=value;option.textContent=value;$('category').append(option)}
  const missingCount=data.metadata.missing_french??rows.filter(row=>row.missing_fr).length;
  $('missingTitle').textContent=missingCount?`${missingCount} traduction${missingCount>1?'s':''} française${missingCount>1?'s':''} manquante${missingCount>1?'s':''} détectée${missingCount>1?'s':''}`:'Aucune traduction française manquante détectée';
  $('showMissing').hidden=missingCount===0;
  function currentDecision(key){return progress[key]||{state:'unreviewed',proposal:'',notes:''}}
  function applyFilters(keepKey){
    const q=normalize($('search').value), macro=$('macro').value, category=$('category').value, state=$('state').value;
    $('clearFilters').hidden=!(q||macro||category||state);
    filtered=rows.filter(row=>{
      const decision=currentDecision(row.key);
      if(macro&&row.macro!==macro)return false;if(category&&row.category!==category)return false;
      if(state==='missing'&&!row.missing_fr)return false;
      if(state==='selected'&&decision.state==='unreviewed')return false;
      if(state==='proposals'&&!((decision.state==='change'||decision.state==='ambiguous')&&String(decision.proposal||'').trim()))return false;
      if(state&&!['selected','missing','proposals'].includes(state)&&decision.state!==state)return false;
      if(!q)return true;
      return [row.key,row.fr,row.translation_notes,...Object.values(row.languages)].some(v=>normalize(v).includes(q));
    });
    const found=keepKey?filtered.findIndex(r=>r.key===keepKey):-1;cursor=found>=0?found:Math.min(cursor,Math.max(0,filtered.length-1));listPage=0;render();
  }
  function el(tag,className,text){const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node}
  function button(text,onClick){const node=el('button','',text);node.addEventListener('click',onClick);return node}
  function renderGameText(value,className=''){
    const root=el('div',`game-text ${className}`.trim()),stack=[{kind:'root',node:root}];
    const current=()=>stack[stack.length-1].node;
    const source=String(value||'—');
    const pattern=/(\[COLOR=[^\]]+\]|\[\/COLOR\]|<br\s*\/?>|<\/?b>|<\/?nobr>|<sprite\b[^>]*>|\{[^{}\r\n]+\}|\[[^\]\r\n]+\])/gi;
    let cursor=0;
    const close=kind=>{if(stack.length>1&&stack[stack.length-1].kind===kind)stack.pop()};
    for(const match of source.matchAll(pattern)){
      if(match.index>cursor)current().append(document.createTextNode(source.slice(cursor,match.index)));
      const token=match[0],upper=token.toUpperCase(),color=token.match(/^\[COLOR=([^\]]+)\]$/i);
      if(color){const role=color[1].trim().toLowerCase().replace(/[^a-z0-9_-]+/g,'-'),span=el('span',`game-color game-color-${role}`);span.title=`Couleur du jeu : ${color[1]}`;current().append(span);stack.push({kind:'color',node:span})}
      else if(upper==='[/COLOR]')close('color');
      else if(/^<br\s*\/?>$/i.test(token))current().append(document.createElement('br'));
      else if(upper==='<B>'){const strong=document.createElement('strong');current().append(strong);stack.push({kind:'bold',node:strong})}
      else if(upper==='</B>')close('bold');
      else if(upper==='<NOBR>'){const span=el('span','game-nowrap');current().append(span);stack.push({kind:'nobr',node:span})}
      else if(upper==='</NOBR>')close('nobr');
      else if(/^<sprite\b/i.test(token)){const money=/icon_money/i.test(token),sprite=el('span','game-sprite','◆');sprite.title=token;sprite.setAttribute('role','img');sprite.setAttribute('aria-label',money?'Icône monnaie':'Icône du jeu');current().append(sprite)}
      else if(/^\{[^{}\r\n]+\}$/.test(token)||/^\[(?:[A-Z][A-Z0-9_]*|[xyzXYZ])\]$/.test(token)){const variable=el('span','game-variable',token);variable.title='Valeur remplacée automatiquement par le jeu';current().append(variable)}
      else current().append(document.createTextNode(token));
      cursor=match.index+token.length;
    }
    if(cursor<source.length)current().append(document.createTextNode(source.slice(cursor)));
    return root
  }
  function renderDisplayedText(value,className=''){return uiPrefs.rawMode?el('div',`game-text raw-text ${className}`.trim(),value||'—'):renderGameText(value,className)}
  function renderLanguage(language,value){
    const code=language.code,raw=String(value||'—'),card=el('details','lang');
    card.open=true;card.title=`Texte brut :\n${raw}`;
    const summary=document.createElement('summary'),name=el('span','language-name',`${language.name} · ${code}`),hint=el('span','language-hint','Replier');
    summary.append(name,hint);const content=el('div','lang-content');content.append(renderDisplayedText(raw));card.append(summary,content);
    card.addEventListener('toggle',()=>{if(card.open)return;uiPrefs.expandedLanguages=uiPrefs.expandedLanguages.filter(item=>item!==code);saveUi();render()});
    return card
  }
  function renderHiddenLanguages(languages,row){
    const section=el('section','hidden-languages'),list=el('div','hidden-language-list');section.append(el('strong','','Autres langues'));
    for(const language of languages){const raw=String(row.languages[language.code]||'—'),show=button(`+ ${language.name} · ${language.code}`,()=>{uiPrefs.expandedLanguages=[...new Set([...uiPrefs.expandedLanguages,language.code])];saveUi();render()});show.title=`Texte brut :\n${raw}`;show.setAttribute('aria-label',`Afficher ${language.name}`);list.append(show)}
    section.append(list);return section
  }
  function appendInline(parent,text){
    const pattern=/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\(https?:\/\/[^)]+\))/g;let cursor=0;
    for(const match of text.matchAll(pattern)){if(match.index>cursor)parent.append(document.createTextNode(text.slice(cursor,match.index)));const token=match[0];if(token.startsWith('**'))parent.append(el('strong','',token.slice(2,-2)));else if(token.startsWith('`'))parent.append(el('code','',token.slice(1,-1)));else{const parts=token.match(/^\[([^\]]+)\]\((https?:\/\/[^)]+)\)$/);const link=el('a','',parts[1]);link.href=parts[2];link.target='_blank';link.rel='noreferrer';parent.append(link)}cursor=match.index+token.length}if(cursor<text.length)parent.append(document.createTextNode(text.slice(cursor)))
  }
  function renderMarkdown(markdown){
    const root=el('div','markdown'), lines=String(markdown||'').split(/\r?\n/);let list=null,lastItem=null;
    const startsBlock=(line,index)=>/^(#{1,3})\s+/.test(line)||/^[-*]\s+/.test(line)||(/^\|.+\|$/.test(line)&&index+1<lines.length&&/^\|(?:\s*:?-+:?\s*\|)+$/.test(lines[index+1]));
    for(let i=0;i<lines.length;){const line=lines[i];if(!line.trim()){list=null;lastItem=null;i++;continue}if(/^\|.+\|$/.test(line)&&i+1<lines.length&&/^\|(?:\s*:?-+:?\s*\|)+$/.test(lines[i+1])){const table=document.createElement('table'),head=document.createElement('thead'),body=document.createElement('tbody'),header=document.createElement('tr');for(const cell of line.slice(1,-1).split('|')){const th=document.createElement('th');appendInline(th,cell.trim());header.append(th)}head.append(header);i+=2;while(i<lines.length&&/^\|.+\|$/.test(lines[i])){const tr=document.createElement('tr');for(const cell of lines[i].slice(1,-1).split('|')){const td=document.createElement('td');appendInline(td,cell.trim());tr.append(td)}body.append(tr);i++}table.append(head,body);root.append(table);list=null;lastItem=null;continue}const heading=line.match(/^(#{1,3})\s+(.+)$/);if(heading){const node=document.createElement('h'+heading[1].length);appendInline(node,heading[2]);root.append(node);list=null;lastItem=null;i++;continue}const bullet=line.match(/^[-*]\s+(.+)$/);if(bullet){if(!list){list=document.createElement('ul');root.append(list)}lastItem=document.createElement('li');appendInline(lastItem,bullet[1]);list.append(lastItem);i++;continue}if(list&&lastItem&&/^\s+/.test(line)){lastItem.append(document.createTextNode(' '));appendInline(lastItem,line.trim());i++;continue}const parts=[line.trim()];i++;while(i<lines.length&&lines[i].trim()&&!startsBlock(lines[i],i)){parts.push(lines[i].trim());i++}const paragraph=document.createElement('p');appendInline(paragraph,parts.join(' '));root.append(paragraph);list=null;lastItem=null}return root
  }
  function tokens(value){return [...String(value||'').matchAll(/\[[^\]]+\]|\{[^}]+\}|<[^>]+>/g)].map(m=>m[0]).sort()}
  function sameTokens(a,b){return JSON.stringify(tokens(a))===JSON.stringify(tokens(b))}
  function goToKey(key){view='card';const index=filtered.findIndex(r=>r.key===key);if(index>=0){cursor=index;render()}else{$('search').value=key;applyFilters(key)}}
  function updateViewButtons(){$('viewCard').classList.toggle('active',view==='card');$('viewList').classList.toggle('active',view==='list');$('toggleRaw').setAttribute('aria-pressed',String(uiPrefs.rawMode));$('toggleRaw').textContent=uiPrefs.rawMode?'Afficher le texte mis en forme':'Afficher le texte brut'}
  function render(){updateCounts();updateViewButtons();main.textContent='';if(!filtered.length){main.append(el('div','empty','Aucune entrée ne correspond aux filtres.'));return}if(view==='list'){renderList();return}renderCard()}
  function renderCard(){
    const row=filtered[cursor], decision=currentDecision(row.key);
    const nav=el('div','nav');nav.append(button('← Précédent',()=>{cursor=Math.max(0,cursor-1);render()}));nav.append(el('div','position',`${cursor+1} / ${filtered.length}`));nav.append(button('Suivant →',()=>{cursor=Math.min(filtered.length-1,cursor+1);render()}));main.append(nav);
    main.append(el('h1','key',row.key));const meta=el('div','meta');for(const text of [row.category,row.group,labelMacro(row.macro),`max. ${row.max_source_chars} caractères`])meta.append(el('span','pill',text));main.append(meta);
    main.append(el('p','language-help','Survolez une langue pour voir son texte brut. Repliez-la depuis son en-tête.'));
    const expanded=data.languages.filter(language=>uiPrefs.expandedLanguages.includes(language.code)),hidden=data.languages.filter(language=>!uiPrefs.expandedLanguages.includes(language.code)),grid=el('div','grid');for(const language of expanded)grid.append(renderLanguage(language,row.languages[language.code]));if(expanded.length)main.append(grid);if(hidden.length)main.append(renderHiddenLanguages(hidden,row));
    const french=el('section','french');french.append(el('h2','','Français actuel'));french.append(renderDisplayedText(row.fr,'value'));const chars=String(row.fr||'').length;french.append(el('div','length',`${chars} caractères · référence ${row.max_source_chars}`));if(row.translation_notes)french.append(el('div','notes',row.translation_notes));main.append(french);
    const review=el('section','decision');review.append(el('h2','','Ajouter à votre sélection'));const choices=el('div','decision-buttons');for(const [value,label] of [['change','Proposer une correction'],['ambiguous','Signaler une ambiguïté'],['in_game','À vérifier en jeu']]){const b=button(label,()=>{progress[row.key]={...currentDecision(row.key),state:value};save();render()});if(decision.state===value)b.classList.add('active');choices.append(b)}if(decision.state!=='unreviewed'){const remove=button('Retirer de la sélection',()=>{delete progress[row.key];save();render()});remove.classList.add('remove');choices.append(remove)}review.append(choices);
    const proposal=el('div','proposal'+(decision.state!=='unreviewed'?' visible':''));const pLabel=el('label','','Proposition française (facultative)');const p=el('textarea');p.id='proposalText';pLabel.htmlFor=p.id;p.value=decision.proposal||'';const len=el('div','length');const warning=el('div','token-warning','Attention : variables ou balises différentes du français actuel.');const nLabel=el('label','','Justification ou contexte');const n=el('textarea');n.id='proposalNotes';nLabel.htmlFor=n.id;n.value=decision.notes||'';function updateProposal(){const d=currentDecision(row.key);d.proposal=p.value;d.notes=n.value;if(d.state==='unreviewed'&&!d.proposal&&!d.notes)delete progress[row.key];else progress[row.key]=d;len.textContent=`${p.value.length} caractères · référence ${row.max_source_chars}`;warning.classList.toggle('visible',!!p.value&&!sameTokens(row.fr,p.value));save();updateCounts()}p.addEventListener('input',updateProposal);n.addEventListener('input',updateProposal);proposal.append(pLabel,p,len,warning,nLabel,n);review.append(proposal);main.append(review);updateProposal();
    renderNeighbors(row);renderReferences(row);
  }
  function rowStatus(row){const state=currentDecision(row.key).state;if(row.missing_fr)return ['Traduction manquante','missing'];return [{change:'Correction',ambiguous:'Ambiguïté',in_game:'À vérifier'}[state]||'','']}
  function renderList(){
    const pages=Math.max(1,Math.ceil(filtered.length/pageSize));listPage=Math.min(listPage,pages-1);const start=listPage*pageSize,end=Math.min(filtered.length,start+pageSize);
    const nav=el('div','nav');nav.append(button('← Page précédente',()=>{listPage=Math.max(0,listPage-1);render()}));nav.append(el('div','position',`${start+1}–${end} / ${filtered.length}`));nav.append(button('Page suivante →',()=>{listPage=Math.min(pages-1,listPage+1);render()}));main.append(nav);
    main.append(el('p','list-note','Cliquez sur une clé pour ouvrir sa fiche détaillée. La liste affiche 100 résultats par page.'));
    const wrap=el('div','table-wrap'),table=el('table','review-table'),head=document.createElement('thead'),headRow=document.createElement('tr');for(const title of ['Clé','Français actuel','Anglais','État'])headRow.append(el('th','',title));head.append(headRow);const body=document.createElement('tbody');
    for(const row of filtered.slice(start,end)){const tr=document.createElement('tr'),keyCell=document.createElement('td'),fr=document.createElement('td'),en=document.createElement('td'),statusCell=document.createElement('td');keyCell.append(button(row.key,()=>{cursor=filtered.findIndex(item=>item.key===row.key);view='card';render()}));fr.append(renderDisplayedText(row.fr));en.append(renderDisplayedText(row.languages.en));const [label,className]=rowStatus(row);if(label)statusCell.append(el('span','status '+className,label));tr.append(keyCell,fr,en,statusCell);body.append(tr)}table.append(head,body);wrap.append(table);main.append(wrap)
  }
  function labelMacro(value){return {'culinary':'Cuisine','interface-gameplay':'Interface et jouabilité','world':'Monde et progression','dialogue':'Dialogues'}[value]||value}
  function renderNeighbors(row){const same=rows.filter(r=>r.group===row.group), pos=same.findIndex(r=>r.key===row.key), candidates=[...same.slice(Math.max(0,pos-2),pos),...same.slice(pos+1,pos+3)];const section=el('section','section');section.append(el('h2','','Clés adjacentes du même groupe'));const wrap=el('div','neighbors');if(!candidates.length)wrap.append(el('p','notes','Aucune clé voisine dans ce groupe.'));for(const item of candidates){const card=el('div','neighbor');card.append(button(item.key,()=>goToKey(item.key)));card.append(renderDisplayedText(item.fr||item.languages.en||item.languages.id||'—'));wrap.append(card)}section.append(wrap);main.append(section)}
  function renderReferences(row){const section=el('section','section reference');section.append(el('h2','','Contexte et références'));if(row.characters.length){for(const name of row.characters){const box=document.createElement('details');box.open=true;const summary=document.createElement('summary');summary.textContent=name;box.append(summary,renderMarkdown(data.references.characters[name]));section.append(box)}}const universe=document.createElement('details');const us=document.createElement('summary');us.textContent='Univers et ton';universe.append(us,renderMarkdown(data.references.universe));section.append(universe);const terms=document.createElement('details');const ts=document.createElement('summary');ts.textContent='Glossaire et terminologie';terms.append(ts,renderMarkdown(data.references.terminology));section.append(terms);main.append(section)}
  function updateCounts(){const selected=rows.filter(row=>{const v=progress[row.key];return v&&v.state&&v.state!=='unreviewed'}).length,proposals=rows.filter(row=>{const v=progress[row.key];return v&&(v.state==='change'||v.state==='ambiguous')&&String(v.proposal||'').trim()}).length,state=$('state').value;$('selectedCount').textContent=selected;$('proposalCount').textContent=proposals;$('showSelectedCount').disabled=selected===0;$('showProposalCount').disabled=proposals===0;$('showSelectedCount').classList.toggle('active',state==='selected');$('showProposalCount').classList.toggle('active',state==='proposals')}
  function showCountFilter(state,count){if(!count)return;$('state').value=state;view=count===1?'card':'list';applyFilters()}
  function issueSummary(){const selected=rows.filter(row=>currentDecision(row.key).state!=='unreviewed');if(!selected.length)return'';const corrections=selected.filter(row=>currentDecision(row.key).state==='change').length,ambiguities=selected.filter(row=>currentDecision(row.key).state==='ambiguous').length,inGame=selected.filter(row=>currentDecision(row.key).state==='in_game').length;return `### Relecture préparée avec l’espace KuloNiku FR\n\n- Édition : ${data.metadata.edition}\n- Passages sélectionnés : ${selected.length}\n- Corrections proposées : ${corrections}\n- Ambiguïtés signalées : ${ambiguities}\n- Vérifications en jeu : ${inGame}\n\nFichiers à joindre : \`kuloniku-fr-propositions.csv\` et, si utile, \`kuloniku-fr-selection.json\`.\n`}
  async function copyText(value){try{await navigator.clipboard.writeText(value);return true}catch(_){const area=document.createElement('textarea');area.value=value;area.style.position='fixed';area.style.opacity='0';document.body.append(area);area.select();const copied=document.execCommand('copy');area.remove();return copied}}
  function download(name,type,content){const blob=new Blob([content],{type}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
  $('exportProgress').addEventListener('click',()=>download('kuloniku-fr-selection.json','application/json',JSON.stringify({schema:1,metadata:data.metadata,progress},null,2)+'\n'));
  $('exportCsv').addEventListener('click',()=>{const lines=['key,fr,status,notes,source_fingerprint'];for(const row of rows){const d=currentDecision(row.key);if((d.state==='change'||d.state==='ambiguous')&&d.proposal.trim()){const note=`Relecture externe : ${d.notes||d.state}`;lines.push([row.key,d.proposal,'provisional',note,data.metadata.source_fingerprint].map(escapeCsv).join(','))}}download('kuloniku-fr-propositions.csv','text/csv;charset=utf-8','\ufeff'+lines.join('\n')+'\n')});
  $('importButton').addEventListener('click',()=>$('importFile').click());$('importFile').addEventListener('change',event=>{const file=event.target.files[0];if(!file)return;const reader=new FileReader();reader.onload=()=>{try{const incoming=JSON.parse(reader.result);if(incoming.metadata?.source_fingerprint!==data.metadata.source_fingerprint)throw new Error('Cette sélection correspond à une autre version des textes du jeu.');progress=incoming.progress||{};for(const key of Object.keys(progress)){if(progress[key]?.state==='approved')delete progress[key]}save();applyFilters()}catch(error){alert(error.message)}};reader.readAsText(file)});
  $('viewCard').addEventListener('click',()=>{view='card';render()});$('viewList').addEventListener('click',()=>{view='list';listPage=Math.floor(cursor/pageSize);render()});
  $('toggleRaw').addEventListener('click',()=>{uiPrefs.rawMode=!uiPrefs.rawMode;saveUi();render()});
  $('clearFilters').addEventListener('click',()=>{for(const id of ['search','macro','category','state'])$(id).value='';applyFilters()});
  $('showMissing').addEventListener('click',()=>{$('state').value='missing';view='list';applyFilters()});
  $('showSelectedCount').addEventListener('click',()=>showCountFilter('selected',Number($('selectedCount').textContent)));$('showProposalCount').addEventListener('click',()=>showCountFilter('proposals',Number($('proposalCount').textContent)));
  $('copyIssue').addEventListener('click',async()=>{const summary=issueSummary();if(!summary){$('copyStatus').textContent='Sélectionnez au moins un passage.';return}const copied=await copyText(summary);$('copyStatus').textContent=copied?'Résumé copié. Collez-le dans l’issue GitHub.':'Copie impossible. Exportez les fichiers puis ouvrez l’issue.'});
  for(const id of ['search','macro','category','state'])$(id).addEventListener(id==='search'?'input':'change',()=>applyFilters(filtered[cursor]?.key));
  applyFilters();
})();
</script>
</body>
</html>
'''
