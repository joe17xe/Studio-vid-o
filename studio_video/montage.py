"""Monter une vidéo à partir d'un rush (A-roll), aux couleurs d'un projet.

  1. les blancs du rush sont repérés (ffmpeg silencedetect) et coupés, avec des marges ;
  2. la voix est transcrite mot à mot (Whisper, via faster-whisper) ;
  3. les sous-titres s'affichent mot par mot, avec une seconde langue sous chaque phrase
     quand sa traduction est écrite dans le fichier de montage ;
  4. les plans B-roll couvrent l'image, la voix continue dessous ; flous de plaques ;
  5. la musique de la marque passe sous la voix, qui reste devant ; −14 LUFS ;
  6. le carton de fin de la marque termine la vidéo ;
  7. une page de review est préparée dans export/<nom>-review/ ;
  8. après validation, --exporter écrit export/<nom>.mp4 (H.264/AAC, faststart).

Tout l'habillage vient de <studio>/marque.json (voir marque.py). Le fichier de montage
<studio>/montages/<nom>.json est créé au premier passage ; on y corrige la transcription,
on écrit les traductions, on place les B-roll, l'accroche, les flous, et on relance.
"""

import html
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.io import wavfile
from scipy.ndimage import maximum_filter1d, minimum_filter1d, uniform_filter1d

from . import carton as carton_mod
from . import musique, navigateur
from .marque import CACHE, Marque
from .review import ecrire_review, forme_onde, images_cles

# Téléchargement classique des modèles Hugging Face (sans le protocole « xet », qui passe par
# d'autres adresses que celles qu'on autorise d'habitude dans un environnement cloud).
os.environ.setdefault('HF_HUB_DISABLE_XET', '1')

SR = musique.SR
IPS = 30
HOTES_WHISPER = ['huggingface.co', 'cdn-lfs.hf.co', 'cdn-lfs-us-1.hf.co', 'cas-bridge.xethub.hf.co',
                 'us.aws.cdn.hf.co']
IMAGES = ('.jpg', '.jpeg', '.png', '.webp')


# --- petits outils -------------------------------------------------------------------

def ffmpeg(*args):
    subprocess.run(['ffmpeg', '-hide_banner', '-v', 'error', '-y', *map(str, args)], check=True)


def sonder(fichier):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                        'format=duration:stream=codec_type,width,height,r_frame_rate',
                        '-of', 'json', str(fichier)], capture_output=True, text=True, check=True)
    info = json.loads(r.stdout)
    video = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
    audio = any(s['codec_type'] == 'audio' for s in info['streams'])
    n, d = (video['r_frame_rate'].split('/') if video else ('30', '1'))
    return {'duree': float(info['format']['duration']), 'audio': audio,
            'largeur': video and video.get('width'), 'hauteur': video and video.get('height'),
            'ips': float(n) / float(d or 1)}


def mesurer(fichier):
    """Sonie intégrée (LUFS) et crête vraie (dBTP), mesurées par ffmpeg (EBU R128)."""
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(fichier), '-af', 'ebur128=peak=true',
                        '-f', 'null', '-'], capture_output=True, text=True)
    resume = r.stderr[r.stderr.rfind('Summary:'):]
    i = re.search(r'I:\s+(-?[\d.]+) LUFS', resume)
    p = re.search(r'Peak:\s+(-?[\d.]+) dBFS', resume)
    return float(i.group(1)), float(p.group(1))


def hms(t):
    return f'{int(t // 60)}:{t % 60:04.1f}'


def srt_temps(t):
    ms = int(round(t * 1000))
    return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}'


# --- 1. les blancs -------------------------------------------------------------------

def blancs(rush, seuil_db, duree_min):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(rush), '-vn', '-af',
                        f'silencedetect=noise={seuil_db}dB:d={duree_min}', '-f', 'null', '-'],
                       capture_output=True, text=True)
    debuts = [float(x) for x in re.findall(r'silence_start: (-?[\d.]+)', r.stderr)]
    fins = [float(x) for x in re.findall(r'silence_end: (-?[\d.]+)', r.stderr)]
    return debuts, fins


def parole_depuis_blancs(debuts, fins, total, reglages, ips):
    """Les morceaux de parole à garder, avec les marges, calés sur les images du rush."""
    fins = fins + [total] * (len(debuts) - len(fins))
    parole, t = [], 0.0
    for a, b in zip(debuts, fins):
        if a > t:
            parole.append([t, a])
        t = b
    if t < total:
        parole.append([t, total])
    image = 1 / ips
    gardes = []
    for a, b in parole:
        a = max(0.0, a - reglages['marge_avant'])
        b = min(total, b + reglages['marge_apres'])
        a, b = np.floor(a / image) * image, min(total, np.ceil(b / image) * image)
        if gardes and a <= gardes[-1][1] + 0.05:
            gardes[-1][1] = max(gardes[-1][1], b)
        elif b - a >= 0.25:
            gardes.append([a, b])
    return [[round(float(a), 3), round(float(b), 3)] for a, b in gardes]


