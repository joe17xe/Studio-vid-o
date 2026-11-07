"""Essai de bout en bout, sans vrai rush, avec la marque d'un projet.

Fabrique dans <travail> (par défaut <studio>/.essai/, jamais versionné) :
  - a-roll/essai.mp4 : une voix de synthèse (espeak-ng) qui lit six phrases neutres, séparées
    par des blancs de 0,7 à 2,4 s, sur une image horizontale où le temps du rush est incrusté
    (on voit ainsi où tombent les coupes) ;
  - b-roll/ : les trois premiers fichiers du b-roll du projet, sinon trois images de test ;
  - montages/essai.json : accroche, traductions, B-roll.
Puis monte la vidéo (page de review), et l'exporte avec --exporter.
"""

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.io import wavfile

from .marque import Marque, fichiers_police

SR = 48000
PHRASES = [
    {'fr': 'Bonjour, ceci est un essai du studio.', 'ar': 'مرحباً، هذه تجربة للاستوديو.',
     'en': 'Hello, this is a studio test.', 'blanc': 0.9},
    {'fr': 'Les blancs entre les phrases sont coupés.', 'ar': 'تُحذف الفراغات بين الجمل.',
     'en': 'The gaps between sentences are cut.', 'blanc': 1.6},
    {'fr': 'Les sous-titres suivent la voix, mot par mot.', 'ar': 'الترجمة تتبع الصوت، كلمة بكلمة.',
     'en': 'Subtitles follow the voice, word by word.', 'blanc': 0.7},
    {'fr': 'Des plans d’illustration couvrent l’image.', 'dit': "Des plans d'illustration couvrent l'image.",
     'ar': 'لقطات توضيحية تغطي الصورة.', 'en': 'Illustration shots cover the picture.', 'blanc': 2.4},
    {'fr': 'La musique reste sous la voix.', 'ar': 'تبقى الموسيقى تحت الصوت.',
     'en': 'The music stays under the voice.', 'blanc': 1.1},
    {'fr': 'Merci, et à bientôt.', 'ar': 'شكراً، وإلى اللقاء.', 'en': 'Thank you, see you soon.', 'blanc': 1.5},
]
BLANC_DEBUT = 1.4


