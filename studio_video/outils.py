"""Vérifie que chaque outil est installé ET fonctionne, par un petit test réel.
Avec --studio, vérifie aussi la marque du projet (polices téléchargeables, logos présents)."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy.io import wavfile

os.environ.setdefault('HF_HUB_DISABLE_XET', '1')


def lancer(*cmd):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, check=True)


def installer():
    lancer(sys.executable, '-m', 'pip', 'install', '-q', 'faster-whisper', 'av<16', 'yt-dlp', 'playwright')
    manquants = [p for p in ('ffmpeg', 'espeak-ng') if not shutil.which(p)]
    if manquants:
        subprocess.run(['apt-get', 'install', '-y', *manquants], check=False)


def verifier_tout(studio=None, url=None, installer_avant=False):
    if installer_avant:
        installer()
    tmp = Path(tempfile.mkdtemp(prefix='studio-outils-'))
    resultats = []

    def test(nom, role):
        def deco(f):
            try:
                resultats.append(('OK', nom, role, f()))
            except Exception as e:
                resultats.append(('KO', nom, role, (str(e).strip().splitlines() or [type(e).__name__])[0][:220]))
            return f
        return deco

    @test('FFmpeg', 'coupes, recadrage, export')
    def _():
        v = lancer('ffmpeg', '-version').stdout.split()[2]
        sortie = tmp / 'test.mp4'
        lancer('ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=1080x1920:r=30:d=1', '-f', 'lavfi',
               '-i', 'sine=f=440:d=1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
               '-movflags', '+faststart', sortie)
        info = lancer('ffprobe', '-v', 'error', '-show_entries', 'stream=codec_name,width,height',
                      '-of', 'csv=p=0', sortie).stdout.split()
        assert info[0].startswith('h264,1080,1920') and 'aac' in info, info
        return f'version {v}, encodage 1080×1920 H.264/AAC faststart réussi'

    @test('Détection des blancs', 'ffmpeg silencedetect')
    def _():
        from . import montage
        sr = 48000
        bip = 0.3 * np.sin(2 * np.pi * 300 * np.arange(sr) / sr)
        wavfile.write(tmp / 'blanc.wav', sr, (np.concatenate([bip, np.zeros(sr), bip]) * 32767).astype(np.int16))
        debuts, fins = montage.blancs(tmp / 'blanc.wav', -35, 0.45)
        assert len(debuts) == 1 and abs(debuts[0] - 1.0) < 0.05 and abs(fins[0] - 2.0) < 0.05, (debuts, fins)
        return f'blanc trouvé de {debuts[0]:.2f} à {fins[0]:.2f} s (attendu 1,00 → 2,00)'

    @test('Chromium (Playwright)', 'rendu des sous-titres, de l’accroche et du carton')
    def _():
        from PIL import Image
        from . import navigateur
        page = tmp / 'p.html'
        page.write_text("<html><body style='margin:0;background:transparent'><p style='font:60px sans-serif;"
                        "color:#B96A4F' dir='rtl'>مرحبا Studio</p></body></html>", encoding='utf-8')
        with navigateur.onglet(400, 200) as p:
            p.goto(page.as_uri())
            p.screenshot(path=str(tmp / 'p.png'), omit_background=True)
        alpha = np.array(Image.open(tmp / 'p.png'))[:, :, 3]
        assert (alpha > 0).sum() > 500, 'rien n’a été dessiné'
        return 'texte latin et arabe rendus en PNG transparent'

    @test('Musique synthétisée', 'studio_video/musique.py')
    def _():
        from . import musique
        sonie, crete = musique.ecrire(str(tmp / 's.wav'), 30.0, {'souffles': [5.0, 15.0], 'tics': [7.0], 'fin': 30.0})
        assert -17.5 < sonie < -13.5 and crete <= -1.4, (sonie, crete)
        return f'30 s synthétisées : {sonie:.1f} LUFS, crête {crete:.1f} dBFS (le montage final est porté à −14)'

    @test('espeak-ng', 'voix de synthèse pour les essais (jamais pour publier)')
    def _():
        lancer('espeak-ng', '-v', 'fr', '-w', tmp / 'v.wav', 'Bonjour, ceci est un essai du studio.')
        sr, x = wavfile.read(tmp / 'v.wav')
        assert len(x) / sr > 0.8
        return f'{len(x) / sr:.1f} s de voix française'

    @test('Whisper (faster-whisper)', 'transcription mot à mot')
    def _():
        import faster_whisper
        from . import montage
        if not (tmp / 'v.wav').exists():
            raise RuntimeError('espeak-ng manquant : pas de voix de test')
        try:
            phrases = montage.transcrire_whisper(tmp / 'v.wav', 'small', 'fr')
        except montage.ModeleIndisponible as e:
            raise RuntimeError(f'faster-whisper {faster_whisper.__version__} installé, mais modèle indisponible : '
                               f'autoriser {", ".join(montage.HOTES_WHISPER)}') from e
        mots = [m['mot'] for p in phrases for m in p['mots']]
        assert mots, 'aucun mot reconnu'
        return f'« {" ".join(mots)} » ({len(mots)} mots horodatés)'

    @test('yt-dlp', 'récupérer une vidéo de référence (analyse interne)')
    def _():
        v = lancer(sys.executable, '-m', 'yt_dlp', '--version').stdout.strip()
        if not url:
            return f'version {v} (ajouter --url <lien> pour tester un téléchargement)'
        lancer(sys.executable, '-m', 'yt_dlp', '-q', '--no-playlist', '-f', 'mp4/best', '-o', str(tmp / 'ref.%(ext)s'), url)
        return f'version {v}, {next(tmp.glob("ref.*")).stat().st_size / 1e6:.1f} Mo téléchargés'

    if studio:
        @test('Marque du projet', f'{Path(studio) / "marque.json"}')
        def _():
            from .marque import Marque, fichiers_police
            m = Marque(studio)
            if not m.present:
                raise RuntimeError('marque.json absent : lancer « studio-video nouveau »')
            n = sum(len(fichiers_police(spec, m)) for spec in m['polices'].values() if isinstance(spec, dict))
            manquants = [x for x in [m['logo']] + [p.get('fichier') for p in m['partenaires']] if x and not m.chemin(x)]
            if manquants:
                raise RuntimeError(f'fichiers introuvables : {", ".join(manquants)}')
            return f'« {m["nom"]} » : {n} fichiers de police, logos présents, seconde langue : {m.seconde or "aucune"}'

    largeur = max(len(n) for _, n, _, _ in resultats)
    for etat, nom, role, detail in resultats:
        print(f'{"✅" if etat == "OK" else "❌"} {nom:<{largeur}}  {detail}\n   {"":<{largeur}}  ({role})')
    shutil.rmtree(tmp, ignore_errors=True)
    return all(e == 'OK' for e, *_ in resultats)
