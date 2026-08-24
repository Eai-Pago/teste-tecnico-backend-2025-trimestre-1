#!/usr/bin/env python3
"""Adaptador CI → Signal AppSec.

Lê o `findings.json` produzido pela stack DevSecOps (normalize_findings.py),
converte cada achado para o schema `appsec/v1` e POSTa no ingest do Signal.

O adaptador envia o TRECHO vulnerável (para aparecer no chamado e acelerar a
correção). REGRA DE SEGREDO: achados de categoria `secret` têm o trecho REDIGIDO
aqui, no CI — a credencial crua nunca sai da máquina do cliente.

Autônomo: só stdlib (roda no CI do cliente sem instalar nada). O token é lido do
ambiente/argumento e NUNCA é impresso. Modo observação: uma falha de envio NÃO
quebra o build (sai 0 com aviso).

Uso no CI (após gerar findings.json):
    python scripts/signal_push.py \
        --findings findings.json \
        --url "$SIGNAL_URL" --token "$SIGNAL_TOKEN" \
        --application "$GITHUB_REPOSITORY"
"""
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request

_SEVS = ("critical", "high", "medium", "low", "info")
_CWE_RE = re.compile(r"cwe[-_/ ]?(\d+)", re.I)


def category_of(f: dict) -> str:
    """Mapeia o achado da stack para o tipo do Signal (sast|sca|iac|secret)."""
    tool = (f.get("tool") or "").lower()
    tags = [str(t).lower() for t in (f.get("tags") or [])]
    if "secret" in tags or "secret" in tool or "gitleaks" in tool:
        return "secret"
    if ("misconfig" in tool or "hadolint" in tool or "checkov" in tool
            or "dockerfile" in tool or "iac" in tags or "terraform" in tags):
        return "iac"
    if f.get("kind") == "dependency":
        return "sca"
    return "sast"


def cwe_of(f: dict) -> str:
    """Extrai CWE das tags/regra (ex.: 'external/cwe/cwe-89' → 'CWE-89')."""
    for t in list(f.get("tags") or []) + [f.get("rule_id") or "", f.get("rule_name") or ""]:
        m = _CWE_RE.search(str(t))
        if m:
            return f"CWE-{m.group(1)}"
    return ""


def _fingerprint(f: dict) -> str:
    """Identidade ESTÁVEL do achado — independe de reordenação/rescan E de deslocamento de
    LINHA (a linha varia quando código não relacionado é adicionado acima, sem mexer na vuln).
    - SCA (dependência): pacote + versão instalada (não tem código/linha) — inalterado.
    - SAST/IaC/segredo (código): rule + file + HASH DO TRECHO vulnerável (não a start_line).
      Assim a MESMA vuln sobrevive a mudanças de linha; código diferente = achado diferente.
      Fallback pra start_line só quando não há trecho (raro)."""
    pkg = f.get("package") or ""
    if pkg:                                     # SCA: identidade por dependência (estável)
        basis = "|".join(str(x) for x in (
            f.get("tool") or "", f.get("rule_id") or "", f.get("file") or "",
            f.get("start_line") or "", pkg, f.get("installed_version") or ""))
    else:                                       # código: rule + file + hash do trecho
        snip = " ".join((f.get("snippet") or "").split())   # normaliza espaços/indentação
        code_id = (hashlib.sha256(snip.encode("utf-8")).hexdigest()[:16] if snip
                   else f"L{f.get('start_line') or ''}")
        basis = "|".join((f.get("tool") or "", f.get("rule_id") or "",
                          f.get("file") or "", code_id))
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]


_SNIPPET_MAX = 2000     # teto de tamanho do trecho enviado


def _sca_facts(f: dict) -> str:
    """Fatos da dependência (não é código): pacote, versão instalada, versões
    corrigidas e referência. Alimentam a análise do Haiku (atualizar → similar →
    workaround/escalar) e a coluna esquerda do quadro no chamado."""
    linhas = []
    if f.get("package"):
        linhas.append(f"Pacote: {f['package']}")
    if f.get("installed_version"):
        linhas.append(f"Versão instalada: {f['installed_version']}")
    fixed = [str(x) for x in (f.get("fixed_versions") or []) if str(x).strip()]
    linhas.append("Versões corrigidas: " + (", ".join(fixed) if fixed else "nenhuma publicada"))
    if f.get("help_uri"):
        linhas.append(f"Referência: {f['help_uri']}")
    return "\n".join(linhas)


def _snippet_for(f: dict, category: str) -> str:
    """Conteúdo do achado para o chamado. SEGREDO é REDIGIDO AQUI (no CI) — a
    credencial crua nunca sai da máquina do cliente. DEPENDÊNCIA (sca) não tem
    código: manda os FATOS da dependência (pacote/versões/referência)."""
    if category == "secret":
        return "[segredo redigido no CI — rotacione a credencial]"
    if category == "sca":
        return _sca_facts(f)[:_SNIPPET_MAX]
    s = f.get("snippet") or ""
    return s[:_SNIPPET_MAX]


