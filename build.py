#!/usr/bin/env python3
"""Génère site/index.html (recueil de recettes pour TV) à partir des fichiers .md du dossier."""

import html
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "site" / "index.html"
TEMPLATE = ROOT / "template.html"
IGNORED = {"readme.md"}

# Émoji affiché sur la carte de chaque recette (clé = nom du fichier sans .md).
EMOJIS = {
    "beignets": "🍎",
    "crepes": "🫓",
    "gaufres": "🧇",
    "pain": "🥖",
    "pancakes": "🥞",
    "pate-brisee": "🥧",
    "pate-feuilletee": "🥐",
    "pate-sablee": "🍓",
    "pate-a-choux": "🧁",
    "cookies": "🍪",
    "gateau-au-yaourt": "🍰",
    "quatre-quarts": "🧈",
    "genoise": "🎂",
    "brioche": "🍞",
    "pain-au-beurre": "🌴",
    "pizza": "🍕",
}
DEFAULT_EMOJI = "🍽️"


def inline(text):
    """Convertit le Markdown en ligne (gras, italique) en HTML."""
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text)
    return text


def capitalize(text):
    return text[:1].upper() + text[1:]


def sort_key(title):
    return unicodedata.normalize("NFD", title).encode("ascii", "ignore").decode().lower()


def parse(text):
    """Découpe une recette en titre, sous-titre et sections (## / ###) contenant des blocs."""
    title, sections = "", []
    sec = sub = lst = None
    para = []

    def flush_para():
        if para:
            current_sub()["blocks"].append({"t": "p", "raw": " ".join(para)})
            para.clear()

    def current_sub():
        nonlocal sec, sub
        if sec is None:
            sec = {"title": "", "subs": []}
            sections.append(sec)
        if sub is None:
            sub = {"title": "", "blocks": []}
            sec["subs"].append(sub)
        return sub

    for line in text.splitlines():
        stripped = line.strip()
        ul = re.match(r"^[-*]\s+(.*)$", stripped)
        ol = re.match(r"^\d+\.\s+(.*)$", stripped)
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("## "):
            flush_para()
            lst = None
            sec = {"title": line[3:].strip(), "subs": []}
            sections.append(sec)
            sub = None
        elif line.startswith("### "):
            flush_para()
            lst = None
            current_sub()
            sub = {"title": line[4:].strip(), "blocks": []}
            sec["subs"].append(sub)
        elif ul or ol:
            flush_para()
            kind = "ul" if ul else "ol"
            if lst is None or lst["t"] != kind:
                lst = {"t": kind, "raw": []}
                current_sub()["blocks"].append(lst)
            lst["raw"].append((ul or ol).group(1))
        elif not stripped:
            flush_para()
            lst = None
        elif lst is not None and line[:1].isspace():
            lst["raw"][-1] += " " + stripped
        else:
            lst = None
            para.append(stripped)
    flush_para()
    return title, sections


def build_recipe(path):
    title, sections = parse(path.read_text(encoding="utf-8"))
    m = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", title)
    name, subtitle = (m.group(1), m.group(2)) if m else (title, "")

    steps, ingredients, other = [], None, []
    for sec in sections:
        low = sec["title"].lower()
        if "ingrédient" in low:
            ingredients = sec
        if "prépar" in low:
            for sub in sec["subs"]:
                for block in sub["blocks"]:
                    if block["t"] != "ol":
                        continue
                    for raw in block["raw"]:
                        sm = re.match(r"^\*\*(.+?)\*\*\s*:\s*(.*)$", raw)
                        steps.append({
                            "label": inline(sub["title"]),
                            "title": inline(sm.group(1)) if sm else "",
                            "body": inline(capitalize(sm.group(2) if sm else raw)),
                        })

    def to_html(sec):
        return {
            "title": inline(sec["title"]),
            "subs": [{
                "title": inline(sub["title"]),
                "blocks": [
                    {"t": b["t"], "html": inline(b["raw"])} if b["t"] == "p"
                    else {"t": b["t"], "items": [inline(r) for r in b["raw"]]}
                    for b in sub["blocks"]
                ],
            } for sub in sec["subs"]],
        }

    for sec in sections:
        if sec is not ingredients and "prépar" not in sec["title"].lower():
            other.append(sec)
    prep = [s for s in sections if "prépar" in s["title"].lower()]

    return {
        "slug": path.stem,
        "name": name,
        "nameHtml": inline(name),
        "subtitle": inline(subtitle),
        "emoji": EMOJIS.get(path.stem, DEFAULT_EMOJI),
        "ingredients": to_html(ingredients) if ingredients else None,
        "prep": [to_html(s) for s in prep],
        "other": [to_html(s) for s in other],
        "steps": steps,
    }


def main():
    files = [p for p in ROOT.glob("*.md") if p.name.lower() not in IGNORED]
    recipes = sorted((build_recipe(p) for p in files), key=lambda r: sort_key(r["name"]))
    data = json.dumps(recipes, ensure_ascii=False).replace("</", "<\\/")
    page = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/[]", data)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"{len(recipes)} recettes → {OUT.relative_to(ROOT)}")
    for r in recipes:
        print(f"  {r['emoji']} {r['name']} ({len(r['steps'])} étapes)")


if __name__ == "__main__":
    sys.exit(main())