def segments_gardes(rush, reglages, info):
    debuts, fins = blancs(rush, reglages['seuil_db'], reglages['blanc_min'])
    return parole_depuis_blancs(debuts, fins, info['duree'], reglages, info['ips'])


def vers_montage(t, segments):
    """Temps du rush → temps du montage (un instant coupé se cale au début du morceau suivant)."""
    decalage = 0.0
    for a, b in segments:
        if t < a:
            return decalage
        if t <= b:
            return decalage + t - a
        decalage += b - a
    return decalage


def duree_montage(segments):
    return sum(b - a for a, b in segments)


# --- 2. la transcription -------------------------------------------------------------

class ModeleIndisponible(RuntimeError):
    pass


def transcrire_whisper(rush, modele, langue):
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise ModeleIndisponible('faster-whisper n’est pas installé : pip install faster-whisper "av<16"') from e
    local = CACHE / 'modeles' / modele          # un modèle déposé à la main passe avant le réseau
    try:
        m = WhisperModel(str(local) if local.is_dir() else modele, device='cpu', compute_type='int8')
    except Exception as e:
        raise ModeleIndisponible(
            f'le modèle Whisper « {modele} » n’a pas pu être chargé ({type(e).__name__}).\n'
            f'  Il se télécharge depuis Hugging Face : autoriser les hôtes {", ".join(HOTES_WHISPER)},\n'
            f'  ou déposer le dossier du modèle dans {local},\n'
            f'  ou fournir le texte dit avec --texte (horodatage estimé).') from e
    segments, _ = m.transcribe(str(rush), language=langue, word_timestamps=True, beam_size=5,
                               condition_on_previous_text=False)
    phrases = []
    for s in segments:
        mots = [{'mot': w.word.strip(), 'debut': round(w.start, 3), 'fin': round(w.end, 3)}
                for w in s.words or [] if w.word.strip()]
        if mots:
            phrases.append({'texte': s.text.strip(), 'mots': mots})
    return phrases


def mots_de(texte):
    """Les mots, coupés aux espaces ordinaires : « 6 000 » ou « objectif : » (insécables) restent entiers."""
    return [m for m in re.split(r'[ \t\n]+', texte) if m]


def repartir(mots, intervalles):
    """Horodatage estimé : chaque mot reçoit une part du temps de parole, selon sa longueur."""
    poids = np.array([len(m) + 1.5 for m in mots], dtype=float)
    bornes = np.concatenate([[0], np.cumsum(poids)]) / poids.sum()
    total = sum(b - a for a, b in intervalles)

    def instant(f):
        reste = f * total
        for a, b in intervalles:
            if reste <= b - a:
                return a + reste
            reste -= b - a
        return intervalles[-1][1]
    return [{'mot': m, 'debut': round(instant(bornes[i]), 3), 'fin': round(instant(bornes[i + 1]) - 0.02, 3)}
            for i, m in enumerate(mots)]


def transcrire_texte(texte, segments, reglages):
    """Sans Whisper : le texte dit est connu, on le répartit sur les morceaux de parole."""
    phrases = [p.strip() for p in re.split(r'(?<=[.!?…])\s+', texte.strip()) if p.strip()]
    parole = [[a + reglages['marge_avant'], b - reglages['marge_apres']] for a, b in segments]
    if len(phrases) == len(parole):        # une phrase par prise de parole : le cas d'un texte lu
        return [{'texte': p, 'mots': repartir(mots_de(p), [iv])} for p, iv in zip(phrases, parole)]
    mots = repartir(mots_de(' '.join(phrases)), parole)
    sortie, k = [], 0
    for p in phrases:
        n = len(mots_de(p))
        sortie.append({'texte': p, 'mots': mots[k:k + n]})
        k += n
    return sortie


def texte_de(phrase):
    """Le texte d'une phrase (« texte » ; « fr » dans les fichiers de montage d'avant le moteur)."""
    return phrase.get('texte', phrase.get('fr', ''))


# --- 3. les sous-titres --------------------------------------------------------------