def lancer(*cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def couleur(hexa):
    return tuple(int(hexa[i:i + 2], 16) for i in (1, 3, 5))


def degrade(chemin, largeur, hauteur, c1, c2, texte, police):
    """Une image de test : dégradé aux couleurs de la marque et un libellé."""
    a, b = np.array(couleur(c1), float), np.array(couleur(c2), float)
    y = np.linspace(0, 1, hauteur)[:, None, None]
    x = np.linspace(0, 1, largeur)[None, :, None]
    img = Image.fromarray((a * (1 - (x + y) / 2) + b * (x + y) / 2).astype(np.uint8))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(police, int(hauteur / 9))
    d.text((largeur / 2, hauteur / 2), texte, font=f, anchor='mm', fill=(255, 255, 255))
    img.save(chemin, quality=92)


def voix(travail):
    morceaux, durees = [np.zeros(int(BLANC_DEBUT * SR))], []
    tmp = travail / '.phrase.wav'
    for p in PHRASES:
        lancer('espeak-ng', '-v', 'fr', '-s', 150, '-p', 45, '-w', tmp, p.get('dit', p['fr']))
        sr, x = wavfile.read(tmp)
        x = x.astype(float) / 32768
        x = np.interp(np.arange(0, len(x) * SR / sr) * sr / SR, np.arange(len(x)), x)
        morceaux += [x * 0.7, np.zeros(int(p['blanc'] * SR))]
        durees.append(len(x) / SR)
    tmp.unlink()
    signal = np.concatenate(morceaux)
    signal += np.random.default_rng(1).standard_normal(len(signal)) * 10 ** (-58 / 20)
    wavfile.write(travail / '.voix.wav', SR, (signal * 32767).astype(np.int16))
    return len(signal) / SR, durees


def ttf(marque):
    for role in ('texte', 'sous_titres', 'titres'):
        try:
            for _, _, f in fichiers_police(marque['polices'][role], marque):
                if str(f).endswith('.ttf'):
                    return str(f)
        except Exception:
            continue
    return 'DejaVuSans.ttf'


def rush(travail, duree, marque, police):
    c = marque.couleurs
    fond = travail / '.fond.jpg'
    degrade(fond, 1920, 1080, c['fond'], c['fond_2'], '', police)
    texte = (f"drawtext=fontfile={police}:text='RUSH D’ESSAI':fontcolor=white:fontsize=46:"
             "x=(w-text_w)/2:y=330:box=1:boxcolor=black@0.5:boxborderw=18,"
             f"drawtext=fontfile={police}:text='rush %{{pts\\:hms}}':fontcolor=white:fontsize=54:"
             "x=(w-text_w)/2:y=420:box=1:boxcolor=black@0.5:boxborderw=18")
    sortie = travail / 'a-roll' / 'essai.mp4'
    lancer('ffmpeg', '-v', 'error', '-y', '-loop', 1, '-framerate', 30, '-t', f'{duree:.3f}', '-i', fond,
           '-i', travail / '.voix.wav', '-vf', texte, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', 22,
           '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-shortest', sortie)
    (travail / '.voix.wav').unlink()
    fond.unlink()


def brolls(studio, travail, marque, police):
    projet = sorted(f for f in (studio / 'b-roll').glob('*')
                    if f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.mp4', '.mov')) if (studio / 'b-roll').exists() else []
    noms = []
    for i in range(3):
        if i < len(projet):
            cible = travail / 'b-roll' / projet[i].name
            shutil.copy(projet[i], cible)
        else:
            c = marque.couleurs
            cible = travail / 'b-roll' / f'test-{i + 1}.jpg'
            degrade(cible, 1600, 2400, (c['accent'], c['accent_2'], c['fond_2'])[i], c['fond'], f'B-ROLL {i + 1}', police)
        noms.append(f'b-roll/{cible.name}')
    return noms


def montage(travail, durees, noms_broll, marque):
    debuts, t = [], 0.0
    for d in durees:
        debuts.append(t)
        t += d + 0.28
    secondes = marque['langues'].get('secondes', [])
    principale = marque['langues']['principale']
    phrases = [{'texte': p['fr'], 'mots': [], **{lg: p[lg] for lg in secondes if lg in p}} for p in PHRASES]
    accroche = {principale: 'Essai du studio', 'ar': 'تجربة الاستوديو', 'en': 'Studio test', 'duree': 2.4}
    m = {'rush': 'a-roll/essai.mp4', 'titre': f'Essai du studio · {marque["nom"]}', 'reglages': {},
         'segments': None, 'transcription': {'phrases': phrases},
         'accroche': {k: v for k, v in accroche.items() if k in [principale, *secondes, 'duree']},
         'broll': [{'a': round(debuts[2] + 0.3, 2), 'fichier': noms_broll[0], 'duree': 3.0, 'note': 'essai 1'},
                   {'a': round(debuts[3] + 0.2, 2), 'fichier': noms_broll[1], 'duree': 3.0, 'note': 'essai 2'},
                   {'a': round(debuts[4] + 0.3, 2), 'fichier': noms_broll[2], 'duree': 2.6, 'note': 'essai 3'}],
         'flous': []}
    (travail / 'montages' / 'essai.json').write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding='utf-8')
    (travail / 'texte.txt').write_text(' '.join(p['fr'] for p in PHRASES), encoding='utf-8')


def essai(studio, travail=None, exporter=False, whisper=False):
    from .montage import monter
    studio = Path(studio).resolve()
    travail = Path(travail or studio / '.essai').resolve()
    marque = Marque(studio)
    if travail.exists():
        shutil.rmtree(travail)
    for d in ('a-roll', 'b-roll', 'montages', 'export'):
        (travail / d).mkdir(parents=True)
    police = ttf(marque)
    duree, durees = voix(travail)
    rush(travail, duree, marque, police)
    montage(travail, durees, brolls(studio, travail, marque, police), marque)
    print(f'rush d’essai : {duree:.1f} s, {len(PHRASES)} phrases, {len(PHRASES)} blancs à couper')

    class Args:
        texte = None if whisper else str(travail / 'texte.txt')
        recouper = retranscrire = False
        modele = None
    monter('a-roll/essai.mp4', studio, Args, travail)
    if exporter:
        Args.texte = None
        Args.exporter = True
        monter('a-roll/essai.mp4', studio, Args, travail)
    return travail
