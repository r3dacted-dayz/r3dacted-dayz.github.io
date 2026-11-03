#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R3DACTED-Wiki -> statische Seite (GitHub Pages).
Quelle : C:\\Jarvis\\24_R3D_Discord\\wiki\\   (dieselben Feeds wie der Discord-Bot)
Ausgabe: C:\\Jarvis\\24_R3D_Discord\\website\\wiki\\
Aufruf : python wiki_bauen.py      (idempotent + deterministisch; schreibt nur geaenderte Dateien)
Bilder : nur die tatsaechlich referenzierten, als WebP verkleinert (Pillow).
Nichts Internes wird veroeffentlicht: gelesen werden nur die oeffentlichen Felder (siehe VEROEFFENTLICHT unten).
"""
import glob
import hashlib
import html
import json
import os
import re
import sys
import datetime

from PIL import Image

HIER = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.dirname(HIER)                                  # ...\website
QUELLE = os.path.join(os.path.dirname(WEB), 'wiki')          # ...\24_R3D_Discord\wiki
AUS = os.path.join(WEB, 'wiki')
ASSETS = os.path.join(HIER, 'assets')
SITE = 'https://r3dacted-dayz.github.io'

# Themen-Feeds, die reine Listen-Duplikate der Quest-/FAQ-Daten sind (stehen auf quests.html / faq.html)
AUSGESCHLOSSEN = {'faq', 'quests-board', 'quests-peter', 'quests-steve'}
# Titel, die sich nicht sauber an " / " teilen lassen
TITEL_FIX = {'regeln-r3dacted': ('Regeln – R3DACTED', 'Rules – R3DACTED')}
# Kanalerwaehnungen <#id> sind Discord-intern -> neutraler Kanalname (der FAQ-Text nennt ihn selbst)
KANAL = '#support-ticket'

MOD_NAMEN = {  # aus schnittstelle-bot-daten.md (Mod-Kuerzel)
    'VANILLA': 'DayZ Basisspiel / Vanilla', 'DF': 'My Delta Force Weapons', 'BUCA': 'Buca Weapons',
    'FOG': 'Forward Operator Gear', 'BALLERZ': 'BallerZ Gear + DLC', 'RAG': 'RaG BaseItems / Wheel of Fortune',
    'IM7S': 'iM7s Drug Running', 'IAT': 'IAT Crafting Plus', 'APH': 'APH Havoc Storage',
    'NOMNOM': 'NomNom Collectibles', 'SFP': 'SFP', 'BITCOIN': 'Bitcoin-Mining-Farm', 'LBMASTER': 'LBmaster',
    'R3D': 'R3DACTED Core/Vehicles', 'EFT': 'R3D Barter-Items', 'COOKZ': 'CookZ', 'ZMWORKBENCH': 'zm workbench',
    'CARKEY': 'MuchCarKey', 'CARFLIP': 'AutoCarFlip', 'CODELOCK': 'Code Lock', 'DOGTAGS': 'Dogtags',
    'RADIO': 'Psyerns Radio Show', 'TOMBSTONE': 'Tombstone', 'BBP': 'BaseBuildingPlus',
    'AGRICULTURE': 'AgricultureCore / GardeningPlus', 'PVZ': 'PvZmoD The Dark Horde',
    'NINJIN': 'Ninjins PvP/PvE', 'EXPANSION': 'DayZ Expansion',
}
HAENDLER_REIHE = ['Naomi', 'Maria', 'Quinn', 'Rolf', 'Hassan', 'Wechsel-Automat']
TYP = {'story': ('Story', 'Story'), 'daily': ('Täglich', 'Daily'), 'weekly': ('Wöchentlich', 'Weekly')}

DATEIEN = {}      # relativer Pfad (zu AUS) -> Inhalt (str|bytes)
WARN = []
FILTER_LOG = {'themen_ausgeschlossen': sorted(AUSGESCHLOSSEN), 'footer_entfernt': 0, 'kanal_ids': 0}


# ---------------------------------------------------------------- Helfer
def esc(s):
    return html.escape(str(s), quote=True)


def L(de, en):
    """Zweisprachiger Inline-Text (Umschalten per CSS/JS)."""
    if de == en:
        return esc(de)
    return '<span class="de">%s</span><span class="en">%s</span>' % (esc(de), esc(en))


def Lh(de_html, en_html):
    return '<span class="de">%s</span><span class="en">%s</span>' % (de_html, en_html)


def lade(pfad):
    with open(pfad, encoding='utf-8') as f:
        return json.load(f)


def mtime_datum(pfade):
    t = max(os.path.getmtime(p) for p in pfade)
    return datetime.datetime.fromtimestamp(t).strftime('%Y-%m-%d')


# ---------------------------------------------------------------- Markdown (Discord-Dialekt)
def _fmt(s):
    s = re.sub(r'\|\|(.+?)\|\|',
               lambda m: '<span class="spoiler" tabindex="0" role="button" aria-label="Spoiler">%s</span>' % m.group(1), s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'__(.+?)__', r'<u>\1</u>', s)
    s = re.sub(r'~~(.+?)~~', r'<s>\1</s>', s)
    s = re.sub(r'(?<![*\w])\*(?!\s)([^*]+?)(?<!\s)\*(?![*\w])', r'<em>\1</em>', s)
    return s


def inline(raw):
    n_kanal = len(re.findall(r'<#\d+>', raw))
    FILTER_LOG['kanal_ids'] += n_kanal
    s = re.sub(r'<#\d+>', KANAL, raw)
    s = re.sub(r'<(https?://[^>\s]+)>', r'\1', s)
    s = html.escape(s, quote=False)
    stash = []

    def put(h):
        stash.append(h)
        return '\x00%d\x00' % (len(stash) - 1)

    s = re.sub(r'`([^`]+)`', lambda m: put('<code>%s</code>' % m.group(1)), s)
    s = re.sub(r'\[([^\]]+)\]\((https?://[^)\s]+)\)',
               lambda m: put('<a href="%s" rel="noopener">%s</a>' % (m.group(2), _fmt(m.group(1)))), s)
    s = re.sub(r'(?<![\w"=])(https?://[^\s<)]+)',
               lambda m: put('<a href="%s" rel="noopener">%s</a>' % (m.group(1), m.group(1))), s)
    s = _fmt(s)
    return re.sub(r'\x00(\d+)\x00', lambda m: stash[int(m.group(1))], s)


def md(text):
    """Block-Markdown -> HTML. # -> h2, ## -> h3, ### -> h4, '• ' -> Liste, '-# ' -> klein."""
    out = []
    para = []
    lis = []

    def flush():
        nonlocal para, lis
        if para:
            out.append('<p>%s</p>' % '<br>'.join(inline(x) for x in para))
            para = []
        if lis:
            out.append('<ul>%s</ul>' % ''.join('<li>%s</li>' % inline(x) for x in lis))
            lis = []

    for line in text.split('\n'):
        t = line.rstrip()
        if not t.strip():
            flush()
            continue
        m = re.match(r'^(#{1,3}) (.+)$', t)
        if m:
            flush()
            lvl = len(m.group(1)) + 1
            out.append('<h%d>%s</h%d>' % (lvl, inline(m.group(2)), lvl))
            continue
        if t.startswith('-# '):
            flush()
            out.append('<p class="klein">%s</p>' % inline(t[3:]))
            continue
        m = re.match(r'^\s*[•\-] (.+)$', t)
        if m:
            if para:
                out.append('<p>%s</p>' % '<br>'.join(inline(x) for x in para))
                para = []
            lis.append(m.group(1))
            continue
        if lis:
            out.append('<ul>%s</ul>' % ''.join('<li>%s</li>' % inline(x) for x in lis))
            lis = []
        para.append(t)
    flush()
    return '\n'.join(out)