def cartes(phrases, segments, reglages):
    """Découpe chaque phrase en cartes de quelques mots, en temps du montage."""
    sortie = []
    for ip, p in enumerate(phrases):
        groupe = []
        mots = [dict(m, d=vers_montage(m['debut'], segments), f=vers_montage(m['fin'], segments))
                for m in p['mots']]
        for k, m in enumerate(mots):
            texte = ' '.join(x['mot'] for x in groupe + [m])
            if groupe and len(texte) > reglages['caracteres_par_carte']:
                sortie.append({'phrase': ip, 'mots': groupe})
                groupe = []
            groupe.append(m)
            if len(groupe) >= reglages['mots_par_carte'] or m['mot'][-1] in ',.;:!?…' or k == len(mots) - 1:
                sortie.append({'phrase': ip, 'mots': groupe})
                groupe = []
    for i, c in enumerate(sortie):
        c['debut'] = 0.0 if i == 0 else c['mots'][0]['d']   # texte dès la 1re image (couverture)
        suivante = sortie[i + 1]['mots'][0]['d'] if i + 1 < len(sortie) else None
        fin = c['mots'][-1]['f'] + 0.35
        c['fin'] = suivante if suivante is not None and suivante - fin < 0.6 else fin
    return sortie


def css_calques(marque):
    c = marque.couleurs
    st = marque['sous_titres']
    L, H, haut, bas = marque.vertical
    seconde = marque.seconde
    role_sec = marque.role_pour('texte', seconde) if seconde else 'texte'
    pile_seconde = marque.pile(role_sec)
    return f"""{marque.polices_css()}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: {L}px; height: {H}px; background: transparent; overflow: hidden; }}
.st {{ position: absolute; left: 60px; right: 60px; bottom: {H - bas}px; display: flex; justify-content: center; }}
.bloc {{ background: {c['fond_sous_titres']}; border-radius: {st.get('rayon', 30)}px; padding: 22px 34px 24px;
        max-width: {L - 120}px; display: flex; flex-direction: column; align-items: center; gap: 12px;
        text-align: center; box-shadow: 0 8px 40px rgba(0,0,0,.3); }}
.prin {{ font-family: {marque.pile('sous_titres')}; font-weight: {marque.graisse('sous_titres')};
        font-size: {st['taille']}px; line-height: 1.2; color: {c['texte']}; }}
.prin span {{ display: inline-block; }}
.prin .avenir {{ opacity: .62; }}
.prin .actif {{ color: {c['mot_actif']}; transform: scale({st.get('agrandissement_actif', 1.06)}); }}
.sec {{ font-family: {pile_seconde}; font-weight: {marque.graisse(role_sec)};
       font-size: {st.get('taille_seconde', 42)}px; line-height: 1.6; color: {c['seconde_langue']}; text-wrap: balance; }}
.accroche {{ position: absolute; left: 0; right: 0; top: 0; height: 760px;
            background: linear-gradient(180deg, {c['voile']} 0%, transparent 100%); }}
.accroche .zone {{ position: absolute; left: 80px; right: 80px; top: {haut + 20}px; display: flex; flex-direction: column;
                  align-items: center; gap: 18px; text-align: center; }}
.accroche .prin {{ font-family: {marque.pile('titres', 'serif')}; font-weight: {marque.graisse('titres')}; font-size: 72px;
                  line-height: 1.12; }}
.accroche .sec {{ font-size: 50px; color: {c['accent_2']}; }}
"""


