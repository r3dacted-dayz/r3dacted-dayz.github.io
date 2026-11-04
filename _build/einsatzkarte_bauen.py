"""Einsatzkarte (Quest-Karte) fuer die Website verpacken (04.11.2026).
Ablauf: 1) Live-Quests holen + aufloesen (21_DayZDev\\exports\\questkarte-<datum>\\aufloesen.py),
        2) r3d_build_questkarte.py <aufgeloest\\Quests> <einsatzkarte.html>,
        3) dieses Skript: python einsatzkarte_bauen.py <einsatzkarte.html>  -> website\\einsatzkarte.html
"""
import sys
from pathlib import Path

QUELLE = Path(sys.argv[1])
ZIEL = Path(__file__).resolve().parent.parent / "einsatzkarte.html"

roh = QUELLE.read_text(encoding="utf-8")
assert '<div class="marke">' in roh, "HUD-Marke nicht gefunden - Generator geaendert?"

kopf = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="R3DACTED Einsatzkarte: alle Quests des DayZ-Servers auf Nasdara mit Ketten, Belohnungen und Auftraggebern - interaktiv und durchsuchbar.">
<link rel="icon" href="favicon.png">
"""
zusatz_css = """<style>
.zurueck{display:inline-block;margin:0 0 10px;font-family:var(--fm);font-size:11px;letter-spacing:.08em;
 color:var(--ash);text-decoration:none;border:1px solid var(--edge);padding:4px 9px;background:var(--panel)}
.zurueck:hover{color:var(--rot);border-color:var(--rot)}
</style>
"""
roh = roh.replace('<meta charset="utf-8">\n', "", 1)
roh = roh.replace('<div class="marke">', '<a class="zurueck" href="./">&larr; R3DACTED</a>\n<div class="marke">', 1)
ZIEL.write_text(kopf + zusatz_css + roh, encoding="utf-8")
print("geschrieben:", ZIEL, len(kopf + roh), "Zeichen")