def plain(text):
    """Klartext fuer Suchindex/Beschreibungen (Spoiler fliegen raus)."""
    s = re.sub(r'\|\|.+?\|\|', '', text)
    s = re.sub(r'<#\d+>', KANAL, s)
    s = re.sub(r'\[([^\]]+)\]\(https?://[^)\s]+\)', r'\1', s)
    s = re.sub(r'^(#{1,3} |-# |• |- )', '', s, flags=re.M)
    s = s.replace('**', '').replace('__', '').replace('~~', '').replace('`', '')
    s = re.sub(r'(?<![*\w])\*(?!\s)([^*]+?)(?<!\s)\*(?![*\w])', r'\1', s)
    return re.sub(r'\s+', ' ', s).strip()


def kuerzen(s, n=170):
    if len(s) <= n:
        return s
    return s[:n].rsplit(' ', 1)[0].rstrip(' ,;:–-·') + '…'


# ---------------------------------------------------------------- Bilder
IMG = {}   # Quellpfad -> (url relativ zu wiki/, w, h)


def bild(rel):
    """rel z.B. '_bilder/fahrzeuge/Boat_01.jpg' -> wiki/img/boat_01.webp (verkleinert)."""
    if rel in IMG:
        return IMG[rel]
    src = os.path.join(QUELLE, rel.replace('/', os.sep))
    if not os.path.isfile(src):
        WARN.append('Bild fehlt: ' + rel)
        return None
    stem = os.path.splitext(os.path.basename(rel))[0].lower()
    name = 'img/%s.webp' % stem
    maxkante, q = (480, 78) if '/fahrzeuge/' in rel else (1400, 80)
    ziel = os.path.join(AUS, name.replace('/', os.sep))
    if not os.path.isfile(ziel) or os.path.getmtime(ziel) < os.path.getmtime(src):
        os.makedirs(os.path.dirname(ziel), exist_ok=True)
        im = Image.open(src)
        im = im.convert('RGBA' if im.mode in ('RGBA', 'LA', 'P') else 'RGB')
        im.thumbnail((maxkante, maxkante), Image.LANCZOS)
        im.save(ziel, 'WEBP', quality=q, method=6)
    with Image.open(ziel) as im:
        w, h = im.size
    IMG[rel] = (name, w, h)
    return IMG[rel]


