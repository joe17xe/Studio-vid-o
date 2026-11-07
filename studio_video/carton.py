"""Le carton de fin : rendu par le moteur à partir de marque.json, ou fourni par le projet.

Carton intégré : fond aux couleurs de la marque, logo (sur pastille si « logo_fond »),
la phrase dans chaque langue, le motif séparateur, le lien, le mot-dièse et, en option,
les logos des partenaires sur tuiles. Les éléments entrent l'un après l'autre ; chaque
entrée est un repère sonore (tic).

Carton d'extension : « carton_fin.extension » = "fichier.py:fonction" (relatif au dossier
studio). La fonction reçoit (marque, cache) et renvoie un dict :
  {"mp4": chemin, "duree": s, "saut_images": n, "battements": [t…], "tics": [t…]}
(« saut_images » : images à sauter au début du MP4, par exemple une couverture tenue).
"""

import hashlib
import html
import importlib.util
import json
import re
import subprocess
from pathlib import Path

from . import navigateur

IPS = 30


def motif_svg(marque, largeur=150):
    c = marque.couleurs
    sep = marque['sous_titres'].get('separateur', 'trait')
    if sep == 'pouls':
        return (f'<svg class="motif" viewBox="0 0 150 26" style="width:{largeur}px;height:26px">'
                f'<path d="M0 15 H52 L60 15 L66 3 L74 24 L80 9 L85 15 H150" fill="none" stroke="{c["accent"]}" '
                'stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/></svg>')
    if sep == 'trait':
        return (f'<svg class="motif" viewBox="0 0 74 8" style="width:74px;height:8px">'
                f'<rect width="34" height="8" rx="4" fill="{c["accent"]}"/>'
                f'<rect x="40" width="34" height="8" rx="4" fill="{c["accent_2"]}"/></svg>')
    return ''


def page_carton(marque):
    c = marque.couleurs
    cf = marque['carton_fin']
    L, H, haut, bas = marque.vertical
    logo = marque.chemin(marque['logo'])
    pastille = marque['logo_fond']
    elements, d = [], 0.25

    def ajout(contenu, pas=0.35):
        nonlocal d
        elements.append(f'<div class="a" style="animation-delay:{d:.2f}s">{contenu}</div>')
        d += pas

    if logo:
        img = f'<img src="{logo.as_uri()}" style="width:{260 if pastille else 330}px">'
        ajout(f'<div class="pastille">{img}</div>' if pastille else img, 0.55)
    if cf.get('etiquette'):
        ajout(f'<p class="etiquette">{html.escape(cf["etiquette"])}</p>', 0.25)
    phrase = cf.get('phrase') or {}
    if phrase.get(marque['langues']['principale']):
        principale = marque['langues']['principale']
        ajout(f'<p class="titre"{marque.attributs("titres", principale)}>{phrase[principale]}</p>')
    for lg in marque['langues'].get('secondes', []):
        if phrase.get(lg):
            ajout(f'<p class="second"{marque.attributs("texte", lg)}>{phrase[lg]}</p>', 0.3)
    m = motif_svg(marque)
    if m:
        ajout(m, 0.3)
    if cf.get('lien'):
        ajout(f'<p class="lien">{html.escape(cf["lien"])}</p>', 0.3)
    if cf.get('hashtag'):
        ajout(f'<p class="hashtag">{html.escape(cf["hashtag"])}</p>', 0.3)
    choix = cf.get('partenaires')
    if choix and marque['partenaires']:
        liste = marque['partenaires'] if choix is True else \
            [p for nom in choix for p in marque['partenaires'] if p.get('nom') == nom]
        tuiles = ''.join(f'<div class="tuile"><img src="{marque.chemin(p["fichier"]).as_uri()}"></div>'
                         for p in liste if marque.chemin(p.get('fichier')))
        ajout(f'<p class="etiquette">{html.escape(cf.get("etiquette_partenaires", "Avec"))}</p>'
              f'<div class="tuiles">{tuiles}</div>', 0.3)
    deg = c.get('degrade') or {}
    haut_c, bas_c = deg.get('haut', c['fond_2']), deg.get('bas', c['fond'])
    lueur_c = deg.get('lueur', c.get('lueur'))
    lueur = (f'radial-gradient(60% 40% at 90% 95%, {lueur_c} 0%, transparent 70%), ' if lueur_c else '')
    css = f"""{marque.polices_css()}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: {L}px; height: {H}px; overflow: hidden; }}
body {{ background: {lueur}radial-gradient(120% 80% at 30% 8%, {haut_c} 0%, {bas_c} 62%);
       color: {c['texte']}; -webkit-font-smoothing: antialiased; }}
.zone {{ position: absolute; left: 90px; right: 90px; top: {haut}px; bottom: {H - bas}px; display: flex;
         flex-direction: column; align-items: center; justify-content: center; gap: 30px; text-align: center; }}
.a {{ opacity: 0; animation: entree .7s cubic-bezier(.2,.7,.2,1) forwards; display: flex; flex-direction: column;
      align-items: center; gap: 18px; }}
@keyframes entree {{ from {{ opacity: 0; transform: translateY(26px); }} to {{ opacity: 1; transform: none; }} }}
.pastille {{ background: {pastille or 'transparent'}; border-radius: 50%; padding: 22px; box-shadow: 0 12px 40px rgba(0,0,0,.35); }}
.pastille img {{ display: block; }}
.titre {{ font-family: {marque.pile('titres', 'serif')}; font-weight: {marque.graisse('titres')}; font-size: 76px; line-height: 1.1; }}
.second {{ font-family: {marque.pile('arabe')}; font-size: 50px; line-height: 1.5; color: {c['seconde_langue']}; }}
.lien {{ font-family: {marque.pile('texte')}; font-weight: 600; font-size: 40px; letter-spacing: .16em; color: {c['accent_2']}; }}
.hashtag {{ font-family: {marque.pile('texte')}; font-size: 34px; color: {c['texte_doux']}; }}
.etiquette {{ font-family: {marque.pile('texte')}; font-weight: 600; font-size: 26px; letter-spacing: .3em;
              text-transform: uppercase; color: {c['accent_2']}; }}
.tuiles {{ display: flex; flex-wrap: wrap; justify-content: center; gap: 16px; max-width: 900px; }}
.tuile {{ background: #fff; border-radius: 18px; height: 120px; padding: 14px 18px; display: flex; align-items: center; }}
.tuile img {{ max-height: 92px; max-width: 220px; }}
"""
    corps = f'<div class="zone">{"".join(elements)}</div>'
    return f'<html><head><meta charset="utf-8"><style>{css}</style></head><body>{corps}</body></html>', d


