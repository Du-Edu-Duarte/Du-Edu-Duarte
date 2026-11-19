#!/usr/bin/env python3
"""Atualiza o README do perfil sozinho.

O que ele faz, a cada execução:
1. Busca os repositórios públicos da conta na API do GitHub.
2. Reescreve a lista "Últimas atualizações" do README (entre os marcadores).
3. Gera assets/langs.svg com as linguagens mais usadas.

Roda pelo GitHub Actions (.github/workflows/atualizar-perfil.yml).
Para testar sem internet: python scripts/update_readme.py --mock dados.json
"""
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

USER = os.environ.get("PROFILE_USER", "Du-Edu-Duarte")
ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
LANGS_SVG = ROOT / "assets" / "langs.svg"
MAX_REPOS = 6
MAX_LANGS = 6
START, END = "<!-- PROJETOS:INICIO -->", "<!-- PROJETOS:FIM -->"
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
CORES = {
    "JavaScript": "#F1E05A", "TypeScript": "#3178C6", "Python": "#4B8BBE",
    "HTML": "#E34C26", "CSS": "#8E6BD8", "Jupyter Notebook": "#DA5B0B",
    "Shell": "#89E051", "Java": "#B07219", "C#": "#178600", "PHP": "#4F5D95",
    "SQL": "#E38C00", "PLpgSQL": "#336790", "Vue": "#41B883", "Dart": "#00B4AB",
}
COR_PADRAO = "#A89A78"


def api(path):
    req = urllib.request.Request("https://api.github.com" + path)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", USER + "-profile-readme")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def load_data():
    """Devolve (repos, linguagens). Com --mock lê de um arquivo JSON."""
    if "--mock" in sys.argv:
        data = json.loads(Path(sys.argv[sys.argv.index("--mock") + 1]).read_text("utf-8"))
        return data["repos"], data["languages"]
    repos = api(f"/users/{USER}/repos?type=owner&sort=pushed&per_page=100")
    repos = [r for r in repos if not r["fork"] and not r["private"]
             and not r.get("archived") and r["name"].lower() != USER.lower()]
    langs = {}
    for r in repos:
        for lang, size in api(f"/repos/{USER}/{r['name']}/languages").items():
            langs[lang] = langs.get(lang, 0) + size
    return repos, langs


def data_br(iso):
    d = dt.datetime.strptime(iso[:10], "%Y-%m-%d")
    return f"{d.day:02d} {MESES[d.month - 1]} {d.year}"


def projects_md(repos):
    repos = sorted(repos, key=lambda r: r["pushed_at"], reverse=True)[:MAX_REPOS]
    if not repos:
        return "_Nenhum repositório público ainda._"
    rows = ["| Projeto | O que é | Linguagem | Atualizado |", "|---|---|---|---|"]
    for r in repos:
        desc = (r.get("description") or "—").replace("|", "\\|").strip()
        if len(desc) > 110:
            desc = desc[:107].rstrip() + "…"
        name = f"[**{r['name']}**]({r['html_url']})"
        if r.get("homepage"):
            name += f" · [demo]({r['homepage']})"
        rows.append(f"| {name} | {desc} | {r.get('language') or '—'} | {data_br(r['pushed_at'])} |")
    return "\n".join(rows)


def langs_svg(langs):
    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: kv[1], reverse=True)[:MAX_LANGS]
    shown = sum(v for _, v in top) or 1
    w, pad, bar_w = 480, 28, 424
    rows = (len(top) + 1) // 2
    h = 118 + rows * 30
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="Linguagens mais usadas">',
        "<style>.t{font:700 17px 'Segoe UI',system-ui,-apple-system,Arial,sans-serif;fill:#E2B454}"
        ".l{font:500 14px 'Segoe UI',system-ui,-apple-system,Arial,sans-serif;fill:#f3ead6}"
        ".p{font:400 13px ui-monospace,Consolas,monospace;fill:#a89a78}</style>",
        f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="14" fill="#0c0b09" stroke="#E2B454" stroke-opacity=".35" stroke-width="2"/>',
        f'<text class="t" x="{pad}" y="42">Linguagens mais usadas</text>',
        f'<clipPath id="b"><rect x="{pad}" y="62" width="{bar_w}" height="12" rx="6"/></clipPath>',
        '<g clip-path="url(#b)">',
    ]
    x = float(pad)
    for lang, size in top:
        seg = bar_w * size / shown
        out.append(f'<rect x="{x:.1f}" y="62" width="{seg + 0.5:.1f}" height="12" fill="{CORES.get(lang, COR_PADRAO)}"/>')
        x += seg
    out.append("</g>")
    for i, (lang, size) in enumerate(top):
        cx = pad + (i % 2) * 220
        cy = 108 + (i // 2) * 30
        pct = 100 * size / total
        out.append(f'<circle cx="{cx + 6}" cy="{cy - 5}" r="6" fill="{CORES.get(lang, COR_PADRAO)}"/>')
        out.append(f'<text class="l" x="{cx + 20}" y="{cy}">{html.escape(lang)}</text>')
        out.append(f'<text class="p" x="{cx + 196}" y="{cy}" text-anchor="end">{pct:.1f}%</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    repos, langs = load_data()
    text = README.read_text("utf-8")
    if START not in text or END not in text:
        sys.exit(f"Marcadores {START} / {END} não encontrados no README.")
    block = f"{START}\n{projects_md(repos)}\n{END}"
    new = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, text, flags=re.S)
    if new != text:
        README.write_text(new, "utf-8")
    if langs:
        LANGS_SVG.parent.mkdir(exist_ok=True)
        LANGS_SVG.write_text(langs_svg(langs), "utf-8")
    print(f"OK: {len(repos)} repositórios, {len(langs)} linguagens.")


if __name__ == "__main__":
    main()