def to_signal_finding(f: dict) -> dict:
    """Converte UM achado da stack para o schema appsec/v1, COM o trecho vulnerável
    (segredo redigido). O trecho vai pro chamado, pra o dev corrigir mais rápido."""
    sev = (f.get("severity") or "info").lower()
    if sev not in _SEVS:
        sev = "info"
    rule = f.get("rule_id") or f.get("rule_name") or ""
    title = (f.get("rule_name") or f.get("message") or rule or "").strip()[:200]
    cat = category_of(f)
    return {
        "fingerprint": _fingerprint(f),
        "tool": f.get("tool") or "",          # cru; o Signal mascara na exibição
        "rule": rule,
        "category": cat,
        "severity": sev,
        "file": f.get("file") or "",
        "line": int(f.get("start_line") or 0),
        "cwe": cwe_of(f),
        "title": title,
        "snippet": _snippet_for(f, cat),      # trecho (segredo já redigido)
    }


def build_payload(data: dict, application: str, owner: str, repo: str,
                  host: str = "github.com") -> dict:
    meta = data.get("meta", {}) or {}
    return {
        "schema": "appsec/v1",
        "application": application,
        "commit": meta.get("sha", "") or os.getenv("GITHUB_SHA", "")[:12],
        "branch": meta.get("ref", "") or os.getenv("GITHUB_REF_NAME", ""),
        # Evento do CI. Scan de PR é PARCIAL (incremental): NÃO reconcilia status de AutoFix
        # (achado ausente do diff ≠ corrigido). Só push/schedule (estado da main) reconciliam.
        "evento": os.getenv("GITHUB_EVENT_NAME", ""),
        "run_id": os.getenv("GITHUB_RUN_ID", ""),
        # Versão da stack instalada neste repo — o Signal compara com a versão canônica
        # (stack/VERSION) para saber quem está desatualizado (auto-update).
        "stack_version": os.getenv("SIGNAL_STACK_VERSION", ""),
        "repo": {"owner": owner, "name": repo, "host": host},
        # `health` = ferramentas que rodaram (normalize_findings.py). É o que habilita o
        # auto-fechar do ingest: sem ele `ran_tools` fica vazio e nada resolve sozinho.
        "health": data.get("health") or {},
        "findings": [to_signal_finding(f) for f in (data.get("findings") or [])],
    }


def post(url: str, token: str, payload: dict, timeout: int = 20) -> tuple:
    """POST autenticado no ingest. Devolve (status, corpo). Levanta em erro de rede."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url.rstrip("/") + "/api/appsec/ingest", data=body, method="POST",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json",
                 "User-Agent": "signal-push/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec B310 - URL do operador (SIGNAL_URL)
        return r.status, r.read().decode("utf-8", "replace")


def main() -> int:
    ap = argparse.ArgumentParser(description="Envia findings.json ao Signal AppSec (appsec/v1).")
    ap.add_argument("--findings", default="findings.json")
    ap.add_argument("--url", default=os.getenv("SIGNAL_URL", ""))
    ap.add_argument("--token", default=os.getenv("SIGNAL_TOKEN", ""))
    ap.add_argument("--application", default=os.getenv("GITHUB_REPOSITORY", ""))
    ap.add_argument("--owner", default=(os.getenv("GITHUB_REPOSITORY", "/").split("/")[0]))
    ap.add_argument("--repo", default=(os.getenv("GITHUB_REPOSITORY", "/").split("/")[-1]))
    ap.add_argument("--host", default="github.com")
    args = ap.parse_args()

    # Fallback: fora do CI (sem GITHUB_REPOSITORY), --owner/--repo vêm vazios. Deriva de
    # --application no formato "owner/repo" — sem isso os achados chegam SEM repo e o AutoFix
    # não sabe onde abrir o PR (ignora todos). O ingest tem o mesmo fallback como 2ª rede.
    if (not args.owner or not args.repo) and "/" in (args.application or ""):
        _ow, _nm = args.application.split("/", 1)
        args.owner = args.owner or _ow.strip()
        args.repo = args.repo or _nm.strip()

    # Modo observação: sem URL/token, não faz nada e NÃO quebra o build.
    if not args.url or not args.token:
        print("[signal-push] SIGNAL_URL/SIGNAL_TOKEN ausentes — envio ignorado.")
        return 0
    try:
        data = json.loads(open(args.findings, encoding="utf-8").read())
    except (OSError, json.JSONDecodeError) as e:
        print(f"[signal-push] não consegui ler {args.findings}: {e}")
        return 0

    payload = build_payload(data, args.application or args.repo, args.owner,
                            args.repo, args.host)
    n = len(payload["findings"])
    by_cat = {}
    for f in payload["findings"]:
        by_cat[f["category"]] = by_cat.get(f["category"], 0) + 1
    resumo = ", ".join(f"{k}={v}" for k, v in sorted(by_cat.items())) or "0"
    try:
        status, resp = post(args.url, args.token, payload)
    except urllib.error.HTTPError as e:
        # "não consegui enviar" ≠ "nada encontrado": diz o código, não vaza o token.
        print(f"[signal-push] ingest recusou (HTTP {e.code}). Achados: {n} ({resumo}).")
        return 0
    except Exception as e:  # rede/DNS/timeout
        print(f"[signal-push] não consegui contatar o Signal ({type(e).__name__}). "
              f"Achados: {n} ({resumo}).")
        return 0
    print(f"[signal-push] enviados {n} achado(s) ao Signal [{resumo}] · HTTP {status}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