def rendre_integre(marque, cache):
    cf = marque['carton_fin']
    L, H, _, _ = marque.vertical
    page_html, fin_anim = page_carton(marque)
    signature = json.dumps([page_html, cf], sort_keys=True, default=str)
    cle = hashlib.sha1(signature.encode()).hexdigest()[:10]
    mp4 = cache / f'carton-{cle}.mp4'
    duree = max(float(cf.get('duree', 4.6)), fin_anim + 1.4)
    if not mp4.exists():
        fichier = cache / f'carton-{cle}.html'
        fichier.write_text(page_html, encoding='utf-8')
        ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'image2pipe', '-framerate', str(IPS), '-c:v', 'mjpeg',
                               '-i', '-', '-c:v', 'libx264', '-crf', '18', '-preset', 'fast', '-pix_fmt', 'yuv420p',
                               str(mp4)], stdin=subprocess.PIPE)
        with navigateur.onglet(L, H) as p:
            navigateur.charger(p, fichier)
            for i in range(int(round(duree * IPS))):
                p.evaluate(f'document.getAnimations().forEach(a => {{ a.pause(); a.currentTime = {1000 * i / IPS}; }})')
                ff.stdin.write(p.screenshot(type='jpeg', quality=92))
        ff.stdin.close()
        ff.wait()
        fichier.unlink()
    # un tic à chaque entrée d'élément après le logo
    tics = [float(x) + 0.1 for x in re.findall(r'animation-delay:([\d.]+)s', page_html)]
    return {'mp4': mp4, 'duree': duree, 'saut_images': 0, 'battements': [], 'tics': tics[1:]}


def appeler_extension(marque, specification, *args):
    fichier, fonction = specification.rsplit(':', 1)
    chemin = marque.chemin(fichier)
    if not chemin:
        raise FileNotFoundError(f'extension introuvable : {fichier}')
    spec = importlib.util.spec_from_file_location(f'extension_{chemin.stem}', chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, fonction)(marque, *args)


def carton(marque, cache):
    """Renvoie le carton de fin à coller après le montage, ou None."""
    cf = marque['carton_fin']
    if cf.get('type') == 'aucun':
        return None
    if cf.get('type') == 'extension':
        r = appeler_extension(marque, cf['extension'], cache)
        r.setdefault('saut_images', 0)
        r.setdefault('battements', [])
        r.setdefault('tics', [])
        r['mp4'] = Path(r['mp4'])
        return r
    return rendre_integre(marque, cache)
