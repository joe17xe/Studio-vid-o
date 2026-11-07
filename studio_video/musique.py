"""Musique synthétisée : originale, libre de droits, sans aucun échantillon externe.

Nappe d'accords, piano feutré, souffles de transition, tics, montée et impact, et, en
option, un battement de cœur (s'il y a des repères « battements »). Tout se règle depuis
marque.json (« son.synthese ») : progression d'accords, graine. La musique se compose
sur des repères (cues) : elle s'efface sous chaque battement et sous l'impact.
Niveau final : −14 LUFS visés (UIT-R BS.1770), crête ≤ −1,5 dBFS.
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, lfilter, sosfilt

SR = 48000
RNG = np.random.default_rng(2026)


def graine(n):
    global RNG
    RNG = np.random.default_rng(n)


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def piste(duree):
    return np.zeros((int(duree * SR) + SR, 2))


def poser(buffer, signal, t, gain=1.0, pan=0.0):
    """Ajoute un signal mono ou stéréo à partir de t (secondes), pan de -1 à 1."""
    i = int(t * SR)
    if i < 0:       # le signal commence avant le film (film court) : on n'en garde que la fin
        signal, i = signal[-i:], 0
    if signal.ndim == 1:
        g = np.array([np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)]) * np.sqrt(2)
        signal = signal[:, None] * g[None, :]
    n = min(len(signal), len(buffer) - i)
    if n > 0:
        buffer[i:i + n] += signal[:n] * gain


def passe_bas(x, f, ordre=2):
    return sosfilt(butter(ordre, f, 'low', fs=SR, output='sos'), x, axis=0)


def passe_haut(x, f, ordre=2):
    return sosfilt(butter(ordre, f, 'high', fs=SR, output='sos'), x, axis=0)


def balayage(x, f0, f1, q=1.2, bloc=256):
    """Passe-bande dont la fréquence glisse de f0 à f1 (filtre RBJ par blocs)."""
    y = np.zeros_like(x)
    zi = np.zeros(2)
    n = len(x)
    for debut in range(0, n, bloc):
        p = debut / max(n - 1, 1)
        f = f0 * (f1 / f0) ** p
        w = 2 * np.pi * f / SR
        alpha = np.sin(w) / (2 * q)
        b = np.array([alpha, 0, -alpha])
        a = np.array([1 + alpha, -2 * np.cos(w), 1 - alpha])
        y[debut:debut + bloc], zi = lfilter(b / a[0], a / a[0], x[debut:debut + bloc], zi=zi)
    return y


def enveloppe(n, attaque, relache):
    e = np.ones(n)
    a, r = int(attaque * SR), int(relache * SR)
    if a:
        e[:a] = np.linspace(0, 1, a) ** 2
    if r:
        e[-r:] *= np.linspace(1, 0, r) ** 2
    return e


# --- instruments -----------------------------------------------------------------

def coup(f0, f1, duree, decroissance):
    """Choc grave à hauteur glissante (corps d'un battement ou d'un impact)."""
    t = np.arange(int(duree * SR)) / SR
    f = f1 + (f0 - f1) * np.exp(-t / 0.035)
    phase = 2 * np.pi * np.cumsum(f) / SR
    env = (1 - np.exp(-t / 0.003)) * np.exp(-t / decroissance)
    return np.sin(phase) * env


def battement():
    """« Lub-dub » : corps grave (casque, enceinte) + « toc » dans les médiums et
    clic court, pour rester audible sur le haut-parleur d'un téléphone."""
    def temps(f0, f1, dec, gain):
        corps = coup(f0, f1, 0.35, dec)
        harmo = coup(f0 * 2.3, f1 * 2.3, 0.35, dec * 0.8) * 0.5
        toc = coup(f0 * 3.6, f1 * 3.6, 0.35, 0.03) * 0.95
        tac = coup(f0 * 7.0, f1 * 7.0, 0.35, 0.016) * 0.6
        frappe = coup(f0 * 11.0, f1 * 11.0, 0.35, 0.012) * 0.3
        # harmoniques de saturation : l'oreille reconstitue le grave (fondamentale
        # absente) même sur un haut-parleur de téléphone qui ne le reproduit pas
        grain = passe_haut(passe_bas(np.tanh(corps * 5), 1400), 280) * 0.8
        s = passe_bas(corps + harmo + toc + tac + frappe, 1600) + grain
        n = int(0.014 * SR)
        s[:n] += balayage(RNG.standard_normal(n), 2600, 1300, q=0.9) * enveloppe(n, 0.001, 0.011) * 0.4
        return s * gain
    lub, dub = temps(64, 42, 0.07, 1.0), temps(78, 50, 0.05, 0.72)
    sortie = np.zeros(int(0.7 * SR))
    sortie[:len(lub)] += lub
    i = int(0.21 * SR)
    sortie[i:i + len(dub)] += dub[:len(sortie) - i]
    return sortie


