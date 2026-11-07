"""Vidéos de référence : les récupérer pour une analyse interne, et mesurer leur montage.

  studio-video references telecharger <lien> [--nom mon-nom]
      yt-dlp, dans studio/references/videos/ (jamais versionné, jamais republié).
      Préférer un fichier fourni par l'équipe ; respecter les droits de l'auteur.
  studio-video references analyser references/videos/<fichier>.mp4
      Mesure ce qui se mesure (coupes, rythme, blancs, sonie, couleurs, débit de parole si
      Whisper est là) et écrit la fiche studio/references/notes/<nom>.md, avec la grille
      d'analyse à compléter à l'œil (typo, sous-titres, musique…). La planche d'images
      (une par plan) reste à côté de la vidéo, non versionnée.
"""

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image

from . import montage as monter
from .marque import Marque


def telecharger(lien, nom, studio):
    dossier = studio / 'references' / 'videos'
    dossier.mkdir(parents=True, exist_ok=True)
    modele = f'{nom}.%(ext)s' if nom else '%(uploader|ref)s-%(id)s.%(ext)s'
    print('Usage d’analyse interne uniquement : la vidéo n’est ni versionnée, ni republiée, ni montée.')
    r = subprocess.run([sys.executable, '-m', 'yt_dlp', '--no-playlist', '-f', 'bv*[height<=1920]+ba/b',
                        '--merge-output-format', 'mp4', '-o', str(dossier / modele), '--print', 'after_move:filepath',
                        lien], capture_output=True, text=True)
    if r.returncode:
        bloque = 'Forbidden' in r.stderr or 'ProxyError' in r.stderr or 'Tunnel' in r.stderr
        sys.exit('Téléchargement impossible' + (' : le réseau de cette session bloque ce site. Déposer la vidéo à la '
                                                'main dans studio/references/videos/, ou lancer la commande sur un '
                                                'ordinateur de l’équipe.' if bloque else f' :\n{r.stderr[-800:]}'))
    fichier = Path(r.stdout.strip().splitlines()[-1])
    print(f'→ {fichier}')
    return fichier


def coupes(video, ecart=6):
    """Changements de plan, coupes franches et fondus courts : on compare chaque image (en petit,
    en niveaux de gris) à celle d'il y a 0,2 s, et on garde les pics nets, espacés d'au moins 0,5 s."""
    info = monter.sonder(video)
    lw, lh = 72, 128
    brut = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), '-an', '-vf', f'fps=30,scale={lw}:{lh},format=gray',
                           '-f', 'rawvideo', '-'], capture_output=True, check=True).stdout
    f = np.frombuffer(brut, np.uint8).reshape(-1, lh, lw).astype(np.int16)
    d = np.zeros(len(f))
    d[ecart:] = np.abs(f[ecart:] - f[:-ecart]).mean(axis=(1, 2))
    seuil = max(9.0, 3 * np.median(d[ecart:]) if len(d) > ecart else 9.0)
    pics, rayon = [], 15
    for i in range(ecart, len(d)):
        if d[i] >= seuil and d[i] == d[max(0, i - rayon):i + rayon + 1].max():
            if not pics or i - pics[-1] >= rayon:
                pics.append(i)
    # le pic tombe au milieu du changement : la coupe est ~ecart/2 images plus tôt
    return [round(max(0, i - ecart / 2) / 30, 2) for i in pics if i / 30 < info['duree'] - 0.1]


def image_a(video, t, taille=None):
    vf = ['-vf', f'scale={taille}:-1'] if taille else []
    brut = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.3f}', '-i', str(video), '-frames:v', '1', *vf,
                           '-f', 'image2pipe', '-c:v', 'png', '-'], capture_output=True, check=True).stdout
    from io import BytesIO
    return Image.open(BytesIO(brut)).convert('RGB')


def palette(images, n=6):
    """Couleurs dominantes de l'ensemble des plans (quantification), avec leur part."""
    pixels = np.concatenate([np.asarray(im.resize((90, 160))).reshape(-1, 3) for im in images])
    q = Image.fromarray(pixels.reshape(-1, 90, 3).astype(np.uint8)).quantize(n, method=Image.Quantize.MEDIANCUT)
    comptes = sorted(q.getcolors(), reverse=True)
    pal = q.getpalette()
    total = sum(c for c, _ in comptes)
    return [('#%02X%02X%02X' % tuple(pal[3 * i:3 * i + 3]), c / total) for c, i in comptes]


def proche_charte(hexa, charte):
    rgb = np.array([int(hexa[i:i + 2], 16) for i in (1, 3, 5)])
    if not charte:
        return '—'
    nom, ref = min(charte.items(), key=lambda kv: np.linalg.norm(rgb - [int(kv[1][i:i + 2], 16) for i in (1, 3, 5)]))
    d = np.linalg.norm(rgb - [int(ref[i:i + 2], 16) for i in (1, 3, 5)])
    return f'{nom} ({ref})' if d < 60 else '—'


