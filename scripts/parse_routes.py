#!/usr/bin/env python3
"""
scripts/parse_routes.py — SIGNAL / MOVSEC  (AEX CP6/CP7/CP8: mapa de rotas)

Varre o código do repositório e extrai as ROTAS HTTP declaradas num artefato
ESTRUTURAL, cobrindo três stacks:

  • Python  — FastAPI / APIRouter / Flask            (via `ast`, alta fidelidade)
  • Node    — Express / Fastify / Koa-router         (via regex + balanceamento)
  • NestJS  — @Controller / @Get / @Post (decorator)  (via regex + balanceamento)
  • Java    — Spring MVC (@GetMapping, @RequestMapping) (via regex + balanceamento)

  routes.json   {"routes": [{metodo, caminho, arquivo, handler, linha_inicio,
                 linha_fim, exige_auth, origem, confianca}, ...]}

NÃO leva trecho de código — só a estrutura (a allowlist do ingest do Signal
rejeita qualquer campo de código numa rota). O Signal casa cada achado SAST
(arquivo:linha) ao handler que o CONTÉM (intervalo de linha) e, cruzando com o
que o DAST confirmou vivo, decide o ALCANCE real do achado (épico AEX).

Regra de ouro do AEX v1 — "só sobe, nunca rebaixa por ausência": quando não dá
para AFIRMAR que a rota exige autenticação, `exige_auth` fica `None`
(indeterminado). Nunca assumimos `False` (público) por falta de evidência —
quem confirma "público e vivo" é o DAST, não este parser estático.

Confiança por stack: Python `ast` = "alta"; regex de JS/Java = "media" (o
casamento por intervalo é mais aproximado). Sem dependências externas. Python 3.10+.

Uso:
  python scripts/parse_routes.py --root . --out .
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path

# ---- comum -----------------------------------------------------------------

_PY_EXT = {".py"}
_JS_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
_JAVA_EXT = {".java"}
_ALL_EXT = _PY_EXT | _JS_EXT | _JAVA_EXT

# Diretórios que não são código de aplicação servido (vendored, build, testes).
_SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "env", "site-packages",
              "__pycache__", "dist", "build", "target", "out", ".gradle", ".idea",
              ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
              "migrations", "tests", "test", "testing", "__tests__", "examples"}

# Pistas de que o handler exige autenticação (heurística CONSERVADORA: só liga o
# True, nunca o False). Vale para os três parsers.
_AUTH_HINTS = ("auth", "user", "current", "token", "login", "require", "logged",
               "security", "principal", "identity", "permission", "scope", "jwt",
               "ensure", "protect", "guard", "verify", "session")


def _iter_files(root: Path):
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in _SKIP_DIRS and not d.startswith(".")]
        for fn in fns:
            if os.path.splitext(fn)[1] in _ALL_EXT:
                yield Path(dp) / fn


def _rel(p: Path, root: Path) -> str:
    try:
        return p.relative_to(root).as_posix()
    except ValueError:
        return p.as_posix()


def _route(metodo, caminho, arquivo, handler, lo, hi, auth, confianca) -> dict:
    return {"metodo": metodo, "caminho": caminho, "arquivo": arquivo,
            "handler": handler or "", "linha_inicio": lo, "linha_fim": hi,
            "exige_auth": auth, "origem": "parser", "confianca": confianca}


def _line_at(src: str, pos: int) -> int:
    return src.count("\n", 0, pos) + 1


def _match_delim(src: str, open_pos: int) -> int:
    """Dado o índice de um '(' ou '{', devolve o índice do fechamento casado (ou -1).
    Heurística: ignora strings/comentários — suficiente para achar o fim do bloco."""
    if open_pos < 0 or open_pos >= len(src):
        return -1
    opener = src[open_pos]
    closer = {"(": ")", "{": "}"}.get(opener)
    if not closer:
        return -1
    depth = 0
    for i in range(open_pos, len(src)):
        ch = src[i]
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return i
    return -1


# ---- Python (ast) — CP6 ----------------------------------------------------

_HTTP = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
_ROUTE_ATTRS = _HTTP | {"route", "websocket", "api_route", "add_route"}
_AUTH_CALLS = {"Security", "Auth", "Authenticated", "RequireAuth", "LoginRequired"}


def _str_const(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _methods_from_route_kw(call: ast.Call) -> list[str]:
    for kw in call.keywords or []:
        if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple, ast.Set)):
            got = [m.upper() for m in (_str_const(e) for e in kw.value.elts) if m]
            if got:
                return got
    return ["GET"]


def _decorator_routes(dec) -> list[tuple[str, str]]:
    if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
        return []
    attr = dec.func.attr.lower()
    if attr not in _ROUTE_ATTRS:
        return []
    caminho = _str_const(dec.args[0]) if dec.args else None
    if caminho is None:
        for kw in dec.keywords or []:
            if kw.arg in ("path", "rule"):
                caminho = _str_const(kw.value)
    if not caminho:
        return []
    if attr == "websocket":
        return [("WS", caminho)]
    if attr in ("route", "api_route", "add_route"):
        return [(m, caminho) for m in _methods_from_route_kw(dec)]
    return [(attr.upper(), caminho)]


def _call_name(node) -> str:
    f = getattr(node, "func", node)
    return getattr(f, "id", "") or getattr(f, "attr", "")


def _exige_auth_py(fn) -> bool | None:
    for dec in fn.decorator_list:
        nome = _call_name(dec).lower()
        if nome and any(h in nome for h in _AUTH_HINTS):
            return True
    for d in list(fn.args.defaults) + list(fn.args.kw_defaults or []):
        if not isinstance(d, ast.Call):
            continue
        chamada = _call_name(d)
        if chamada in _AUTH_CALLS:
            return True
        if chamada in ("Depends", "Require", "Inject"):
            alvo = _call_name(d.args[0]) if d.args else ""
            if alvo and any(h in alvo.lower() for h in _AUTH_HINTS):
                return True
    return None


def _routes_py(src: str, rel: str) -> list[dict]:
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return []
    out: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        pares: list[tuple[str, str]] = []
        for dec in node.decorator_list:
            pares += _decorator_routes(dec)
        if not pares:
            continue
        auth = _exige_auth_py(node)
        lo = min([node.lineno] + [d.lineno for d in node.decorator_list])
        hi = getattr(node, "end_lineno", None) or node.lineno
        for metodo, caminho in pares:
            out.append(_route(metodo, caminho, rel, node.name, lo, hi, auth, "alta"))
    return out


# ---- Node / Express (regex) — CP7 ------------------------------------------

# obj.verb('/path', ...)  — obj = app|router|api|route|<qualquer>Router|r
_JS_ROUTE = re.compile(
    r"""(?P<obj>[A-Za-z_$][\w$]*)\s*\.\s*
        (?P<verb>get|post|put|patch|delete|options|head|all)\s*\(\s*
        (?P<q>['"`])(?P<path>/[^'"`]*)(?P=q)""",
    re.VERBOSE,
)
# 2º argumento como referência nomeada: .get('/x', nomeDoHandler)
_JS_HANDLER = re.compile(r"""^\s*,\s*(?P<name>[A-Za-z_$][\w$.]*)\s*[),]""")
_JS_FUNC = re.compile(r"function\s+([A-Za-z_$][\w$]*)")
# Middlewares de auth por nome EXATO (evita falso-positivo em handler tipo getUserProfile,
# que contém "user"): marcar auth=True à toa REBAIXARIA uma rota pública -> só nomes claros.
_JS_AUTH_EXACT = {
    "auth", "authenticate", "authenticated", "isauthenticated", "requireauth",
    "requireauthentication", "requirelogin", "requireuser", "requiresauth",
    "ensureauth", "ensureauthenticated", "ensureloggedin", "isloggedin",
    "checkauth", "verifytoken", "verifyjwt", "jwtauth", "authmiddleware",
    "authguard", "withauth", "passport", "authorize", "authorization",
    "protect", "protectroute", "isadmin", "adminonly",
}


def _exige_auth_js(trecho: str) -> bool | None:
    for tok in re.findall(r"[A-Za-z_$][\w$]*", trecho):
        if tok.lower() in _JS_AUTH_EXACT:
            return True
    return None


def _routes_js(src: str, rel: str) -> list[dict]:
    out: list[dict] = []
    for m in _JS_ROUTE.finditer(src):
        verb = m.group("verb").lower()
        metodo = "ANY" if verb == "all" else verb.upper()
        caminho = m.group("path")
        lo = _line_at(src, m.start())
        # fim do call: casa os parênteses a partir do '(' da chamada
        open_paren = src.find("(", m.start())
        close = _match_delim(src, open_paren) if open_paren >= 0 else -1
        hi = _line_at(src, close) if close >= 0 else lo
        # handler: prefere `function NOME(...)`; senão a 1ª referência nomeada após o path
        resto = src[m.end():(close + 1) if close >= 0 else m.end() + 1]
        fnm = _JS_FUNC.search(resto)
        if fnm:
            handler = fnm.group(1)
        else:
            hm = _JS_HANDLER.match(resto)
            handler = hm.group("name") if hm else ""
        # auth: examina o cabeçalho da chamada (do path até o 1º '{' ou fim de linha)
        cabeca = src[m.end():m.end() + 240].split("{", 1)[0].split("\n", 1)[0]
        out.append(_route(metodo, caminho, rel, handler, lo, hi,
                          _exige_auth_js(cabeca), "media"))
    return out


# ---- Node / NestJS (regex, decorator de classe) — CP-Nest ------------------

# @Controller('prefix') | @Controller("prefix") | @Controller({ path: 'prefix' }) | @Controller()
_NEST_CTRL = re.compile(
    r"""@Controller\(\s*(?:
        (['"`])(?P<p>[^'"`]*)\1                       # @Controller('x')
        |\{[^}]*?\bpath\s*:\s*(['"`])(?P<p2>[^'"`]*)\3  # @Controller({ path: 'x' })
    )?""",
    re.VERBOSE | re.DOTALL,
)
# @Get() | @Get('id') | @Post('/x') | @All() ...
_NEST_MAP = re.compile(
    r"""@(?P<kind>Get|Post|Put|Patch|Delete|Options|Head|All)\(\s*
        (?:(['"`])(?P<path>[^'"`]*)\2)?\s*\)""",
    re.VERBOSE,
)
# nome do método TS após o(s) decorator(es): pula linhas que começam com @, pega `nome(`
_NEST_METHODNAME = re.compile(r"(?:async\s+)?(?P<name>[A-Za-z_$][\w$]*)\s*\(")
# guards do Nest (@UseGuards(...)) — auth só quando o nome do guard é claramente de auth
_NEST_USEGUARDS = re.compile(r"@UseGuards\(\s*(?P<args>[^)]*)\)")
_NEST_AUTH_HINTS = ("auth", "jwt", "session", "login", "role", "permission",
                    "ability", "policy", "oauth", "identity")


def _nest_path(prefix: str, path: str) -> str:
    partes = [p.strip("/") for p in (prefix or "", path or "") if p and p.strip("/")]
    return "/" + "/".join(partes) if partes else "/"


def _nest_guard_auth(trecho: str) -> bool:
    for g in _NEST_USEGUARDS.findall(trecho):
        low = g.lower()
        if any(h in low for h in _NEST_AUTH_HINTS):
            return True
    return False


def _routes_nest(src: str, rel: str) -> list[dict]:
    cm = _NEST_CTRL.search(src)
    prefix = (cm.group("p") or cm.group("p2") or "") if cm else ""
    cls = _JAVA_CLASS.search(src)          # 'class X' (reusa o regex de classe)
    cls_pos = cls.start() if cls else -1
    # @UseGuards no nível da classe (antes da declaração) protege TODOS os métodos
    classe_auth = _nest_guard_auth(src[:cls_pos]) if cls_pos >= 0 else False
    out: list[dict] = []
    for m in _NEST_MAP.finditer(src):
        kind = m.group("kind")
        metodo = "ANY" if kind == "All" else kind.upper()
        caminho = _nest_path(prefix, m.group("path") or "")
        lo = _line_at(src, m.start())
        # nome do método: no texto após o decorator, ignorando outras linhas de @decorator
        depois = src[m.end():m.end() + 400]
        handler = ""
        for linha in depois.splitlines():
            t = linha.strip()
            if not t or t.startswith("@"):
                continue
            hm = _NEST_METHODNAME.search(t)
            if hm and hm.group("name") not in ("if", "for", "while", "switch", "return"):
                handler = hm.group("name")
            break
        brace = src.find("{", m.end())
        close = _match_delim(src, brace) if brace >= 0 else -1
        hi = _line_at(src, close) if close >= 0 else lo
        # auth: guard do método (janela do membro) OU guard de classe
        prev = max(src.rfind("}", 0, m.start()), src.rfind(";", 0, m.start()))
        janela = src[(prev + 1) if prev >= 0 else cls_pos:(brace if brace >= 0 else m.end() + 60)]
        auth = True if (classe_auth or _nest_guard_auth(janela)) else None
        out.append(_route(metodo, caminho, rel, handler, lo, hi, auth, "media"))
    return out


# ---- Java / Spring MVC (regex) — CP8 ---------------------------------------

_JAVA_CLASS = re.compile(r"\b(?:class|interface)\s+[A-Za-z_$][\w$]*")
_JAVA_REQMAP = re.compile(r"@RequestMapping\s*\(\s*(?P<body>[^)]*)\)", re.DOTALL)
_JAVA_MAPPING = re.compile(
    r"@(?P<kind>Get|Post|Put|Patch|Delete|Request)Mapping\b\s*(?:\((?P<body>[^)]*)\))?",
    re.DOTALL,
)
_JAVA_PATH = re.compile(r"""(?:value|path)\s*=\s*(['"])(?P<p>[^'"]*)\1"""
                        r"""|^\s*(['"])(?P<p2>[^'"]*)\3""")
_JAVA_REQ_METHOD = re.compile(r"RequestMethod\.(?P<m>GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)")
_JAVA_METHODNAME = re.compile(
    r"(?:public|protected|private|static|final|\s)*"
    r"[A-Za-z_$][\w$<>,.\[\]\s]*?\s+(?P<name>[A-Za-z_$][\w$]*)\s*\(")
_JAVA_AUTH = ("PreAuthorize", "PostAuthorize", "Secured", "RolesAllowed",
              "Authenticated", "DenyAll")
_KIND_METHOD = {"Get": "GET", "Post": "POST", "Put": "PUT",
                "Patch": "PATCH", "Delete": "DELETE"}


def _java_path(body: str) -> str | None:
    if not body:
        return None
    m = _JAVA_PATH.search(body.strip())
    if not m:
        return None
    return m.group("p") or m.group("p2")


def _join(prefix: str, path: str) -> str:
    if not prefix:
        return path or "/"
    if not path:
        return prefix
    return prefix.rstrip("/") + "/" + path.lstrip("/")


def _routes_java(src: str, rel: str) -> list[dict]:
    cls = _JAVA_CLASS.search(src)
    cls_pos = cls.start() if cls else -1
    # prefixo de classe = último @RequestMapping ANTES da declaração da classe
    prefix = ""
    if cls_pos >= 0:
        for m in _JAVA_REQMAP.finditer(src):
            if m.start() < cls_pos:
                prefix = _java_path(m.group("body")) or prefix
    out: list[dict] = []
    for m in _JAVA_MAPPING.finditer(src):
        # anotação antes da classe = nível de classe (prefixo), não é uma rota própria
        if cls_pos >= 0 and m.start() < cls_pos:
            continue
        kind = m.group("kind")
        body = m.group("body") or ""
        path = _java_path(body)
        metodos = (_JAVA_REQ_METHOD.findall(body) or ["GET"]) if kind == "Request" \
            else [_KIND_METHOD[kind]]
        caminho = _join(prefix, path or "")
        lo = _line_at(src, m.start())
        # nome do método Java + fim do corpo (casa as chaves a partir do 1º '{')
        nm = _JAVA_METHODNAME.search(src[m.end():m.end() + 400])
        handler = nm.group("name") if nm else ""
        if handler in ("if", "for", "while", "switch", "return", "new", "catch"):
            handler = ""
        brace = src.find("{", m.end())
        close = _match_delim(src, brace) if brace >= 0 else -1
        hi = _line_at(src, close) if close >= 0 else lo
        # auth: só as anotações DESTE método — do fim do membro anterior ('}' ou ';') até
        # a abertura do corpo. Assim o @PreAuthorize do método anterior não vaza pra cá.
        prev = max(src.rfind("}", 0, m.start()), src.rfind(";", 0, m.start()))
        janela = src[(prev + 1) if prev >= 0 else 0:(brace if brace >= 0 else m.end() + 60)]
        auth = True if any(a in janela for a in _JAVA_AUTH) else None
        for metodo in metodos:
            out.append(_route(metodo, caminho, rel, handler, lo, hi, auth, "media"))
    return out


# ---- orquestração ----------------------------------------------------------

def _routes_in_file(path: Path, root: Path) -> list[dict]:
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    ext = path.suffix
    rel = _rel(path, root)
    if ext in _PY_EXT:
        return _routes_py(src, rel)
    if ext in _JS_EXT:
        # NestJS usa decorator de classe (@Controller/@Get) — sintaxe diferente do Express
        # (obj.get('/x')). Decide pelo @Controller para não misturar os dois parsers.
        return _routes_nest(src, rel) if "@Controller" in src else _routes_js(src, rel)
    if ext in _JAVA_EXT:
        return _routes_java(src, rel)
    return []


def mapear(root: Path) -> list[dict]:
    """Todas as rotas do repositório, deduplicadas e ordenadas por arquivo:linha."""
    rotas: list[dict] = []
    vistos: set = set()
    for p in sorted(_iter_files(root)):
        for r in _routes_in_file(p, root):
            k = (r["metodo"], r["caminho"], r["arquivo"], r["linha_inicio"])
            if k in vistos:
                continue
            vistos.add(k)
            rotas.append(r)
    rotas.sort(key=lambda r: (r["arquivo"], r["linha_inicio"], r["metodo"]))
    return rotas


def main() -> int:
    ap = argparse.ArgumentParser(description="Mapeia rotas HTTP (Python/Node/Java) -> routes.json (AEX).")
    ap.add_argument("--root", default=".", help="raiz do repositório")
    ap.add_argument("--out", default=".", help="diretório de saída")
    args = ap.parse_args()

    root = Path(args.root)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not root.is_dir():
        print(f"[parse-routes] raiz inexistente ({root}) — 0 rotas.", file=sys.stderr)
        rotas: list[dict] = []
    else:
        rotas = mapear(root)

    (out_dir / "routes.json").write_text(
        json.dumps({"routes": rotas}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[parse-routes] {len(rotas)} rota(s) mapeada(s) -> routes.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