def nappe(notes, duree, attaque=1.4, relache=2.2, brillance=1700):
    """Accord tenu : voix désaccordées, synthèse additive douce, ouverture stéréo."""
    n = int((duree + relache) * SR)
    t = np.arange(n) / SR
    sortie = np.zeros((n, 2))
    for note in notes:
        for desaccord, pan in ((-7, -0.7), (0, 0.0), (7, 0.7)):
            f = midi(note) * 2 ** (desaccord / 1200)
            voix = np.zeros(n)
            for k in range(1, 11):
                if f * k > 6000:
                    break
                voix += np.sin(2 * np.pi * f * k * t + RNG.uniform(0, 2 * np.pi)) / k ** 1.35
            g = np.array([np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)])
            sortie += voix[:, None] * g[None, :]
    env = enveloppe(n, attaque, relache)
    return passe_bas(sortie * env[:, None], brillance) / (len(notes) * 3)


def piano(note, velocite=1.0, duree=2.6):
    """Piano feutré : partiels légèrement inharmoniques, aigus qui s'éteignent vite."""
    f = midi(note)
    n = int(duree * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for k in range(1, 9):
        fk = f * k * np.sqrt(1 + 0.0004 * k * k)
        if fk > 9000:
            break
        s += np.sin(2 * np.pi * fk * t) / k ** 1.5 * np.exp(-t * k ** 0.7 / 1.6)
    s *= 1 - np.exp(-t / 0.004)
    marteau = passe_bas(RNG.standard_normal(int(0.015 * SR)), 1800) * enveloppe(int(0.015 * SR), 0.001, 0.012) * 0.06
    s[:len(marteau)] += marteau
    return passe_bas(s, 3200) * velocite * enveloppe(n, 0.0, 0.3)


def souffle(duree=0.9):
    n = int(duree * SR)
    s = balayage(RNG.standard_normal(n), 300, 2200, q=0.7)
    return s * np.sin(np.linspace(0, np.pi, n)) ** 2


def montee(duree=2.0):
    n = int(duree * SR)
    t = np.arange(n) / SR
    bruit = balayage(RNG.standard_normal(n), 400, 7000, q=1.4)
    ton = np.sin(2 * np.pi * np.cumsum(np.linspace(180, 760, n)) / SR) * 0.25
    return (bruit + ton) * (t / duree) ** 2.2


def impact():
    s = coup(58, 34, 2.2, 0.55) * 1.0
    n = int(0.5 * SR)
    bruit = passe_bas(RNG.standard_normal(n), 900) * np.exp(-np.arange(n) / SR / 0.09) * 0.5
    s[:n] += bruit
    return s


def trait(duree=0.32):
    """Coup de feutre qui barre un mot : souffle étroit qui monte, attaque franche."""
    n = int(duree * SR)
    s = balayage(RNG.standard_normal(n), 1800, 3400, q=1.6)
    return s * enveloppe(n, 0.015, 0.09)


def tic():
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 1180 * t) + 0.35 * np.sin(2 * np.pi * 2360 * t)) * np.exp(-t / 0.018)


def reverb(x, duree=2.8, predelai=0.02):
    n = int(duree * SR)
    t = np.arange(n) / SR
    ir = RNG.standard_normal((n, 2)) * np.exp(-6.9 * t / duree)[:, None]
    ir = passe_bas(ir, 4500)
    ir = np.vstack([np.zeros((int(predelai * SR), 2)), ir])
    ir /= np.sqrt((ir ** 2).sum(axis=0))
    return np.stack([fftconvolve(x[:, c], ir[:, c])[:len(x)] for c in range(2)], axis=1)