def analyser(video, studio, sans_whisper=False):
    marque = Marque(studio)
    charte = {k: v for k, v in marque.couleurs.items() if isinstance(v, str) and re.fullmatch(r'#[0-9A-Fa-f]{6}', v)}
    video = video if video.is_absolute() else (studio / video if (studio / video).exists() else Path.cwd() / video)
    info = monter.sonder(video)
    nom = video.stem
    duree = info['duree']
    instants = coupes(video)
    bornes = [0.0] + instants + [duree]
    plans = np.diff(bornes)
    milieux = [(a + b) / 2 for a, b in zip(bornes, bornes[1:])]
    images = [image_a(video, t, 360) for t in milieux[:40]]
    # planche (non versionnée)
    w, h = images[0].size
    cols = min(8, len(images))
    planche = Image.new('RGB', (cols * w, -(-len(images) // cols) * h), 'white')
    for i, im in enumerate(images):
        planche.paste(im, ((i % cols) * w, (i // cols) * h))
    sortie_planche = video.with_name(f'{nom}-planche.jpg')
    planche.save(sortie_planche, quality=85)

    sonie, crete = monter.mesurer(video) if info['audio'] else (None, None)
    blancs_txt = '—'
    if info['audio']:
        debuts, fins = monter.blancs(video, -35, 0.45)
        fins += [duree] * (len(debuts) - len(fins))
        total_blanc = sum(b - a for a, b in zip(debuts, fins))
        blancs_txt = f'{len(debuts)} blancs de plus de 0,45 s, {total_blanc:.1f} s au total ({100 * total_blanc / duree:.0f} %)'
    debit = 'Whisper indisponible : à estimer à l’écoute'
    if info['audio'] and not sans_whisper:
        try:
            phrases = monter.transcrire_whisper(video, 'small', marque['langues']['principale'])
            n = sum(len(p['mots']) for p in phrases)
            debit = f'{n} mots, {60 * n / duree:.0f} mots par minute (langue supposée : français)'
        except monter.ModeleIndisponible:
            pass
    couleurs = palette(images)

    l = [f'# Référence : {nom}', '',
         f'Analysée le {date.today().strftime("%d/%m/%Y")}. Vidéo : `references/videos/{video.name}` '
         '(non versionnée, usage d’analyse interne). Source et auteur : _à noter_.', '',
         '## Mesures (automatiques)', '',
         '| Mesure | Valeur |', '|---|---|',
         f'| Durée | {duree:.1f} s |',
         f'| Format | {info["largeur"]}×{info["hauteur"]}, {info["ips"]:.0f} i/s |',
         f'| Plans | {len(plans)} (une coupe toutes les {duree / len(plans):.1f} s, {60 * (len(plans) - 1) / duree:.0f} coupes par minute) |',
         f'| Durée des plans | médiane {np.median(plans):.1f} s, de {plans.min():.1f} à {plans.max():.1f} s |',
         f'| Première coupe | {bornes[1]:.1f} s (l’accroche tient jusque-là) |',
         f'| Blancs dans le son | {blancs_txt} |',
         f'| Débit de parole | {debit} |',
         f'| Sonie | {f"{sonie:.1f} LUFS, crête {crete:.1f} dBTP" if sonie is not None else "pas de son"} |', '',
         '### Couleurs dominantes', '', '| Couleur | Part | Plus proche de la charte |', '|---|---|---|']
    l += [f'| `{c}` | {100 * p:.0f} % | {proche_charte(c, charte)} |' for c, p in couleurs]
    l += ['', '### Rythme des coupes', '',
          ' · '.join(f'{t:.1f}' for t in instants[:60]) or 'aucune coupe détectée (plan-séquence ou animation)', '',
          '## Grille d’analyse (à compléter en regardant la vidéo)', '',
          '| Critère | Ce qu’on voit | On le prend pour notre projet ? |', '|---|---|---|',
          '| Accroche (3 premières secondes) | | |',
          '| Typographie (polices, graisse, taille) | | |',
          '| Sous-titres : position, taille, mots par carte | | |',
          '| Sous-titres : mot actif (couleur, grossissement) | | |',
          '| Couleurs et étalonnage | | |',
          '| Rythme : une coupe par idée ? jump cuts ? | | |',
          '| Transitions (cut, fondu, zoom) | | |',
          '| B-roll : fréquence, durée, sujets | | |',
          '| Musique : style, niveau sous la voix | | |',
          '| Effets sonores | | |',
          '| Carton de fin, appel à l’action | | |',
          '| Ce qu’on ne prend surtout pas | | |', '',
          '## Ce qu’on retient', '', '- _trois idées au plus, reportées ensuite dans le guide de montage du projet_', '']
    notes = studio / 'references' / 'notes'
    notes.mkdir(parents=True, exist_ok=True)
    (notes / f'{nom}.md').write_text('\n'.join(l), encoding='utf-8')
    print(f'{len(plans)} plans, {sonie and f"{sonie:.1f} LUFS"} → {notes / f"{nom}.md"} ; planche : {sortie_planche}')