def img_tag(rel, alt, base):
    b = bild(rel)
    if not b:
        return ''
    return '<img src="%s%s" width="%d" height="%d" alt="%s" loading="lazy" decoding="async">' % (base, b[0], b[1], b[2], esc(alt))


# ---------------------------------------------------------------- Themen parsen
RE_KOPF = re.compile(r'^# (🇩🇪 DE|🇺🇸 ENG?) · (.*?)(?:\n|$)(.*)$', re.S)
RE_FLAG = re.compile(r'^(🇩🇪 DE|🇺🇸 ENG?)\s*·\s*(.*)$', re.S)


def teile_absaetze(inhalt):
    """Nicht geflaggter Text: Absaetze mit genau 2 Zeilen = DE/EN, 1 Zeile = beide, '-# ' = klein/beide.
    Rueckgabe: Liste (lang, text) mit lang in de|en|both."""
    res = []
    for p in re.split(r'\n\s*\n', inhalt.strip()):
        zeilen = [z for z in p.split('\n') if z.strip()]
        klein = [z for z in zeilen if z.startswith('-# ')]
        haupt = [z for z in zeilen if not z.startswith('-# ')]
        if len(haupt) == 2:
            res.append(('de', haupt[0]))
            res.append(('en', haupt[1]))
        elif len(haupt) == 1:
            res.append(('both', haupt[0]))
        elif len(haupt) > 2:
            WARN.append('Absatz mit %d Zeilen (als beide): %r' % (len(haupt), haupt[0][:50]))
            res.append(('both', '\n'.join(haupt)))
        for k in klein:
            res.append(('both', k))
    return res


def bauen_thema(pfad):
    d = lade(pfad)
    slug = d['slug']
    titel_roh = d['titel']
    if slug in TITEL_FIX:
        tde, ten = TITEL_FIX[slug]
        icon = titel_roh.split(' ', 1)[0]
    else:
        teile = titel_roh.split(' / ')
        if len(teile) != 2:
            WARN.append('Titel nicht teilbar: ' + titel_roh)
            teile = [titel_roh, titel_roh]
        m = re.match(r'^(\S+)\s+(.*)$', teile[0])
        icon, tde = (m.group(1), m.group(2)) if m and not re.match(r'^[\w]', m.group(1)) else ('', teile[0])
        ten = teile[1]
    blocks = []     # dict(lang, kind, ...)
    intro = {'de': '', 'en': ''}
    plaintext = {'de': [], 'en': []}
    heads = {'de': [], 'en': []}

    def add(lang, kind, **kw):
        b = {'lang': lang, 'kind': kind}
        b.update(kw)
        blocks.append(b)
        return b

    def texte(lang, t):
        for l in (('de', 'en') if lang == 'both' else (lang,)):
            plaintext[l].append(plain(t))

    for m in d['nachrichten']:
        inh = (m.get('inhalt') or '').strip()
        bildrel = m.get('bild')
        embeds = m.get('embeds') or []
        if inh:
            km = RE_KOPF.match(inh)
            if km:
                lang = 'de' if km.group(1).startswith('🇩🇪') else 'en'
                add(lang, 'md', text=km.group(3).strip())
                texte(lang, km.group(3))
                for h in re.findall(r'^#{1,3} (.+)$', km.group(3), flags=re.M):
                    heads[lang].append(plain(h))
            else:
                for lang, t in teile_absaetze(inh):
                    add(lang, 'md', text=t)
                    texte(lang, t)
                    if lang in ('de', 'en') and not intro[lang] and not t.startswith(('#', '-#')):
                        intro[lang] = plain(t)
                    for h in re.findall(r'^#{1,3} (.+)$', t, flags=re.M):
                        for l in (('de', 'en') if lang == 'both' else (lang,)):
                            heads[l].append(plain(h))
        for e in embeds:
            et = e.get('title') or ''
            fm = RE_FLAG.match(et)
            lang = None
            if fm:
                lang = 'de' if fm.group(1).startswith('🇩🇪') else 'en'
                et = fm.group(2)
            if e.get('footer'):
                FILTER_LOG['footer_entfernt'] += 1
            desc = e.get('description') or ''
            flds = [(f['name'], f['value']) for f in (e.get('fields') or [])]
            if lang is None and bildrel and not flds:
                add('both', 'card', title=et, text=desc, img=bildrel)
                bildrel = None
                for l in ('de', 'en'):
                    plaintext[l].append(plain(et + ' ' + desc))
                continue
            lang = lang or 'both'
            add(lang, 'embed', title=et, text=desc, fields=flds)
            for l in (('de', 'en') if lang == 'both' else (lang,)):
                heads[l].append(plain(et))
                plaintext[l].append(plain(desc))
                for n, v in flds:
                    heads[l].append(plain(n))
                    plaintext[l].append(plain(v))
        if bildrel:
            alt = ' / '.join(x for x in (plain(z) for z in inh.split('\n')[:2]) if x) or tde
            add('both', 'fig', img=bildrel, alt=kuerzen(alt, 140))
    if not intro['de']:
        # ohne Intro-Zeile: erste Beschreibung/erstes Feld je Sprache
        for l in ('de', 'en'):
            for b in blocks:
                if b['lang'] == l and b['kind'] == 'embed':
                    intro[l] = plain(b['text'] or (b['fields'][0][1] if b['fields'] else ''))
                    break
    return {
        'slug': slug, 'icon': icon, 'tde': tde, 'ten': ten, 'order': d.get('reihenfolge', 999),
        'intro': {l: kuerzen(re.sub(r'^[^\w]+', '', intro[l])) for l in intro},
        'heads': {l: ' · '.join(heads[l]) for l in heads},
        'text': {l: ' '.join(x for x in plaintext[l] if x) for l in plaintext},
        'blocks': blocks,
    }