def attenuation(n, instants, profondeur_db, maintien, relache, attaque=0.02):
    """Gain de « ducking » : la musique s'efface sous chaque événement puis revient."""
    d = np.zeros(n)
    for t0 in instants:
        a, b = int((t0 - attaque) * SR), min(n, int((t0 + maintien + 6 * relache) * SR))
        t = np.arange(max(a, 0), b) / SR - t0
        forme = np.where(t < 0, 1 + t / attaque, np.where(t < maintien, 1.0, np.exp(-(t - maintien) / relache)))
        d[max(a, 0):b] = np.maximum(d[max(a, 0):b], np.clip(forme, 0, 1))
    return 10 ** (-profondeur_db * d / 20)


def sonie(x):
    """Sonie intégrée en LUFS (UIT-R BS.1770-4 : pondération K, fenêtres de 400 ms, double seuil)."""
    k = lfilter([1.53512485958697, -2.69169618940638, 1.19839281085285],
                [1.0, -1.69065929318241, 0.73248077421585], x, axis=0)
    k = lfilter([1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621], k, axis=0)
    bloc, pas = int(0.4 * SR), int(0.1 * SR)
    z = np.array([(k[i:i + bloc] ** 2).mean(axis=0).sum() for i in range(0, len(k) - bloc + 1, pas)])
    z = z[-0.691 + 10 * np.log10(z + 1e-12) > -70]
    seuil = -0.691 + 10 * np.log10(z.mean()) - 10
    return -0.691 + 10 * np.log10(z[-0.691 + 10 * np.log10(z) > seuil].mean())


# --- composition -------------------------------------------------------------------

# Progressions : un accord toutes les 4 secondes (60 bpm) ; nappe (accords) et arpèges du piano.
PROGRESSIONS = {
    # Ré mineur : Dm – B♭ – F – C (i–VI–III–VII), résolution sur Dm
    're_mineur': {'accords': [[50, 57, 62, 65], [46, 53, 58, 62], [53, 57, 60, 65], [48, 55, 60, 64]],
                  'arpeges': [[62, 65, 69, 74], [58, 62, 65, 70], [60, 65, 69, 72], [60, 64, 67, 72]],
                  'resolution': [50, 57, 62, 65, 69]},
    # Fa majeur : F – C – Dm – B♭ (I–V–vi–IV), lumineux, résolution sur F
    'fa_majeur': {'accords': [[53, 60, 65, 69], [48, 55, 60, 64], [50, 57, 62, 65], [46, 53, 58, 62]],
                  'arpeges': [[65, 69, 72, 77], [60, 64, 67, 72], [62, 65, 69, 74], [58, 62, 65, 70]],
                  'resolution': [53, 60, 65, 69, 72]},
    # Sol majeur : G – Em – C – D (I–vi–IV–V), chaleureux, résolution sur G
    'sol_majeur': {'accords': [[55, 59, 62, 67], [52, 55, 59, 64], [48, 55, 60, 64], [50, 54, 57, 62]],
                   'arpeges': [[67, 71, 74, 79], [64, 67, 71, 76], [60, 64, 67, 72], [62, 66, 69, 74]],
                   'resolution': [55, 59, 62, 67, 71]},
}
ACCORDS = PROGRESSIONS['re_mineur']['accords']
ARPEGES = PROGRESSIONS['re_mineur']['arpeges']


SONIE_CIBLE = -14.0     # LUFS, la référence des plateformes sociales
CRETE_MAX = -1.5        # dBFS


