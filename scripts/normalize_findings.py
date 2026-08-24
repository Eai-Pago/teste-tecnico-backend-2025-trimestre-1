#!/usr/bin/env python3
"""
scripts/normalize_findings.py — SIGNAL / MOVSEC

Consolida a saída de todas as ferramentas de scan (SARIF 2.1.0, OSV-Scanner,
Trivy) em dois artefatos:

  FINDINGS.md    relatório legível, com arquivo:linha e o trecho de código
                 recortado — feito para ser lido pelo Claude Code
  findings.json  mesma informação em formato estruturado

Uso:
  python scripts/normalize_findings.py --reports reports/ --root . --out .

Sem dependências externas. Python 3.10+.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

CONTEXT_LINES = 4
SEV_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
SEV_EMOJI = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵", "INFO": "⚪"}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def normalize_severity(level: str | None, security_severity: str | None) -> str:
    """SARIF traz severidade em dois lugares. O score numérico é mais preciso."""
    if security_severity:
        try:
            score = float(security_severity)
            if score >= 9.0:
                return "CRITICAL"
            if score >= 7.0:
                return "HIGH"
            if score >= 4.0:
                return "MEDIUM"
            if score > 0:
                return "LOW"
        except (TypeError, ValueError):
            pass
    return {
        "error": "HIGH",
        "warning": "MEDIUM",
        "note": "LOW",
        "none": "INFO",
    }.get((level or "warning").lower(), "MEDIUM")


def clean_uri(uri: str, root: Path) -> str:
    """Devolve caminho relativo à raiz do repo, do jeito que o editor espera."""
    if not uri:
        return ""
    uri = uri.removeprefix("file://")
    p = Path(uri)
    if p.is_absolute():
        try:
            return str(p.relative_to(root.resolve()))
        except ValueError:
            return str(p)
    return str(p).lstrip("./")


def read_snippet(root: Path, rel_path: str, start: int, end: int | None) -> str | None:
    """Recorta o trecho real do arquivo, com contexto e marcador na linha do achado."""
    if not rel_path or not start:
        return None
    fpath = root / rel_path
    if not fpath.is_file():
        return None
    try:
        lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None

    end = end or start
    lo = max(1, start - CONTEXT_LINES)
    hi = min(len(lines), end + CONTEXT_LINES)
    width = len(str(hi))

    out = []
    for n in range(lo, hi + 1):
        marker = ">" if start <= n <= end else " "
        out.append(f"{str(n).rjust(width)} {marker} {lines[n - 1]}")
    return "\n".join(out)


def language_of(rel_path: str) -> str:
    return {
        ".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "tsx",
        ".go": "go", ".rb": "ruby", ".java": "java", ".sh": "bash",
        ".yml": "yaml", ".yaml": "yaml", ".tf": "hcl", ".json": "json",
        ".sql": "sql", ".html": "html", ".toml": "toml",
    }.get(Path(rel_path).suffix.lower(), "text")


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_sarif(path: Path, root: Path) -> list[dict]:
    """Parser genérico de SARIF 2.1.0 — serve para OpenGrep, Gitleaks,
    Trivy, Hadolint, Checkov, zizmor e qualquer outra ferramenta conforme."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"  ! ignorando {path.name}: {exc}", file=sys.stderr)
        return []

    findings: list[dict] = []

    for run in data.get("runs", []):
        driver = run.get("tool", {}).get("driver", {})
        tool = driver.get("name", path.stem)

        # Indexa metadados de regra para enriquecer o achado
        rules: dict[str, dict] = {}
        rules_by_idx: list[dict] = []
        for rule in driver.get("rules", []) or []:
            rules[rule.get("id", "")] = rule
            rules_by_idx.append(rule)

        for res in run.get("results", []):
            # Honra supressão inline (nosemgrep/# noqa): o SARIF do OpenGrep NÃO omite
            # o achado suprimido — inclui-o marcado em `suppressions`. Sem esta guarda
            # o relatório recontava tudo que o nosemgrep já havia dispensado no código.
            if res.get("suppressions"):
                continue
            rule_id = res.get("ruleId") or ""
            rule = rules.get(rule_id)
            if rule is None:
                idx = res.get("ruleIndex")
                if isinstance(idx, int) and 0 <= idx < len(rules_by_idx):
                    rule = rules_by_idx[idx]
            rule = rule or {}

            props = rule.get("properties", {}) or {}
            severity = normalize_severity(
                res.get("level") or rule.get("defaultConfiguration", {}).get("level"),
                props.get("security-severity"),
            )

            # Ruff é lint, não SAST. Ele emite TUDO como level=error, o que inflava
            # o relatório com 1400+ "HIGH" de ordenação de import e linha longa.
            # Só as regras Bandit (prefixo S) têm peso real de segurança.
            if tool.lower().startswith("ruff"):
                severity = "MEDIUM" if rule_id.startswith("S") else "INFO"

            locs = res.get("locations") or []
            phys = (locs[0].get("physicalLocation", {}) if locs else {})
            rel = clean_uri(phys.get("artifactLocation", {}).get("uri", ""), root)
            region = phys.get("region", {}) or {}
            start = region.get("startLine")
            end = region.get("endLine")

            snippet = (region.get("snippet", {}) or {}).get("text")
            if snippet:
                snippet = snippet.rstrip()
            else:
                snippet = read_snippet(root, rel, start, end)

            tags = [t for t in (props.get("tags") or []) if isinstance(t, str)]
            guidance = (
                (rule.get("help", {}) or {}).get("text")
                or (rule.get("fullDescription", {}) or {}).get("text")
                or ""
            ).strip()

            findings.append({
                "kind": "code",
                "tool": tool,
                "rule_id": rule_id,
                "rule_name": rule.get("name") or (rule.get("shortDescription", {}) or {}).get("text", ""),
                "severity": severity,
                "message": (res.get("message", {}) or {}).get("text", "").strip(),
                "file": rel,
                "start_line": start,
                "end_line": end,
                "start_column": region.get("startColumn"),
                "snippet": snippet,
                "language": language_of(rel),
                "tags": tags,
                "guidance": guidance,
                "help_uri": rule.get("helpUri", ""),
            })

    return findings