def render_blocks(thema, base):
    out = []
    i = 0
    bl = thema['blocks']
    while i < len(bl):
        b = bl[i]
        if b['kind'] == 'card':
            cards = []
            while i < len(bl) and bl[i]['kind'] == 'card':
                c = bl[i]
                cards.append('<article class="vcard">%s<div class="vtxt"><h3>%s</h3>%s</div></article>' % (
                    img_tag(c['img'], c['title'], base), inline(c['title']), md(c['text'])))
                i += 1
            out.append('<div class="cards">%s</div>' % ''.join(cards))
            continue
        if b['kind'] == 'md':
            h = md(b['text'])
        elif b['kind'] == 'fig':
            h = '<figure>%s</figure>' % img_tag(b['img'], b['alt'], base)
        else:  # embed
            parts = []
            if b['title']:
                parts.append('<h2>%s</h2>' % inline(b['title']))
            if b['text']:
                parts.append(md(b['text']))
            for n, v in b['fields']:
                parts.append('<section class="feld"><h3>%s</h3>%s</section>' % (inline(n), md(v)))
            h = '\n'.join(parts)
        if h:
            out.append(h if b['lang'] == 'both' else '<div class="%s">%s</div>' % (b['lang'], h))
        i += 1
    return '\n'.join(out)


# ---------------------------------------------------------------- Seiten-Geruest
def kopf(base, key, tde, ten, dde, den, canon):
    root = base + '../'
    nav = [('index', base or './', 'Wiki', 'Wiki'), ('items', base + 'items.html', 'Items', 'Items'),
           ('quests', base + 'quests.html', 'Quests', 'Quests'), ('faq', base + 'faq.html', 'FAQ', 'FAQ')]
    navh = ''.join('<a href="%s"%s>%s</a>' % (u, ' aria-current="page"' if k == key else '', L(a, b)) for k, u, a, b in nav)
    suche = ''
    if key != 'index':
        suche = ('<form class="hsuche" action="%s" method="get" role="search"><input type="search" name="q" '
                 'data-ph-de="Wiki durchsuchen" data-ph-en="Search the wiki" placeholder="Wiki durchsuchen" '
                 'data-al-de="Wiki durchsuchen" data-al-en="Search the wiki" aria-label="Wiki durchsuchen"></form>') % (base or './')
    return """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(t)s</title>
<meta name="description" content="%(d)s">
<meta property="og:title" content="%(t)s">
<meta property="og:description" content="%(d)s">
<meta property="og:type" content="website">
<meta property="og:image" content="%(site)s/banner.jpg">
<link rel="canonical" href="%(site)s/wiki/%(canon)s">
<link rel="icon" href="%(root)sfavicon.png">
<link href="https://fonts.googleapis.com/css2?family=Archivo+Black&family=Barlow+Condensed:wght@500;700&family=JetBrains+Mono&display=swap" rel="stylesheet">
<link rel="stylesheet" href="%(base)swiki.css?v=%(cv)s">
<script>(function(){var l;try{l=localStorage.getItem('r3dLang')}catch(e){}if(l!=='de'&&l!=='en'){l=((navigator.language||'de').slice(0,2).toLowerCase()==='de')?'de':'en'}var h=document.documentElement;h.setAttribute('data-lang',l);h.setAttribute('lang',l)})();</script>
</head>
<body data-page="%(key)s" data-title-de="%(t)s" data-title-en="%(te)s">
<a class="skip" href="#inhalt">%(skip)s</a>
<header><div class="wrap">
  <img src="%(root)slogo.png" alt="R3DACTED logo"><b>R3DACTED</b>
  <a href="https://trackyserver.com/dayz-server/country/DE"><img alt="Dayz servers list" src="https://trackyserver.com/pages/logos/logo.webp"></a>
  <nav aria-label="Wiki">%(nav)s<a href="%(root)s">%(home)s</a><a href="https://discord.gg/pBTkAF7pXq">Discord</a></nav>
  %(suche)s
  <div class="lang" role="group" aria-label="Sprache / Language"><button type="button" data-set-lang="de" aria-pressed="true">DE</button><button type="button" data-set-lang="en" aria-pressed="false">EN</button></div>
</div></header>
<main id="inhalt" class="wrap">
""" % {'t': esc(tde + ' – R3DACTED Wiki'), 'te': esc(ten + ' – R3DACTED Wiki'), 'd': esc(dde + ' | ' + den) if den else esc(dde),
       'site': SITE, 'canon': canon, 'root': root, 'base': base, 'cv': ASSET_V['css'], 'key': key, 'nav': navh,
       'suche': suche, 'skip': L('Zum Inhalt', 'Skip to content'), 'home': L('Start', 'Home')}


