"""La page de review : la vidéo, la transcription cliquable, les coupes, les B-roll, les images
clés, les alertes et les points à vérifier ; aux couleurs de la marque."""

import html
import subprocess
from datetime import date

import numpy as np
from PIL import Image, ImageDraw


def _hms(t):
    return f'{int(t // 60)}:{t % 60:04.1f}'


def _ffmpeg(*args):
    subprocess.run(['ffmpeg', '-hide_banner', '-v', 'error', '-y', *map(str, args)], check=True)


def forme_onde(rush, segments, info, sortie, marque):
    """Forme d'onde du rush ; les blancs coupés sont grisés."""
    c = marque.couleurs
    brut = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(rush), '-ac', '1', '-ar', '8000', '-f', 's16le', '-'],
                          capture_output=True, check=True).stdout
    x = np.frombuffer(brut, np.int16).astype(float) / 32768
    largeur, hauteur = 1600, 180
    img = Image.new('RGB', (largeur, hauteur), '#FFFFFF')
    d = ImageDraw.Draw(img)
    total = info['duree']
    t = 0.0
    for a, b in segments + [[total, total]]:
        if a > t:
            d.rectangle([t / total * largeur, 0, a / total * largeur, hauteur], fill='#E6E6E2')
        t = b
    pas = max(1, len(x) // largeur)
    for i in range(largeur):
        bloc = x[i * pas:(i + 1) * pas]
        if len(bloc):
            h = min(1.0, np.abs(bloc).max() * 1.6) * (hauteur / 2 - 6)
            garde = any(a <= i / largeur * total <= b for a, b in segments)
            d.line([i, hauteur / 2 - h, i, hauteur / 2 + h], fill=c['fond_2'] if garde else '#B5B5AE')
    img.save(sortie)


def images_cles(video, instants, dossier):
    sortie = []
    for t in instants:
        nom = f'image-{t:06.2f}.jpg'
        _ffmpeg('-ss', f'{t:.3f}', '-i', video, '-frames:v', 1, '-vf', 'scale=360:-1', '-q:v', 3, dossier / nom)
        sortie.append((t, nom))
    return sortie


def ecrire_review(m, nom, dossier, video, mesures, cles, brolls, alertes, phrases, segments, info, marque, commande):
    from .montage import sonder, vers_montage
    e = html.escape
    c = marque.couleurs
    sonie, crete = mesures
    blancs_coupes, t = [], 0.0
    for a, b in segments + [[info['duree'], info['duree']]]:
        if a - t > 0.01:
            blancs_coupes.append((t, a))
        t = b
    total_coupe = sum(b - a for a, b in blancs_coupes)
    duree_finale = sonder(dossier / video)['duree']
    secondes = marque['langues'].get('secondes', [])

    lignes_tr = []
    for p in phrases:
        mots = ' '.join(f'<span class="mot" data-t="{vers_montage(w["debut"], segments):.2f}">{e(w["mot"])}</span>'
                        for w in p['mots'])
        trad = ''
        for lg in secondes:
            if p.get(lg):
                trad += f'<div class="trad"{" dir=rtl" if marque.sens(lg) == "rtl" else ""}><b>{lg}</b> {e(p[lg])}</div>'
            else:
                trad += f'<div class="trad vide">{lg} : à écrire dans le fichier de montage (champ « {lg} »)</div>'
        debut = vers_montage(p['mots'][0]['debut'], segments) if p['mots'] else 0
        lignes_tr.append(f'<div class="phrase"><span class="t" data-t="{debut:.2f}">{_hms(debut)}</span> {mots}{trad}</div>')
    coupes = ''.join(f'<tr><td>{i + 1}</td><td>{_hms(a)} → {_hms(b)}</td><td>{b - a:.2f} s</td>'
                     f'<td class="t" data-t="{vers_montage(b, segments):.2f}">{_hms(vers_montage(b, segments))}</td></tr>'
                     for i, (a, b) in enumerate(blancs_coupes))
    gardes = ''.join(f'<tr><td>{i + 1}</td><td>{_hms(a)} → {_hms(b)}</td><td>{b - a:.2f} s</td>'
                     f'<td class="t" data-t="{vers_montage(a, segments):.2f}">{_hms(vers_montage(a, segments))}</td></tr>'
                     for i, (a, b) in enumerate(segments))
    br = ''.join(f'<tr><td class="t" data-t="{b["a"]:.2f}">{_hms(b["a"])}</td><td>{e(b["fichier"])}</td>'
                 f'<td>{float(b["duree"]):.1f} s</td><td>{e(b.get("note", ""))}</td></tr>' for b in brolls) \
        or '<tr><td colspan="4">Aucun B-roll : à placer dans le fichier de montage (« broll »).</td></tr>'
    grille = ''.join(f'<figure data-t="{t:.2f}"><img src="{n}" alt="image à {_hms(t)}"><figcaption>{_hms(t)}</figcaption>'
                     f'</figure>' for t, n in cles)
    al = ''.join(f'<div class="alerte">{e(a)}</div>' for a in alertes)
    liste = ''.join(f'<label><input type="checkbox"> {e(x)}</label>' for x in marque.controles)
    source = m['transcription'].get('source', '')
    r = m['reglages']
    css = f"""
:root {{ --fond: {c['fond']}; --fond2: {c['fond_2']}; --accent: {c['accent']}; --accent2: {c['accent_2']};
        --texte: {c['texte']}; --papier: #FAFAF7; --ligne: #E4E2DC; --encre: #1E2420; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--papier); color: var(--encre); font: 16px/1.55 system-ui, sans-serif; }}
header {{ background: radial-gradient(120% 140% at 20% 0%, var(--fond2), var(--fond)); color: var(--texte); padding: 28px 16px; }}
header .in, main {{ max-width: 1120px; margin: 0 auto; }}
h1, h2 {{ font-family: Georgia, serif; font-weight: 600; }}
h1 {{ margin: 0 0 6px; font-size: 30px; }} h2 {{ margin: 36px 0 12px; font-size: 23px; }}
.statut {{ display: inline-block; background: var(--accent2); color: var(--fond); border-radius: 99px; padding: 2px 12px;
          font-size: 13px; font-weight: 600; letter-spacing: .04em; }}
main {{ padding: 0 16px 60px; }}
.chiffres {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }}
.chiffres div {{ background: rgba(255,255,255,.1); border-radius: 12px; padding: 8px 14px; }}
.chiffres b {{ display: block; font-size: 20px; }}
.haut {{ display: grid; grid-template-columns: minmax(0, 360px) minmax(0, 1fr); gap: 28px; margin-top: 28px; }}
@media (max-width: 760px) {{ .haut {{ grid-template-columns: 1fr; }} }}
video {{ width: 100%; border-radius: 16px; background: #000; position: sticky; top: 12px; }}
.phrase {{ padding: 10px 0; border-bottom: 1px solid var(--ligne); }}
.mot {{ cursor: pointer; border-radius: 4px; padding: 0 1px; }}
.mot:hover, .mot.lu {{ background: color-mix(in oklab, var(--accent2) 30%, white); }}
.trad {{ margin-top: 4px; color: #4A5350; }} .trad b {{ font-size: 12px; text-transform: uppercase; color: #8A918E; }}
.trad.vide {{ font-style: italic; font-size: 14px; color: #8A918E; }}
table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
th, td {{ text-align: left; padding: 7px 8px; border-bottom: 1px solid var(--ligne); vertical-align: top; }}
.t {{ font-variant-numeric: tabular-nums; cursor: pointer; color: color-mix(in oklab, var(--accent2) 70%, black);
      white-space: nowrap; font-weight: 600; }}
.onde {{ width: 100%; border-radius: 10px; border: 1px solid var(--ligne); }}
.grille {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; }}
.grille figure {{ margin: 0; cursor: pointer; }} .grille img {{ width: 100%; border-radius: 10px; display: block; }}
.grille figcaption {{ font-size: 13px; }}
.alerte {{ background: #FFF4E5; border-left: 4px solid var(--accent2); padding: 10px 14px; border-radius: 8px; margin: 8px 0; }}
.liste label {{ display: block; padding: 5px 0; }}
code {{ background: #EEECE6; padding: 2px 6px; border-radius: 6px; font-size: 14px; overflow-wrap: anywhere; }}
.legende {{ font-size: 13px; color: #6B716E; }}
"""
    page = f"""<!doctype html>
<html lang="{marque['langues']['principale']}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Review · {e(nom)}</title><style>{css}</style></head><body>
<header><div class="in">
<span class="statut">À VALIDER · rien n’est publié</span>
<h1>{e(m.get('titre') or nom)}</h1>
<div>{e(marque['nom'])} · rush <code style="background:rgba(255,255,255,.12);color:inherit">{e(m['rush'])}</code> · préparé le {date.today().strftime('%d/%m/%Y')}</div>
<div class="chiffres">
<div><b>{_hms(duree_finale)}</b>durée finale</div>
<div><b>{_hms(info['duree'])}</b>rush</div>
<div><b>{len(blancs_coupes)} blancs</b>{total_coupe:.1f} s coupées</div>
<div><b>{len(brolls)}</b>plans B-roll</div>
<div><b>{sonie:.1f} LUFS</b>son (cible {marque['son']['sonie_cible']:g})</div>
<div><b>{crete:.1f} dBTP</b>crête (≤ {marque['son']['crete_max']:g})</div>
</div></div></header>
<main>
{al}
<div class="haut">
<div><video id="v" src="{video}" controls playsinline preload="metadata"></video>
<p class="legende">Aperçu de travail. La version finale est exportée après validation.</p></div>
<div><h2 style="margin-top:0">Transcription</h2>
<p class="legende">Cliquer un mot pour y aller dans la vidéo. Source : {e(source)}. Les corrections se font dans
<code>montages/{e(nom)}.json</code>, puis on relance le montage.</p>
{''.join(lignes_tr)}</div></div>
<h2>Les coupes</h2>
<img class="onde" src="coupes.png" alt="Forme d’onde du rush, blancs coupés en gris">
<p class="legende">En couleur, ce qui est gardé ; en gris, les blancs coupés. Réglages : seuil {r['seuil_db']} dB,
blanc d’au moins {r['blanc_min']} s, marges {r['marge_avant']} s avant et {r['marge_apres']} s après.</p>
<table><tr><th>#</th><th>Blanc coupé (rush)</th><th>Durée</th><th>Dans le montage</th></tr>{coupes or '<tr><td colspan="4">Aucun blanc.</td></tr>'}</table>
<h2>Les morceaux gardés</h2>
<table><tr><th>#</th><th>Rush</th><th>Durée</th><th>Début dans le montage</th></tr>{gardes}</table>
<h2>Les B-roll</h2>
<table><tr><th>À</th><th>Fichier</th><th>Durée</th><th>Note</th></tr>{br}</table>
<h2>Images clés</h2>
<div class="grille">{grille}</div>
<h2>À vérifier avant de valider</h2>
<div class="liste">{liste}</div>
<h2>Valider</h2>
<p>Quand tout est bon, dire à Claude « c’est validé, exporte », ou lancer :</p>
<p><code>{e(commande)}</code></p>
</main>
<script>
const v = document.getElementById('v');
document.querySelectorAll('[data-t]').forEach(el => el.addEventListener('click', () => {{
  v.currentTime = parseFloat(el.dataset.t) + 0.01; v.play(); }}));
const mots = [...document.querySelectorAll('.mot')];
v.addEventListener('timeupdate', () => mots.forEach(m => m.classList.toggle('lu',
  Math.abs(v.currentTime - parseFloat(m.dataset.t)) < 0.25)));
</script>
</body></html>"""
    (dossier / 'index.html').write_text(page, encoding='utf-8')