def _sarif_tools(path: Path) -> set[str]:
    """Nomes das ferramentas (drivers) que rodaram neste SARIF, MESMO com 0 achados.
    Necessário para o `health`: o Signal só fecha um achado ausente se a ferramenta
    que o havia encontrado comprovadamente rodou no scan atual (trava anti-silêncio).
    Sem isto, um SAST que corrige tudo (0 resultados) nunca marcaria a correção."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    out: set[str] = set()
    for run in data.get("runs", []) or []:
        name = ((run.get("tool", {}) or {}).get("driver", {}) or {}).get("name")
        if name:
            out.add(name)
    return out


def parse_osv(path: Path, root: Path) -> list[dict]:
    """OSV-Scanner traz versão corrigida, que o SARIF dele omite."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    findings = []
    for result in data.get("results", []) or []:
        manifest = clean_uri((result.get("source", {}) or {}).get("path", ""), root)
        for pkg in result.get("packages", []) or []:
            info = pkg.get("package", {}) or {}
            name = info.get("name", "?")
            version = info.get("version", "?")
            ecosystem = info.get("ecosystem", "")

            for vuln in pkg.get("vulnerabilities", []) or []:
                fixed = set()
                for affected in vuln.get("affected", []) or []:
                    for rng in affected.get("ranges", []) or []:
                        for ev in rng.get("events", []) or []:
                            if ev.get("fixed"):
                                fixed.add(ev["fixed"])

                sev = "MEDIUM"
                for s in vuln.get("severity", []) or []:
                    if s.get("type", "").startswith("CVSS"):
                        sev = normalize_severity(None, _cvss_to_score(s.get("score", "")))
                        break
                if vuln.get("database_specific", {}).get("severity"):
                    sev = str(vuln["database_specific"]["severity"]).upper()

                findings.append({
                    "kind": "dependency",
                    "tool": "OSV-Scanner",
                    "rule_id": vuln.get("id", ""),
                    "severity": sev if sev in SEV_ORDER else "MEDIUM",
                    "message": (vuln.get("summary") or vuln.get("details", ""))[:400].strip(),
                    "file": manifest,
                    "package": name,
                    "ecosystem": ecosystem,
                    "installed_version": version,
                    "fixed_versions": sorted(fixed),
                    "aliases": vuln.get("aliases", []),
                    "help_uri": f"https://osv.dev/vulnerability/{vuln.get('id', '')}",
                })
    return findings


def _cvss_to_score(vector: str) -> str | None:
    """Não calcula CVSS; só extrai score numérico quando já vier pronto."""
    try:
        return str(float(vector))
    except (TypeError, ValueError):
        return None