def fuss(base, stand):
    d = stand.split('-')
    return """
</main>
<script src="%(base)swiki.js?v=%(jv)s" defer></script>
<footer><div class="wrap">
  <span>© 2026 R3DACTED · Not affiliated with Bohemia Interactive</span>
  <span class="stand">%(stand)s</span>
  <a href="https://trackyserver.com/dayz-server/country/DE"><img alt="Dayz servers list" src="https://trackyserver.com/pages/logos/logo.webp"></a>
  <a href="https://trackyserver.com/dayz-server/country/DE">Dayz servers list</a>
</div></footer>
</body>
</html>
""" % {'base': base, 'jv': ASSET_V['js'],
       'stand': L('Daten-Stand %s.%s.%s' % (d[2], d[1], d[0]), 'Data as of %s' % stand)}


def seite(pfad, base, key, tde, ten, dde, den, body, stand):
    canon = pfad if pfad != 'index.html' else ''
    DATEIEN[pfad] = kopf(base, key, tde, ten, dde, den, canon) + body + fuss(base, stand)


# ---------------------------------------------------------------- Hauptprogramm
def zahl_de(n):
    return '{:,}'.format(n).replace(',', '.')


def main():
    global ASSET_V
    os.makedirs(AUS, exist_ok=True)
    # Assets (css/js) -> Versions-Hash fuer Cache-Busting (deterministisch)
    ASSET_V = {}
    for k, n in (('css', 'wiki.css'), ('js', 'wiki.js')):
        data = open(os.path.join(ASSETS, n), 'rb').read()
        DATEIEN[n] = data
        ASSET_V[k] = hashlib.sha1(data).hexdigest()[:8]

    items_roh = lade(os.path.join(QUELLE, '_items.json'))
    quests = lade(os.path.join(QUELLE, '_quests.json'))
    faq = lade(os.path.join(QUELLE, '_faq.json'))
    themen = []
    quell_dateien = [os.path.join(QUELLE, n) for n in ('_items.json', '_quests.json', '_faq.json')]
    for p in sorted(glob.glob(os.path.join(QUELLE, '*.json'))):
        n = os.path.basename(p)
        if n.startswith('_') or '.bak' in n or n.count('.') != 1:
            continue
        if n[:-5] in AUSGESCHLOSSEN:
            continue
        themen.append(bauen_thema(p))
        quell_dateien.append(p)
    themen.sort(key=lambda t: (t['order'], t['slug']))
    stand = mtime_datum(quell_dateien)

    # ---- Items -> kompakte Tabelle
    cats, cat_idx, mods, mod_idx = [], {}, [], {}
    hand = list(HAENDLER_REIHE)
    for it in items_roh:
        for h in it.get('haendler') or []:
            if h not in hand:
                hand.append(h)
    zeilen = []
    for it in items_roh:
        c = (it.get('kategorie') or '', it.get('kategorie_en') or it.get('kategorie') or '')
        if c not in cat_idx:
            cat_idx[c] = len(cats)
            cats.append(list(c))
        m = it.get('mod') or ''
        if m not in mod_idx:
            mod_idx[m] = len(mods)
            mods.append([m, MOD_NAMEN.get(m, m)])
        mask = 0
        for h in it.get('haendler') or []:
            mask |= 1 << hand.index(h)
        de = it.get('name_de') or it.get('name_en') or it['klasse']
        en = it.get('name_en') or de
        z = [it['klasse'], de, '' if en == de else en, mod_idx[m], it.get('kauf'), it.get('verkauf'), mask, cat_idx[c]]
        if it.get('bild') and bild(it['bild']):
            z.append(bild(it['bild'])[0])
        zeilen.append(z)
    mods_sort = sorted(range(len(mods)), key=lambda i: mods[i][0])
    # (Reihenfolge der Filter wird im Browser sortiert; hier unveraendert lassen -> stabile Indizes)

    # ---- search.json
    suche = {
        'v': 1, 'stand': stand, 'mods': mods, 'cats': cats, 'hand': hand, 'items': zeilen,
        'topics': [[t['slug'], t['icon'], t['tde'], t['ten'], t['intro']['de'], t['intro']['en'],
                    t['heads']['de'], t['heads']['en'], t['text']['de'], t['text']['en']] for t in themen],
        'quests': [[q['nr'], q['typ'], q['geber'], q['titel_de'], q['titel_en'],
                    '' if q.get('schatzsuche') else q['ziel_de'], '' if q.get('schatzsuche') else q['ziel_en'],
                    q['belohnung_de'], q['belohnung_en'], q.get('voraussetzung') or [], 1 if q.get('schatzsuche') else 0]
                   for q in quests],
        'faq': [[i, f['gruppe_de'], f['gruppe_en'], f['frage_de'], f['frage_en'], plain(f['antwort_de']), plain(f['antwort_en'])]
                for i, f in enumerate(faq)],
    }
    DATEIEN['search.json'] = json.dumps(suche, ensure_ascii=False, separators=(',', ':'))

    # ---- Themenseiten
    for t in themen:
        base = '../'
        body = ('<nav class="crumb" aria-label="Breadcrumb"><a href="../">Wiki</a> › %s</nav>'
                '<h1>%s <span class="h1t">%s</span></h1>\n%s\n') % (
            L(t['tde'], t['ten']), esc(t['icon']), L(t['tde'], t['ten']), render_blocks(t, base))
        seite('themen/%s.html' % t['slug'], base, 'thema', t['tde'], t['ten'], t['intro']['de'] or t['tde'],
              t['intro']['en'], body, stand)

    # ---- wiki/index.html
    kacheln = []
    for t in themen:
        kacheln.append('<a class="tile" href="themen/%s.html"><span class="ti">%s</span><span class="tt">%s</span>'
                       '<span class="td">%s</span></a>' % (t['slug'], esc(t['icon']), L(t['tde'], t['ten']),
                                                              L(t['intro']['de'], t['intro']['en'])))
    n_i, n_q, n_f = len(zeilen), len(quests), len(faq)
    body = """
<section class="hero-s">
  <h1>R3DACTED <span class="h1t">Wiki</span></h1>
  <p class="sub">%(sub)s</p>
  <form class="gsuche" id="sform" action="./" method="get" role="search">
    <input id="q" name="q" type="search" autocomplete="off" autofocus spellcheck="false"
      data-ph-de="Suchen: Item, Quest, Händler, Frage … (z. B. m4a1, Hassan, Bitcoin)" data-ph-en="Search: item, quest, trader, question … (e.g. m4a1, Hassan, Bitcoin)"
      placeholder="Suchen: Item, Quest, Händler, Frage …" data-al-de="Wiki durchsuchen" data-al-en="Search the wiki" aria-label="Wiki durchsuchen">
    <button type="submit">%(go)s</button>
  </form>
  <p class="hint">%(hint)s</p>
  <div id="status" class="sr" role="status" aria-live="polite"></div>
</section>
<noscript><p class="warn">%(nojs)s</p></noscript>
<div id="results" hidden></div>
<div id="start">
  <div class="einstieg">
    <a class="tile big" href="items.html"><span class="ti">🎒</span><span class="tt">Items</span><span class="td">%(items)s</span></a>
    <a class="tile big" href="quests.html"><span class="ti">📜</span><span class="tt">Quests</span><span class="td">%(quests)s</span></a>
    <a class="tile big" href="faq.html"><span class="ti">❓</span><span class="tt">FAQ</span><span class="td">%(faq)s</span></a>
  </div>
  <h2>%(themen)s</h2>
  <div class="tiles">%(kacheln)s</div>
</div>
""" % {
        'sub': L('Alles über den DayZ-Server auf Nasdara – durchsuchbar.', 'Everything about the DayZ server on Nasdara – searchable.'),
        'go': L('Suchen', 'Search'),
        'hint': L('Tippfehler, Umlaute und Bindestriche sind egal: „m4a1“ findet „M4-A1“. Tastatur: / zum Suchen, ↑ ↓ zum Wählen, Esc zum Leeren.',
                  'Typos, umlauts and hyphens do not matter: “m4a1” finds “M4-A1”. Keys: / to search, ↑ ↓ to pick, Esc to clear.'),
        'nojs': L('Für Suche und Filter wird JavaScript benötigt. Die Themenseiten funktionieren auch ohne.',
                  'Search and filters need JavaScript. The topic pages work without it.'),
        'items': L('%s handelbare Items mit Preisen' % zahl_de(n_i), '{:,} tradeable items with prices'.format(n_i)),
        'quests': L('%d Quests mit Ziel & Belohnung' % n_q, '%d quests with goal & reward' % n_q),
        'faq': L('%d häufige Fragen' % n_f, '%d frequently asked questions' % n_f),
        'themen': L('Themen', 'Topics'), 'kacheln': ''.join(kacheln)}
    seite('index.html', '', 'index', 'Wiki', 'Wiki',
          'Das R3DACTED-Wiki: Items, Preise, Quests, Händler, FAQ und Spielmechaniken – durchsuchbar.',
          'The R3DACTED wiki: items, prices, quests, traders, FAQ and game mechanics – searchable.', body, stand)

    # ---- items.html
    body = """
<h1>%(h)s</h1>
<p class="sub">%(sub)s</p>
<div class="filter" role="search">
  <label class="fl wide"><span class="fn">%(l_q)s</span><input id="iq" type="search" autocomplete="off" spellcheck="false" data-ph-de="Name oder Klassenname …" data-ph-en="Name or class name …" placeholder="Name oder Klassenname …"></label>
  <label class="fl"><span class="fn">%(l_cat)s</span><select id="icat"></select></label>
  <label class="fl"><span class="fn">Mod</span><select id="imod"></select></label>
  <label class="fl"><span class="fn">%(l_h)s</span><select id="ih"></select></label>
  <label class="fl"><span class="fn">%(l_s)s</span><select id="isort"></select></label>
</div>
<p id="icount" class="count" role="status" aria-live="polite"></p>
<noscript><p class="warn">%(nojs)s</p></noscript>
<div id="igrid" class="igrid"></div>
<div class="more"><button type="button" id="imore" hidden></button></div>
""" % {'h': L('Items', 'Items'),
       'sub': L('Alle handelbaren Items. Preise in R3D Coins (RC), wie sie am Händler stehen.',
                'All tradeable items. Prices in R3D Coins (RC), as shown at the trader.'),
       'l_q': L('Suche', 'Search'), 'l_cat': L('Kategorie', 'Category'), 'l_h': L('Händler', 'Trader'), 'l_s': L('Sortierung', 'Sort'),
       'nojs': L('Für die Item-Liste wird JavaScript benötigt.', 'The item list needs JavaScript.')}
    seite('items.html', '', 'items', 'Items', 'Items',
          'Alle handelbaren Items auf R3DACTED mit Preisen, Händlern und Mods – filterbar.',
          'All tradeable items on R3DACTED with prices, traders and mods – filterable.', body, stand)

    # ---- quests.html
    qh = []
    for q in quests:
        nr = q['nr']
        td, te = TYP.get(q['typ'], (q['typ'], q['typ']))
        if q.get('schatzsuche'):
            zd = '<span class="spoiler" tabindex="0" role="button" aria-label="Spoiler">%s</span>' % esc(q['ziel_de'])
            ze = '<span class="spoiler" tabindex="0" role="button" aria-label="Spoiler">%s</span>' % esc(q['ziel_en'])
        else:
            zd, ze = esc(q['ziel_de']), esc(q['ziel_en'])
        vor = ''
        if q.get('voraussetzung'):
            lk = ', '.join('<a href="#q%d">#%03d</a>' % (v, v) for v in q['voraussetzung'])
            vor = '<p class="vor"><strong>%s</strong> %s</p>' % (L('Voraussetzung:', 'Requires:'), lk)
        qh.append(
            '<article class="qcard" id="q%d" data-typ="%s" data-geber="%s"><h3><span class="qnr">#%03d</span> %s</h3>'
            '<div class="badges"><span class="badge t-%s">%s</span><span class="badge">%s</span></div>'
            '<p><strong>%s</strong> %s</p><p><strong>%s</strong> %s</p>%s</article>' % (
                nr, esc(q['typ']), esc(q['geber']), nr, L(q['titel_de'], q['titel_en']), esc(q['typ']), L(td, te), esc(q['geber']),
                L('Ziel:', 'Goal:'), Lh(zd, ze), L('Belohnung:', 'Reward:'), L(q['belohnung_de'], q['belohnung_en']), vor))
    gebers = sorted({q['geber'] for q in quests})
    typs = [t for t in ('story', 'daily', 'weekly') if any(q['typ'] == t for q in quests)]
    body = """
<h1>%(h)s</h1>
<p class="sub">%(sub)s</p>
<div class="filter">
  <label class="fl wide"><span class="fn">%(l_q)s</span><input id="fq" type="search" autocomplete="off" data-ph-de="Titel, Ziel, Belohnung …" data-ph-en="Title, goal, reward …" placeholder="Titel, Ziel, Belohnung …"></label>
  <label class="fl"><span class="fn">%(l_t)s</span><select id="ftyp"><option value="" data-t-de="Alle" data-t-en="All">Alle</option>%(typopt)s</select></label>
  <label class="fl"><span class="fn">%(l_g)s</span><select id="fgeber"><option value="" data-t-de="Alle" data-t-en="All">Alle</option>%(gopt)s</select></label>
</div>
<p id="fcount" class="count" role="status" aria-live="polite"></p>
<div class="qgrid" id="fliste">%(karten)s</div>
""" % {'h': L('Quests', 'Quests'),
       'sub': L('%d Quests – Voraussetzungen schalten sich frei. Schatzsuchen sind als Spoiler versteckt (anklicken).' % len(quests),
                '%d quests – prerequisites unlock as you go. Treasure hunts are hidden as spoilers (click to reveal).' % len(quests)),
       'l_q': L('Suche', 'Search'), 'l_t': L('Art', 'Type'), 'l_g': L('Auftraggeber', 'Quest giver'),
       'typopt': ''.join('<option value="%s" data-t-de="%s" data-t-en="%s">%s</option>' % (t, TYP[t][0], TYP[t][1], TYP[t][0]) for t in typs),
       'gopt': ''.join('<option value="%s">%s</option>' % (esc(g), esc(g)) for g in gebers), 'karten': '\n'.join(qh)}
    seite('quests.html', '', 'quests', 'Quests', 'Quests',
          'Alle Quests auf R3DACTED mit Ziel, Belohnung und Voraussetzungen.',
          'All R3DACTED quests with goal, reward and prerequisites.', body, stand)

    # ---- faq.html
    gruppen = []
    for i, f in enumerate(faq):
        if not gruppen or gruppen[-1][0] != f['gruppe_de']:
            gruppen.append((f['gruppe_de'], f['gruppe_en'], []))
        gruppen[-1][2].append((i, f))
    fh = []
    for gd, ge, lst in gruppen:
        fh.append('<section class="fgruppe"><h2>%s</h2>' % L(gd, ge))
        for i, f in lst:
            fh.append('<details class="fq" id="f%d"><summary>%s</summary><div class="fa">%s</div></details>' % (
                i, L(f['frage_de'], f['frage_en']), Lh(md(f['antwort_de']), md(f['antwort_en']))))
        fh.append('</section>')
    body = """
<h1>FAQ</h1>
<p class="sub">%(sub)s</p>
<div class="filter">
  <label class="fl wide"><span class="fn">%(l_q)s</span><input id="fq" type="search" autocomplete="off" data-ph-de="Frage oder Stichwort …" data-ph-en="Question or keyword …" placeholder="Frage oder Stichwort …"></label>
</div>
<p id="fcount" class="count" role="status" aria-live="polite"></p>
<div id="fliste">%(f)s</div>
""" % {'sub': L('%d häufige Fragen, nach Themen gruppiert.' % len(faq), '%d frequently asked questions, grouped by topic.' % len(faq)),
       'l_q': L('Suche', 'Search'), 'f': '\n'.join(fh)}
    seite('faq.html', '', 'faq', 'FAQ', 'FAQ',
          'Häufige Fragen zu R3DACTED: Join, Wirtschaft, Quests, Basisbau, Season Pass, Support.',
          'Frequently asked questions about R3DACTED: joining, economy, quests, base building, season pass, support.', body, stand)

    # ---- schreiben + aufraeumen
    for rel, b in IMG.items():
        pass
    erwartet = set(DATEIEN) | {v[0] for v in IMG.values()}
    geaendert = 0
    for rel, inhalt in DATEIEN.items():
        ziel = os.path.join(AUS, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(ziel), exist_ok=True)
        data = inhalt if isinstance(inhalt, bytes) else inhalt.encode('utf-8')
        if os.path.isfile(ziel) and open(ziel, 'rb').read() == data:
            continue
        with open(ziel, 'wb') as f:
            f.write(data)
        geaendert += 1
    entfernt = 0
    for wurzel, _, dateien in os.walk(AUS):
        for n in dateien:
            p = os.path.join(wurzel, n)
            rel = os.path.relpath(p, AUS).replace(os.sep, '/')
            if rel not in erwartet:
                os.remove(p)
                entfernt += 1
    for wurzel, dirs, dateien in os.walk(AUS, topdown=False):
        if not os.listdir(wurzel) and wurzel != AUS:
            os.rmdir(wurzel)

    gesamt = sum(os.path.getsize(os.path.join(w, n)) for w, _, ds in os.walk(AUS) for n in ds)
    print('Wiki gebaut: %d Dateien (%d geschrieben, %d entfernt), %.1f KB wiki\\, Daten-Stand %s' % (
        len(erwartet), geaendert, entfernt, gesamt / 1024, stand))
    print('Themen: %d, Items: %d, Quests: %d, FAQ: %d, Bilder: %d' % (len(themen), n_i, n_q, n_f, len(IMG)))
    print('Gefiltert/Hinweise:', json.dumps(FILTER_LOG, ensure_ascii=False))
    for w in WARN:
        print('WARNUNG:', w)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
