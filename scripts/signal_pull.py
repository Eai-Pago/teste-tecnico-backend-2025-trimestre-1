#!/usr/bin/env python3
"""Adaptador Signal → CI (veredito de FP).

Fecha o loop do AppSec SEM tocar no repositório do cliente: baixa do Signal os
fingerprints de FP SUPRIMIDOS (aprovados/comprovados) do engajamento e remove os
achados correspondentes do `findings.json` local. A decisão de falso-positivo mora
no Signal (fp_score/IA + supressão comprovada); o CI só APLICA. Nenhuma supressão
é escrita no repo — melhorias no Signal valem na próxima execução, retroativas.

Casa pelo MESMO fingerprint que o signal_push.py envia (importado daqui p/ não
divergir). Autônomo: só stdlib. Modo observação: sem URL/token, no-op; falha de
rede NÃO quebra o build (sai 0 com aviso).

Uso no CI (após normalize + push):
    python scripts/signal_pull.py \
        --findings findings.json \
        --url "$SIGNAL_URL" --token "$SIGNAL_TOKEN"
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

# Reusa a fórmula de fingerprint do push (mesma identidade estável), sem duplicar.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from signal_push import _fingerprint   # noqa: E402


def fetch_suppressed(url: str, token: str, timeout: int = 20) -> set:
    """GET /api/appsec/suppressions (Bearer). Devolve o set de fingerprints suprimidos."""
    req = urllib.request.Request(
        url.rstrip("/") + "/api/appsec/suppressions", method="GET",
        headers={"Authorization": f"Bearer {token}",
                 "User-Agent": "signal-pull/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec B310 - URL do operador (SIGNAL_URL)
        data = json.loads(r.read().decode("utf-8", "replace"))
    return set(data.get("fingerprints") or [])


def main() -> int:
    ap = argparse.ArgumentParser(description="Aplica as supressões de FP do Signal ao findings.json.")
    ap.add_argument("--findings", default="findings.json")
    ap.add_argument("--url", default=os.getenv("SIGNAL_URL", ""))
    ap.add_argument("--token", default=os.getenv("SIGNAL_TOKEN", ""))
    args = ap.parse_args()

    # Modo observação: sem URL/token, não faz nada e NÃO quebra o build.
    if not args.url or not args.token:
        print("[signal-pull] SIGNAL_URL/SIGNAL_TOKEN ausentes — filtro de FP ignorado.")
        return 0
    try:
        data = json.loads(open(args.findings, encoding="utf-8").read())
    except (OSError, json.JSONDecodeError) as e:
        print(f"[signal-pull] não consegui ler {args.findings}: {e}")
        return 0

    try:
        suppressed = fetch_suppressed(args.url, args.token)
    except urllib.error.HTTPError as e:
        print(f"[signal-pull] Signal recusou (HTTP {e.code}). Nada filtrado.")
        return 0
    except Exception as e:  # rede/DNS/timeout
        print(f"[signal-pull] não consegui contatar o Signal ({type(e).__name__}). Nada filtrado.")
        return 0

    if not suppressed:
        print("[signal-pull] nenhum FP suprimido no Signal — relatório inalterado.")
        return 0

    findings = data.get("findings") or []
    kept, dropped = [], 0
    for f in findings:
        if _fingerprint(f) in suppressed:
            dropped += 1
        else:
            kept.append(f)
    if dropped:
        data["findings"] = kept
        # Registra no meta o que foi filtrado (auditável, sem esconder o número).
        meta = data.setdefault("meta", {})
        meta["fp_suppressed_by_signal"] = meta.get("fp_suppressed_by_signal", 0) + dropped
        with open(args.findings, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
    print(f"[signal-pull] {dropped} achado(s) suprimido(s) pelo Signal (FP) — "
          f"{len(kept)} restante(s) no relatório.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