def calques(cartes_, phrases, accroche, marque, dossier):
    """Un PNG par état des sous-titres (une carte, un mot actif) et l'accroche ; rendus par Chromium."""
    dossier.mkdir(parents=True, exist_ok=True)
    css = css_calques(marque)
    seconde = marque.seconde
    principale = marque['langues']['principale']
    attr_prin = marque.attributs('sous_titres', principale)
    attr_sec = marque.attributs('texte', seconde) if seconde else ''
    motif = carton_mod.motif_svg(marque)
    agrandissement = float(marque['sous_titres'].get('agrandissement_actif', 1.06))
    L, H, _, _ = marque.vertical
    etats = []
    with navigateur.onglet(L, H) as onglet:
        def photo(nom, corps):
            fichier = dossier / f'{nom}.html'
            fichier.write_text(f'<html><head><meta charset="utf-8"><style>{css}</style></head><body>{corps}</body></html>',
                               encoding='utf-8')
            onglet.goto(fichier.as_uri())
            onglet.wait_for_function("document.fonts.status === 'loaded'")
            # chaque mot garde autour de lui la place de son agrandissement : le mot actif ne mord
            # jamais sur l'espace voisin, et la carte ne bouge pas d'un mot actif à l'autre
            onglet.evaluate("""k => document.querySelectorAll('.prin span').forEach(s => {
                const w = s.getBoundingClientRect().width / (s.classList.contains('actif') ? k : 1);
                s.style.marginInline = (w * (k - 1) / 2).toFixed(2) + 'px'; })""", agrandissement)
            onglet.screenshot(path=str(dossier / f'{nom}.png'), omit_background=True)
            fichier.unlink()
            return dossier / f'{nom}.png'

        vide = photo('vide', '')
        for ic, c in enumerate(cartes_):
            trad = (phrases[c['phrase']].get(seconde) or '').strip() if seconde else ''
            for k in range(len(c['mots'])):
                mots = ' '.join(f'<span class="{"actif" if j == k else "dit" if j < k else "avenir"}">'
                                f'{html.escape(m["mot"])}</span>' for j, m in enumerate(c['mots']))
                bas = f'{motif}<p class="sec"{attr_sec}>{html.escape(trad)}</p>' if trad else ''
                debut = c['debut'] if k == 0 else c['mots'][k]['d']
                fin = c['fin'] if k == len(c['mots']) - 1 else c['mots'][k + 1]['d']
                etats.append((debut, fin, photo(f'c{ic:03d}-{k:02d}',
                                                f'<div class="st"><div class="bloc"><p class="prin"{attr_prin}>{mots}</p>{bas}</div></div>')))
        image_accroche = None
        if accroche:
            lignes = ''.join(f'<p class="{"prin" if lg == principale else "sec"}"'
                             f'{marque.attributs("titres" if lg == principale else "texte", lg)}>'
                             f'{accroche[lg]}</p>' for lg in [principale] + marque['langues'].get('secondes', [])
                             if accroche.get(lg))
            # compatibilité : « fr » pour la langue principale
            if not lignes and accroche.get('fr'):
                lignes = f'<p class="prin">{accroche["fr"]}</p>'
            image_accroche = photo('accroche', f'<div class="accroche"><div class="zone">{lignes}</div></div>')
    return etats, vide, image_accroche


def sequence_sous_titres(etats, vide, duree, dossier):
    """Une image par trame du montage (liens vers les PNG d'état) : timing exact à la trame près."""
    if dossier.exists():
        shutil.rmtree(dossier)
    dossier.mkdir(parents=True)
    n = int(round(duree * IPS))
    trames = [vide] * n
    for debut, fin, png in etats:
        for i in range(int(round(debut * IPS)), min(n, int(round(fin * IPS)))):
            trames[i] = png
    for i, png in enumerate(trames):
        os.symlink(png, dossier / f'{i:05d}.png')
    return dossier / '%05d.png'


def ecrire_srt(cartes_, phrases, langues, dossier):
    principale, secondes = langues
    fr = ''.join(f'{i + 1}\n{srt_temps(c["debut"])} --> {srt_temps(c["fin"])}\n'
                 f'{" ".join(m["mot"] for m in c["mots"])}\n\n' for i, c in enumerate(cartes_))
    (dossier / f'sous-titres-{principale}.srt').write_text(fr, encoding='utf-8')
    for lg in secondes:
        blocs = []
        for ip, p in enumerate(phrases):
            cs = [c for c in cartes_ if c['phrase'] == ip]
            if p.get(lg) and cs:
                blocs.append((cs[0]['debut'], cs[-1]['fin'], p[lg]))
        if blocs:
            (dossier / f'sous-titres-{lg}.srt').write_text(
                ''.join(f'{i + 1}\n{srt_temps(a)} --> {srt_temps(b)}\n{t}\n\n' for i, (a, b, t) in enumerate(blocs)),
                encoding='utf-8')


# --- 4. les B-roll -------------------------------------------------------------------

def chemin_media(nom, travail, marque):
    for base in (travail, travail / 'b-roll'):
        if (base / nom).exists():
            return (base / nom).resolve()
    trouve = marque.chemin(nom)
    if trouve:
        return trouve
    raise FileNotFoundError(f'B-roll introuvable : {nom} (chercher dans {travail / "b-roll"})')