def composer(duree, cues, progression='re_mineur'):
    """cues : dict avec 'battements', 'souffles', 'traits', 'tics', 'montee', 'impact', 'fin'.
    'traits', 'montee' et 'impact' sont facultatifs (les Reels courts s'en passent).
    Deux bus : la musique (nappe, piano), qui s'efface sous chaque battement, et
    les effets (battements, souffles, traits, tics, montée, impact)."""
    prog = PROGRESSIONS[progression]
    accords, arpeges = prog['accords'], prog['arpeges']
    seche, envoi = piste(duree), piste(duree)          # bus musique
    fx_seche, fx_envoi = piste(duree), piste(duree)    # bus effets
    montee_t, impact_t = cues.get('montee'), cues.get('impact')
    repere = impact_t if impact_t is not None else float('inf')   # avant / après l'impact

    # nappe : entre en fondu à 3 s, s'étoffe après l'impact, se résout à la fin
    t = 2.0
    i = 0
    while t < cues['fin'] - 4:
        accord = accords[i % 4]
        riche = t >= repere
        notes = accord + ([accord[0] + 12] if riche else [])
        voix = nappe(notes, 4.0, brillance=2300 if riche else 1600)
        poser(envoi, voix, t, gain=0.55 if t >= 6 else 0.3)
        poser(seche, voix, t, gain=0.25)
        poser(seche, coup(midi(accord[0] - 12), midi(accord[0] - 12), 3.8, 1.8) * 0.5, t, gain=0.22)
        t += 4.0
        i += 1
    poser(envoi, nappe(prog['resolution'], 5.0, attaque=1.0, relache=3.0, brillance=2000), cues['fin'] - 5.5, 0.7)

    # piano : arpège doux entre 5 s et la montée, plus présent après l'impact
    t, i = 5.0, 0
    while t < cues['fin'] - 6:
        pres_battement = any(tb - 0.15 <= t < tb + 0.45 for tb in cues.get('battements', []))
        pendant_montee = montee_t is not None and montee_t[0] - 0.5 <= t < repere + 0.5
        if pres_battement or pendant_montee:
            t += 0.5
            i += 1
            continue
        arpege = arpeges[int((t - 2.0) // 4) % 4]
        note = arpege[i % 4] + (12 if (t > repere and i % 8 == 7) else 0)
        velocite = 0.55 if t < repere else 0.75
        poser(envoi, piano(note, velocite), t, gain=0.16, pan=(-0.35, 0.2, -0.1, 0.35)[i % 4])
        poser(seche, piano(note, velocite), t, gain=0.11, pan=(-0.35, 0.2, -0.1, 0.35)[i % 4])
        t += 0.5
        i += 1

    for tb in cues.get('battements', []):
        poser(fx_seche, battement(), tb, gain=1.35)
        poser(fx_envoi, battement(), tb, gain=0.2)
    for k, ts in enumerate(cues['souffles']):
        poser(fx_envoi, souffle(), ts - 0.45, gain=0.07, pan=(-0.5, 0.5)[k % 2])
        poser(fx_seche, souffle(), ts - 0.45, gain=0.04, pan=(-0.5, 0.5)[k % 2])
    for tt in cues.get('traits', []):
        poser(fx_seche, trait(), tt, gain=0.05, pan=0.15)
        poser(fx_envoi, trait(), tt, gain=0.03, pan=0.15)
    for tt in cues.get('tics', []):
        poser(fx_seche, tic(), tt, gain=0.16)
        poser(fx_envoi, tic(), tt, gain=0.08)
    if montee_t is not None:
        t0, t1 = montee_t
        poser(fx_seche, montee(t1 - t0), t0, gain=0.22)
    if impact_t is not None:
        poser(fx_seche, impact(), impact_t, gain=1.0)
        poser(fx_envoi, impact(), impact_t, gain=0.5)

    # la musique s'efface de 11 dB sous chaque battement, de 10 dB sous l'impact
    musique = (seche + reverb(envoi) * 0.9) * 0.8
    g = attenuation(len(musique), cues.get('battements', []), 11, 0.32, 0.22)
    if impact_t is not None:
        g = np.minimum(g, attenuation(len(musique), [impact_t], 10, 0.25, 0.7))
    mix = musique * g[:, None] + fx_seche + reverb(fx_envoi) * 0.9
    mix = passe_haut(mix, 28)
    mix = mix[: int(duree * SR)]
    fondu = int(1.2 * SR)
    mix[-fondu:] *= np.linspace(1, 0, fondu)[:, None] ** 1.5
    mix = np.tanh(mix / np.max(np.abs(mix)) * 1.7) / np.tanh(1.7)   # saturation douce des crêtes

    # niveau final : −14 LUFS, sans dépasser −1,5 dBFS en crête
    gain_db = min(SONIE_CIBLE - sonie(mix), CRETE_MAX - 20 * np.log10(np.max(np.abs(mix))))
    return mix * 10 ** (gain_db / 20)


def ecrire(chemin, duree, cues, progression='re_mineur'):
    """Écrit la bande-son en WAV 16 bits ; renvoie (sonie en LUFS, crête en dBFS)."""
    mix = composer(duree, cues, progression)
    wavfile.write(chemin, SR, (mix * 32767).astype(np.int16))
    return sonie(mix), 20 * np.log10(np.max(np.abs(mix)))
