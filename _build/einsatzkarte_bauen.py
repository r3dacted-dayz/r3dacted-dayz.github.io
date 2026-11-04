"""Einsatzkarte / Quest Map fuer die Website verpacken (04.11.2026, DE + EN).
Ablauf (21_DayZDev\\exports\\questkarte-<datum>):
  1) Live-Quests holen (scp, Spieler-/Gruppendaten loeschen)
  2) python aufloesen.py German  ->  QK_LANG=de r3d_build_questkarte.py aufgeloest\\Quests einsatzkarte.html
     python aufloesen.py English ->  QK_LANG=en r3d_build_questkarte.py aufgeloest\\Quests einsatzkarte_en.html
  3) python einsatzkarte_bauen.py <einsatzkarte.html> <einsatzkarte_en.html>
     -> website\\einsatzkarte.html (DE) + website\\quest-map.html (EN), gegenseitig verlinkt
"""
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent
SEITEN = [
    ("de", Path(sys.argv[1]), WEB / "einsatzkarte.html", "quest-map.html",
     "R3DACTED Einsatzkarte: alle Quests des DayZ-Servers auf Nasdara mit Ketten, Belohnungen und Auftraggebern - interaktiv und durchsuchbar."),
    ("en", Path(sys.argv[2]), WEB / "quest-map.html", "einsatzkarte.html",
     "R3DACTED quest map: every quest of the DayZ server on Nasdara with chains, rewards and quest givers - interactive and searchable."),
]
CSS = """<style>
.leiste{display:flex;gap:6px;margin:0 0 10px}
.zurueck,.sprache a,.sprache b{display:inline-block;font-family:var(--fm);font-size:11px;letter-spacing:.08em;
 text-decoration:none;border:1px solid var(--edge);padding:4px 9px;background:var(--panel)}
.zurueck,.sprache a{color:var(--ash)}
.zurueck:hover,.sprache a:hover{color:var(--rot);border-color:var(--rot)}
.sprache{margin-left:auto;display:flex;gap:4px}
.sprache b{color:#fff;background:var(--rot);border-color:var(--rot)}
</style>
"""

for lang, quelle, ziel, andere, beschr in SEITEN:
    roh = quelle.read_text(encoding="utf-8")
    assert '<div class="marke">' in roh, "HUD-Marke nicht gefunden - Generator geaendert?"
    de_knopf = '<b>DE</b>' if lang == "de" else f'<a href="{andere}" hreflang="de">DE</a>'
    en_knopf = '<b>EN</b>' if lang == "en" else f'<a href="{andere}" hreflang="en">EN</a>'
    leiste = (f'<div class="leiste"><a class="zurueck" href="./">&larr; R3DACTED</a>'
              f'<span class="sprache">{de_knopf}{en_knopf}</span></div>\n')
    kopf = (f'<!doctype html>\n<html lang="{lang}">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            f'<meta name="description" content="{beschr}">\n'
            f'<link rel="alternate" hreflang="{"en" if lang == "de" else "de"}" href="{andere}">\n'
            '<link rel="icon" href="favicon.png">\n')
    roh = roh.replace('<meta charset="utf-8">\n', "", 1)
    roh = roh.replace('<div class="marke">', leiste + '<div class="marke">', 1)
    ziel.write_text(kopf + CSS + roh, encoding="utf-8")
    print("geschrieben:", ziel.name, len(kopf + roh), "Zeichen")
