#!/usr/bin/env python3
"""Génère site/index.html (recueil de recettes pour TV) à partir des fichiers .md de recettes/<catégorie>/."""

import html
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RECIPES = ROOT / "recettes"
OUT = ROOT / "site" / "index.html"
TEMPLATE = ROOT / "template.html"
IGNORED = {"readme.md"}

# Chaque recette peut commencer par un en-tête :
#   ---
#   categorie: Desserts
#   emoji: 🍪
#   ---
# Ordre d'affichage des catégories sur l'accueil ; les autres suivent par ordre alphabétique.
CATEGORIES = ["Entrées et apéritifs", "Soupes", "Salades", "Plats", "Accompagnements", "Desserts", "Pâtisseries", "Pains et viennoiseries", "Boissons", "Cocktails", "Cocktails sans alcool", "Bases"]
DEFAULT_CATEGORY = "Divers"
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


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", sort_key(text)).strip("-")


def split_meta(text):
    """Sépare l'en-tête « --- clé: valeur --- » éventuel du reste de la recette."""
    meta = {}
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                meta[sort_key(key.strip())] = value.strip()
        text = text[m.end():]
    return meta, text


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
    meta, text = split_meta(path.read_text(encoding="utf-8"))
    title, sections = parse(text)
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
        "emoji": meta.get("emoji") or DEFAULT_EMOJI,
        "category": meta.get("categorie") or DEFAULT_CATEGORY,
        "ingredients": to_html(ingredients) if ingredients else None,
        "prep": [to_html(s) for s in prep],
        "other": [to_html(s) for s in other],
        "steps": steps,
    }


def main():
    files = [p for p in RECIPES.rglob("*.md") if p.name.lower() not in IGNORED]
    recipes = []
    for p in files:
        r = build_recipe(p)
        if p.parent.name != slugify(r["category"]):
            print(f"⚠ {p.relative_to(ROOT)} : catégorie « {r['category']} », à ranger dans recettes/{slugify(r['category'])}/")
        recipes.append(r)
    recipes.sort(key=lambda r: sort_key(r["name"]))
    names = {r["category"] for r in recipes}
    ordered = [c for c in CATEGORIES if c in names] + sorted(names - set(CATEGORIES), key=sort_key)
    categories = [{"name": c, "nameHtml": inline(c), "slug": slugify(c)} for c in ordered]
    for r in recipes:
        r["categorySlug"] = slugify(r["category"])

    def js(value):
        return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")

    page = (TEMPLATE.read_text(encoding="utf-8")
            .replace("/*__DATA__*/[]", js(recipes))
            .replace("/*__CATEGORIES__*/[]", js(categories)))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"{len(recipes)} recettes → {OUT.relative_to(ROOT)}")
    for c in categories:
        print(f"  {c['name']}")
        for r in recipes:
            if r["categorySlug"] == c["slug"]:
                print(f"    {r['emoji']} {r['name']} ({len(r['steps'])} étapes)")


if __name__ == "__main__":
    sys.exit(main())