def preparer_broll(b, travail, marque, cache):
    """Chaque B-roll devient un clip vertical à 30 i/s, sans son ; une photo devient un lent zoom."""
    L, H, _, _ = marque.vertical
    source = chemin_media(b['fichier'], travail, marque)
    d = float(b['duree'])
    sortie = cache / f'broll-{source.stem}-{b.get("debut", 0)}-{d}-{b.get("cadrage_x", 0.5)}.mp4'
    cx = b.get('cadrage_x', 0.5)
    retouche = b.get('etalonnage', 'eq=contrast=1.06:saturation=1.12')
    alerte = None
    if source.suffix.lower() in IMAGES:
        largeur, hauteur = Image.open(source).size
        if hauteur < 1600 and largeur < 1600:
            alerte = f'photo petite ({largeur}×{hauteur}) : elle sera agrandie, prendre l’original HD'
        n = int(round(d * IPS))
        filtre = (f'scale={2 * L}:{2 * H}:force_original_aspect_ratio=increase,crop={2 * L}:{2 * H}:(iw-{2 * L})*{cx}:(ih-{2 * H})/2,'
                  f"zoompan=z='1.0+0.07*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={L}x{H}:fps={IPS},"
                  f'{retouche},setsar=1,format=yuv420p')
        if not sortie.exists():
            ffmpeg('-loop', '1', '-framerate', IPS, '-t', d, '-i', source, '-vf', filtre, '-frames:v', n,
                   '-c:v', 'libx264', '-crf', 18, '-preset', 'fast', sortie)
    else:
        info = sonder(source)
        if (info['hauteur'] or 0) < 1080 and (info['largeur'] or 0) < 1920:
            alerte = f'vidéo en basse définition ({info["largeur"]}×{info["hauteur"]})'
        filtre = (f'scale={L}:{H}:force_original_aspect_ratio=increase,crop={L}:{H}:(iw-{L})*{cx}:(ih-{H})/2,'
                  f'{retouche},fps={IPS},setsar=1,format=yuv420p')
        if not sortie.exists():
            ffmpeg('-ss', b.get('debut', 0), '-t', d, '-i', source, '-an', '-vf', filtre,
                   '-c:v', 'libx264', '-crf', 18, '-preset', 'fast', sortie)
    return sortie, alerte


# --- 5. le son -----------------------------------------------------------------------

def lire_wav(fichier):
    sr, x = wavfile.read(fichier)
    x = x.astype(np.float64) / (32768.0 if x.dtype == np.int16 else 1.0)
    return x if x.ndim == 2 else np.stack([x, x], axis=1)


def limiteur(x, plafond_db):
    """Limiteur à anticipation simple : le gain baisse juste avant chaque crête, puis remonte."""
    plafond = 10 ** (plafond_db / 20)
    crete = maximum_filter1d(np.abs(x).max(axis=1), size=int(0.004 * SR))
    gain = np.minimum(1.0, plafond / np.maximum(crete, 1e-9))
    gain = minimum_filter1d(gain, size=int(0.01 * SR))
    gain = uniform_filter1d(gain, size=int(0.01 * SR))
    return x * np.minimum(gain, plafond / np.maximum(np.abs(x).max(axis=1), 1e-9))[:, None]


def parole_active(voix, duree):
    """Où la voix parle (enveloppe à 50 ms), élargi un peu avant et après."""
    n = int(duree * SR)
    e = np.sqrt(uniform_filter1d((voix[:n] ** 2).mean(axis=1), size=int(0.05 * SR)))
    actif = (20 * np.log10(e + 1e-9) > -45).astype(float)
    actif = maximum_filter1d(actif, size=int(0.6 * SR), origin=-int(0.1 * SR))
    return uniform_filter1d(actif, size=int(0.25 * SR))     # rampes douces


def composer_musique(marque, duree, cues):
    son = marque['son']
    if son.get('musique') == 'synthese':
        musique.graine(son.get('synthese', {}).get('graine', 2026))
        return musique.composer(duree, cues, son.get('synthese', {}).get('progression', 're_mineur'))
    if son.get('musique') == 'extension':
        return carton_mod.appeler_extension(marque, son['extension'], duree, cues)
    return None


def bande_son(voix_wav, duree_aroll, duree_totale, cues, marque, sortie):
    """Voix devant, musique de la marque dessous, puis pleine sur le carton de fin ; −14 LUFS."""
    son = marque['son']
    voix = lire_wav(voix_wav)
    n = int(duree_totale * SR)
    v = np.zeros((n, 2))
    v[:min(n, len(voix))] = voix[:n]
    v *= 10 ** ((son['voix_lufs'] - musique.sonie(v[:int(duree_aroll * SR)])) / 20)
    mix = v
    m = composer_musique(marque, duree_totale, cues)
    if m is not None:
        m = m[:n]
        m = np.vstack([m, np.zeros((n - len(m), 2))]) if len(m) < n else m
        actif = parole_active(v, duree_totale)
        sur_fin = np.clip((np.arange(n) / SR - duree_aroll + 0.3) / 0.6, 0, 1)    # carton : musique pleine
        db = son['musique_sous_voix_db'] * actif + son['musique_pause_db'] * (1 - actif)
        mix = v + m * (10 ** (db * (1 - sur_fin) / 20))[:, None]
    for _ in range(4):                       # sonie cible, crête sous le plafond (marge pour l'AAC)
        mix *= 10 ** ((son['sonie_cible'] - musique.sonie(mix)) / 20)
        mix = limiteur(mix, son['crete_max'] - 0.8)
    wavfile.write(sortie, SR, (np.clip(mix, -1, 1) * 32767).astype(np.int16))
    return musique.sonie(mix)