def parse_trivy(path: Path, root: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if "Results" not in data:
        return []

    findings = []
    for result in data.get("Results", []) or []:
        target = clean_uri(result.get("Target", ""), root)

        for v in result.get("Vulnerabilities", []) or []:
            findings.append({
                "kind": "dependency",
                "tool": "Trivy",
                "rule_id": v.get("VulnerabilityID", ""),
                "severity": (v.get("Severity") or "MEDIUM").upper(),
                "message": (v.get("Title") or v.get("Description", ""))[:400].strip(),
                "file": target,
                "package": v.get("PkgName", ""),
                "installed_version": v.get("InstalledVersion", ""),
                "fixed_versions": [v["FixedVersion"]] if v.get("FixedVersion") else [],
                "help_uri": v.get("PrimaryURL", ""),
            })

        # Misconfigurações de IaC/Dockerfile: essas TÊM linha, são corrigíveis no código
        for m in result.get("Misconfigurations", []) or []:
            cause = m.get("CauseMetadata", {}) or {}
            start = cause.get("StartLine")
            end = cause.get("EndLine")
            findings.append({
                "kind": "code",
                "tool": "Trivy (misconfig)",
                "rule_id": m.get("ID", ""),
                "rule_name": m.get("Title", ""),
                "severity": (m.get("Severity") or "MEDIUM").upper(),
                "message": (m.get("Message") or m.get("Description", "")).strip(),
                "file": target,
                "start_line": start,
                "end_line": end,
                "snippet": read_snippet(root, target, start, end),
                "language": language_of(target),
                "guidance": m.get("Resolution", ""),
                "help_uri": m.get("PrimaryURL", ""),
                "tags": [],
            })

        for s in result.get("Secrets", []) or []:
            findings.append({
                "kind": "code",
                "tool": "Trivy (secret)",
                "rule_id": s.get("RuleID", ""),
                "rule_name": s.get("Title", ""),
                "severity": (s.get("Severity") or "CRITICAL").upper(),
                "message": f"Segredo detectado: {s.get('Title', '')}",
                "file": target,
                "start_line": s.get("StartLine"),
                "end_line": s.get("EndLine"),
                "snippet": "[conteúdo omitido — segredo]",
                "language": language_of(target),
                "guidance": "Revogue a credencial na origem, remova do código e do histórico, e migre para variável de ambiente ou cofre.",
                "tags": ["secret"],
                "help_uri": "",
            })

    return findings


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------

def dedupe(findings: list[dict]) -> list[dict]:
    seen, out = set(), []
    for f in findings:
        key = (f.get("tool"), f.get("rule_id"), f.get("file"),
               f.get("start_line"), f.get("package"))
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def render_markdown(findings: list[dict], meta: dict) -> str:
    code = [f for f in findings if f["kind"] == "code"]
    deps = [f for f in findings if f["kind"] == "dependency"]

    counts = defaultdict(int)
    for f in findings:
        counts[f["severity"]] += 1

    L: list[str] = []
    L.append("# Relatório de Segurança — SIGNAL")
    L.append("")
    L.append(f"- **Commit:** `{meta['sha']}`")
    L.append(f"- **Branch:** `{meta['ref']}`")
    L.append(f"- **Gerado em:** {meta['timestamp']}")
    L.append(f"- **Total:** {len(findings)} achado(s) — "
             + ", ".join(f"{s}: {counts[s]}" for s in SEV_ORDER if counts[s]))
    L.append("")
    L.append("> Este relatório é informativo. Nenhum gate de CI foi bloqueado.")
    L.append("")

    # Instrução embutida: o arquivo é auto-suficiente como prompt
    L.append("## Instruções para correção assistida")
    L.append("")
    L.append("Cada achado abaixo traz caminho relativo, linha e o trecho real do código.")
    L.append("Ao corrigir:")
    L.append("")
    L.append("1. Trate primeiro CRITICAL e HIGH na seção *Achados em código*.")
    L.append("2. Abra o arquivo indicado e vá à linha marcada com `>`.")
    L.append("3. Confirme que o achado é real antes de alterar — SAST tem falso positivo. ")
    L.append("   Se for falso positivo, registre a supressão com justificativa em vez de silenciar a regra globalmente.")
    L.append("4. Para cada correção, escreva ou ajuste um teste que falharia sem ela.")
    L.append("5. Dependências: aplique a menor versão corrigida listada, e rode a suíte antes de commitar.")
    L.append("")

    # ---- Código ----
    L.append(f"## Achados em código ({len(code)})")
    L.append("")
    if not code:
        L.append("_Nenhum achado._")
        L.append("")
    else:
        by_sev = defaultdict(list)
        for f in code:
            by_sev[f["severity"]].append(f)

        for sev in SEV_ORDER:
            group = by_sev.get(sev)
            if not group:
                continue
            group.sort(key=lambda x: (x.get("file") or "", x.get("start_line") or 0))
            L.append(f"### {SEV_EMOJI[sev]} {sev} ({len(group)})")
            L.append("")
            for i, f in enumerate(group, 1):
                loc = f.get("file") or "(sem arquivo)"
                if f.get("start_line"):
                    loc += f":{f['start_line']}"
                L.append(f"#### {i}. `{loc}`")
                L.append("")
                L.append(f"- **Ferramenta:** {f['tool']}")
                L.append(f"- **Regra:** `{f.get('rule_id') or 'n/d'}`"
                         + (f" — {f['rule_name']}" if f.get("rule_name") else ""))
                if f.get("tags"):
                    L.append(f"- **Tags:** {', '.join(f['tags'])}")
                if f.get("help_uri"):
                    L.append(f"- **Referência:** {f['help_uri']}")
                L.append("")
                if f.get("message"):
                    L.append(f"**Problema:** {f['message']}")
                    L.append("")
                if f.get("snippet"):
                    L.append(f"```{f.get('language', 'text')}")
                    L.append(f["snippet"])
                    L.append("```")
                    L.append("")
                if f.get("guidance"):
                    L.append(f"**Orientação da regra:** {f['guidance']}")
                    L.append("")
                L.append("---")
                L.append("")

    # ---- Dependências ----
    L.append(f"## Achados em dependências ({len(deps)})")
    L.append("")
    if not deps:
        L.append("_Nenhum achado._")
        L.append("")
    else:
        by_pkg = defaultdict(list)
        for f in deps:
            by_pkg[(f.get("package", "?"), f.get("installed_version", "?"))].append(f)

        L.append("| Pacote | Instalada | Corrigir para | Severidade | IDs | Manifesto |")
        L.append("|---|---|---|---|---|---|")
        for (pkg, ver), group in sorted(by_pkg.items()):
            worst = min(group, key=lambda x: SEV_ORDER.index(x["severity"])
                        if x["severity"] in SEV_ORDER else 99)["severity"]
            fixes = sorted({v for f in group for v in f.get("fixed_versions", [])})
            ids = ", ".join(sorted({f.get("rule_id", "") for f in group})[:4])
            manifest = group[0].get("file", "")
            L.append(f"| `{pkg}` | {ver} | {', '.join(fixes) if fixes else '_sem correção_'} "
                     f"| {worst} | {ids} | `{manifest}` |")
        L.append("")

    return "\n".join(L)


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports", default="reports", help="diretório com os arquivos de scan")
    ap.add_argument("--root", default=".", help="raiz do repositório")
    ap.add_argument("--out", default=".", help="diretório de saída")
    args = ap.parse_args()

    reports_dir = Path(args.reports)
    root = Path(args.root)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not reports_dir.is_dir():
        # Sem reports/ (repo sem achados / scanners não aplicáveis) NÃO é erro: segue com
        # 0 achados e gera findings.json vazio. A stack roda em qualquer tipo de repo.
        print(f"reports/ ausente ({reports_dir}) — seguindo com 0 achados.", file=sys.stderr)
        reports_dir.mkdir(parents=True, exist_ok=True)

    findings: list[dict] = []
    ran: set[str] = set()   # ferramentas que rodaram (alimenta `health` → auto-fecha)
    for path in sorted(reports_dir.rglob("*")):
        if not path.is_file() or path.suffix not in (".sarif", ".json"):
            continue
        name = path.name.lower()
        print(f"  · lendo {path.name}")
        if path.suffix == ".sarif":
            findings += parse_sarif(path, root)
            ran |= _sarif_tools(path)   # nomes dos drivers, mesmo com 0 achados
        elif "osv" in name:
            findings += parse_osv(path, root)
            ran.add("OSV-Scanner")
        elif "trivy" in name or "grype" in name:
            findings += parse_trivy(path, root)
            # o report do Trivy cobre os 3 sub-scanners; marca todos como "rodou"
            ran.update(("Trivy", "Trivy (misconfig)", "Trivy (secret)"))

    findings = dedupe(findings)
    findings.sort(key=lambda f: (
        SEV_ORDER.index(f["severity"]) if f["severity"] in SEV_ORDER else 99,
        f.get("file") or "",
        f.get("start_line") or 0,
    ))

    meta = {
        "sha": os.getenv("GITHUB_SHA", "local")[:12],
        "ref": os.getenv("GITHUB_REF_NAME", "local"),
        "run_url": (f"{os.getenv('GITHUB_SERVER_URL', '')}/{os.getenv('GITHUB_REPOSITORY', '')}"
                    f"/actions/runs/{os.getenv('GITHUB_RUN_ID', '')}"),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }

    # `health`: ferramentas que comprovadamente rodaram (report presente), pelos MESMOS
    # nomes usados no campo `tool` dos findings. O ingest do Signal só fecha um achado
    # ausente se a ferramenta que o encontrou está aqui — sem isto, nada auto-resolve.
    ran |= {f["tool"] for f in findings if f.get("tool")}
    health = {t: {"ran": True} for t in sorted(ran)}

    (out_dir / "findings.json").write_text(
        json.dumps({"meta": meta, "health": health, "findings": findings},
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (out_dir / "FINDINGS.md").write_text(
        render_markdown(findings, meta), encoding="utf-8"
    )

    counts = defaultdict(int)
    for f in findings:
        counts[f["severity"]] += 1
    print(f"\n{len(findings)} achado(s): "
          + ", ".join(f"{s}={counts[s]}" for s in SEV_ORDER if counts[s]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