# --- l'enchaînement ------------------------------------------------------------------

def charger_montage(rush, travail, marque, args):
    nom = rush.stem
    fichier = travail / 'montages' / f'{nom}.json'
    fichier.parent.mkdir(parents=True, exist_ok=True)
    if fichier.exists():
        m = json.loads(fichier.read_text(encoding='utf-8'))
    else:
        m = {'rush': str(rush.relative_to(travail)) if rush.is_relative_to(travail) else str(rush),
             'titre': nom.replace('-', ' ').replace('_', ' ').capitalize(),
             'reglages': {}, 'segments': None, 'transcription': None,
             'accroche': None, 'broll': [], 'flous': []}
    m['reglages'] = {**marque['montage'], **{k: v for k, v in marque['sous_titres'].items()
                                             if k in ('mots_par_carte', 'caracteres_par_carte')},
                     **m.get('reglages', {})}
    if getattr(args, 'modele', None):
        m['reglages']['modele'] = args.modele
    return nom, fichier, m


def monter(rush, studio, args, travail=None):
    """studio : le dossier de la marque (marque.json) ; travail : celui des rushes et exports
    (par défaut le même ; l'essai utilise un dossier à part)."""
    marque = Marque(studio)
    travail = Path(travail or studio).resolve()
    L, H, _, _ = marque.vertical
    rush = Path(rush)
    rush = rush if rush.is_absolute() else (travail / rush if (travail / rush).exists() else Path.cwd() / rush)
    rush = rush.resolve()
    info = sonder(rush)
    if not info['audio']:
        sys.exit(f'{rush.name} n’a pas de piste son : un A-roll doit contenir la voix.')
    nom, fichier, m = charger_montage(rush, travail, marque, args)
    reglages = m['reglages']
    principale = marque['langues']['principale']
    secondes = marque['langues'].get('secondes', [])
    cache = travail / '.cache' / nom
    cache.mkdir(parents=True, exist_ok=True)

    # 1. les blancs
    if getattr(args, 'recouper', False) or not m.get('segments'):
        m['segments'] = segments_gardes(rush, reglages, info)
        print(f'1. blancs : {len(m["segments"])} morceaux de parole gardés sur {info["duree"]:.1f} s de rush')
    segments = m['segments']
    duree_aroll = round(duree_montage(segments) * IPS) / IPS

    # 2. la transcription (gardée dans le fichier de montage, avec les corrections de l'équipe)
    transcrit = any(p.get('mots') for p in (m.get('transcription') or {}).get('phrases', []))
    if getattr(args, 'retranscrire', False) or getattr(args, 'texte', None) or not transcrit:
        anciennes = (m.get('transcription') or {}).get('phrases', [])
        if args.texte:
            texte = Path(args.texte).read_text(encoding='utf-8')
            m['transcription'] = {'source': 'texte fourni, horodatage estimé sans Whisper',
                                  'phrases': transcrire_texte(texte, segments, reglages)}
        else:
            try:
                phrases = transcrire_whisper(rush, reglages['modele'], principale)
            except ModeleIndisponible as e:
                fichier.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding='utf-8')
                sys.exit(f'2. transcription impossible : {e}')
            m['transcription'] = {'source': f'Whisper {reglages["modele"]} (faster-whisper), à relire',
                                  'phrases': phrases}
        # les traductions déjà écrites restent : même phrase, ou même rang
        par_texte = {texte_de(p): p for p in anciennes}
        meme_decoupe = len(anciennes) == len(m['transcription']['phrases'])
        for k, p in enumerate(m['transcription']['phrases']):
            ancienne = par_texte.get(texte_de(p)) or (anciennes[k] if meme_decoupe else {})
            for lg in secondes:
                if ancienne.get(lg):
                    p[lg] = ancienne[lg]
            for lg in secondes:
                p.setdefault(lg, '')
        print(f'2. transcription : {len(m["transcription"]["phrases"])} phrases ({m["transcription"]["source"]})')
    for p in m['transcription']['phrases']:          # compatibilité : « fr » → « texte »
        if 'texte' not in p and 'fr' in p:
            p['texte'] = p.pop('fr')
    fichier.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding='utf-8')
    phrases = m['transcription']['phrases']

    # 3. les sous-titres
    cartes_ = cartes(phrases, segments, reglages)
    etats, vide, image_accroche = calques(cartes_, phrases, m.get('accroche'), marque, cache / 'calques')
    motif = sequence_sous_titres(etats, vide, duree_aroll, cache / 'trames')
    sec = marque.seconde
    print(f'3. sous-titres : {len(cartes_)} cartes, {len(etats)} états mot par mot'
          + (f', {sec} ' + ('présent' if any(p.get(sec) for p in phrases) else 'à écrire') if sec else ''))

    # 4. les B-roll
    brolls, alertes, clips = sorted(m.get('broll', []), key=lambda b: b['a']), [], []
    for b in brolls:
        if b['a'] + float(b['duree']) > duree_aroll + 0.01:
            alertes.append(f'B-roll {b["fichier"]} : dépasse la fin de la parole ({hms(duree_aroll)}), raccourci.')
            b = dict(b, duree=max(0.5, duree_aroll - b['a']))
        clip, alerte = preparer_broll(b, travail, marque, cache)
        if alerte:
            alertes.append(f'B-roll {b["fichier"]} : {alerte}.')
        clips.append((b, clip))
    print(f'4. B-roll : {len(clips)} plans')

    # 6. le carton de fin (avant le son : ses repères font partie de la bande-son)
    fin = carton_mod.carton(marque, cache)
    if fin:
        duree_fin = sonder(fin['mp4'])['duree'] - fin['saut_images'] / IPS
    else:
        duree_fin = 0.0
    duree_totale = duree_aroll + duree_fin

    # 5. la voix coupée, puis la bande-son
    voix = cache / 'voix.wav'
    morceaux = ''.join(f'[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS,afade=t=in:d=0.012,'
                       f'afade=t=out:st={b - a - 0.015:.3f}:d=0.015[a{i}];' for i, (a, b) in enumerate(segments))
    ffmpeg('-i', rush, '-filter_complex',
           morceaux + ''.join(f'[a{i}]' for i in range(len(segments))) +
           f'concat=n={len(segments)}:v=0:a=1,highpass=f=80,'
           'acompressor=threshold=0.1:ratio=3:attack=8:release=120:makeup=1.5,'
           f'aresample={SR},aformat=channel_layouts=stereo[v]',
           '-map', '[v]', '-c:a', 'pcm_s16le', voix)
    cues = {'battements': [duree_aroll + b for b in (fin or {}).get('battements', [])],
            'souffles': [b['a'] for b, _ in clips] + ([duree_aroll] if fin else []),
            'tics': [duree_aroll + t for t in (fin or {}).get('tics', [])], 'fin': duree_totale}
    mix = cache / 'mix.wav'
    sonie = bande_son(voix, duree_aroll, duree_totale, cues, marque, mix)
    musique_txt = {'synthese': 'musique synthétisée dessous', 'extension': 'musique du projet dessous'}.get(
        marque['son'].get('musique'), 'sans musique')
    print(f'5. son : voix devant, {musique_txt}, {sonie:.1f} LUFS')

    # 8. l'image : rush coupé et recadré, B-roll, flous, sous-titres, accroche, carton ; avec le son
    cx = reglages['cadrage_x']
    entrees = ['-i', rush]
    filtre = [''.join(f'[0:v]trim={a}:{b},setpts=PTS-STARTPTS[v{i}];' for i, (a, b) in enumerate(segments)) +
              ''.join(f'[v{i}]' for i in range(len(segments))) +
              f'concat=n={len(segments)}:v=1:a=0,scale={L}:{H}:force_original_aspect_ratio=increase,'
              f'crop={L}:{H}:(iw-{L})*{cx}:(ih-{H})/2,{reglages["etalonnage"]},fps={IPS},setsar=1,'
              f'format=yuv420p,trim=end={duree_aroll:.4f}[base]']
    courant, k = '[base]', 1
    for i, (b, clip) in enumerate(clips):
        entrees += ['-i', clip]
        fin_b = b['a'] + float(b['duree'])
        filtre.append(f'[{k}:v]setpts=PTS-STARTPTS+{b["a"]}/TB[b{i}];{courant}[b{i}]overlay=0:0:eof_action=pass:'
                      f"enable='between(t,{b['a']},{fin_b - 0.001:.3f})'[sb{i}]")
        courant, k = f'[sb{i}]', k + 1
    for i, f in enumerate(m.get('flous', [])):
        filtre.append(f'{courant}split[fa{i}][fb{i}];[fb{i}]crop={f["l"]}:{f["h"]}:{f["x"]}:{f["y"]},boxblur=24:3[fc{i}];'
                      f"[fa{i}][fc{i}]overlay={f['x']}:{f['y']}:enable='between(t,{f.get('de', 0)},{f.get('a', 9999)})'[sf{i}]")
        courant = f'[sf{i}]'
    entrees += ['-framerate', IPS, '-i', motif]
    filtre.append(f'[{k}:v]format=rgba[st];{courant}[st]overlay=0:0:format=auto:eof_action=pass[sst]')
    courant, k = '[sst]', k + 1
    if image_accroche:
        d = float(m['accroche'].get('duree', 2.5))
        entrees += ['-loop', 1, '-framerate', IPS, '-t', d, '-i', image_accroche]
        filtre.append(f'[{k}:v]format=rgba,fade=t=out:st={d - 0.4}:d=0.4:alpha=1[acc];'
                      f'{courant}[acc]overlay=0:0:format=auto:eof_action=pass[sacc]')
        courant, k = '[sacc]', k + 1
    if fin:
        entrees += ['-i', fin['mp4']]
        filtre.append(f'[{k}:v]trim=start_frame={fin["saut_images"]},setpts=PTS-STARTPTS,fps={IPS},setsar=1,'
                      f'format=yuv420p[fin];{courant}format=yuv420p[img];[img][fin]concat=n=2:v=1:a=0[sortie]')
        k += 1
    else:
        filtre.append(f'{courant}format=yuv420p[sortie]')
    entrees += ['-i', mix]
    final = getattr(args, 'exporter', False)
    export = travail / 'export'
    dossier_review = export / f'{nom}-review'
    dossier_review.mkdir(parents=True, exist_ok=True)
    sortie = export / f'{nom}.mp4' if final else dossier_review / 'apercu.mp4'
    qualite = (['-preset', 'slow', '-crf', 20] if final else ['-preset', 'veryfast', '-crf', 23])
    ffmpeg(*entrees, '-filter_complex', ';'.join(filtre), '-map', '[sortie]', '-map', f'{k}:a',
           '-c:v', 'libx264', *qualite, '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-level', '4.1',
           '-c:a', 'aac', '-b:a', '160k', '-ar', SR, '-movflags', '+faststart', '-shortest', sortie)
    mesures = mesurer(sortie)
    print(f'8. {sortie} : {sonder(sortie)["duree"]:.1f} s, {sortie.stat().st_size / 1e6:.1f} Mo, '
          f'{mesures[0]:.1f} LUFS, crête {mesures[1]:.1f} dBTP')

    ecrire_srt(cartes_, phrases, (principale, secondes), dossier_review)
    if final:
        ffmpeg('-i', sortie, '-frames:v', 1, '-q:v', 2, export / f'{nom}-couverture.jpg')
        for srt in dossier_review.glob('sous-titres-*.srt'):
            shutil.copy(srt, export / f'{nom}-{srt.name}')
        return sortie

    # 7. la page de review
    instants = [0.0] + [b['a'] + float(b['duree']) / 2 for b, _ in clips]
    instants += [c['mots'][-1]['d'] for c in cartes_[1::max(1, len(cartes_) // 6)]]
    if fin:
        instants += [duree_aroll + min(2.6, duree_fin - 0.2)]
    instants = sorted({round(t, 2) for t in instants if t < duree_totale})
    for vieux in dossier_review.glob('image-*.jpg'):
        vieux.unlink()
    cles = images_cles(sortie, instants, dossier_review)
    forme_onde(rush, segments, info, dossier_review / 'coupes.png', marque)
    textes = [texte_de(p) for p in phrases] + [p.get(lg, '') for p in phrases for lg in secondes] + \
        [str(v) for v in (m.get('accroche') or {}).values()]
    for mot in marque['mentions_interdites']:
        if any(mot.lower() in t.lower() for t in textes):
            alertes.insert(0, f'Mention interdite par la marque : « {mot} » apparaît dans le texte. À retirer avant export.')
    if 'estimé' in m['transcription'].get('source', ''):
        alertes.insert(0, 'Horodatage estimé (sans Whisper) : vérifier que les sous-titres suivent bien la voix.')
    commande = f'studio-video monter {m["rush"]} --studio {studio}' + (f' --travail {travail}' if travail != Path(studio).resolve() else '') + ' --exporter'
    ecrire_review(m, nom, dossier_review, sortie.name, mesures, cles, brolls, alertes, phrases, segments, info,
                  marque, commande)
    print(f'7. page de review : {dossier_review / "index.html"}')
    return sortie
