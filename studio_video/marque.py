"""La marque d'un projet : studio/marque.json, complété par des valeurs par défaut.

Tout ce qui distingue un projet d'un autre (couleurs, polices, langues, carton de fin,
musique, points de contrôle) vient de ce fichier. Le moteur ne contient aucun réglage
propre à un projet : un besoin nouveau devient un champ de marque.json, documenté dans
le README du moteur, avec une valeur par défaut qui ne change rien aux autres projets.
"""

import copy
import hashlib
import json
import re
import urllib.request
from pathlib import Path

CACHE = Path.home() / '.cache' / 'studio-video'
RTL = {'ar', 'he', 'fa', 'ur'}          # langues écrites de droite à gauche, sauf avis de langues.sens
ALIAS_POLICES = {'ar': 'arabe'}        # nom historique du rôle de police d'une langue

DEFAUT = {
    'nom': 'Projet',
    'couleurs': {                   # neutres : chaque projet met les siennes
        'fond': '#1B1F24', 'fond_2': '#2C333B', 'texte': '#F5F5F2', 'texte_doux': '#BFC5CC',
        'accent': '#8FB8DE', 'accent_2': '#E2B65C', 'mot_actif': '#E2B65C',
        'fond_sous_titres': 'rgba(20,23,27,.76)', 'voile': 'rgba(20,23,27,.85)',
        'seconde_langue': '#E6E2DA', 'lueur': None,
    },
    'polices': {                    # libres (OFL), téléchargées depuis Google Fonts
        'titres': {'famille': 'Source Serif 4', 'google_fonts': 'Source+Serif+4:wght@600', 'graisse': 600},
        'texte': {'famille': 'Inter', 'google_fonts': 'Inter:wght@400;600', 'graisse': 400},
        'sous_titres': {'famille': 'Inter', 'google_fonts': 'Inter:wght@600', 'graisse': 600},
        'arabe': {'famille': 'Noto Sans Arabic', 'google_fonts': 'Noto+Sans+Arabic:wght@500', 'graisse': 500},
    },
    'langues': {'principale': 'fr', 'secondes': []},
    'sous_titres': {
        'taille': 60, 'taille_seconde': 42, 'mots_par_carte': 4, 'caracteres_par_carte': 24,
        'seconde': None,            # code de la langue affichée sous le français : "ar", "en"… ou null
        'separateur': 'trait',      # entre les deux langues : "trait", "pouls" ou "aucun"
        'rayon': 30,
        'agrandissement_actif': 1.06,   # le mot en train d'être dit grossit de 6 % (1 : pas du tout)
    },
    'formats': {'vertical': {'largeur': 1080, 'hauteur': 1920,
                             'zone_utile': {'y_min': 250, 'y_max': 1450}}},
    'logo': None, 'logo_fond': None,
    'carton_fin': {
        'type': 'integre',          # "integre" (rendu par le moteur), "extension" ou "aucun"
        'duree': 4.6, 'etiquette': '', 'phrase': {}, 'lien': '', 'hashtag': '',
        'partenaires': False,       # true (tous), ou la liste des noms à montrer, dans l'ordre
        'extension': None,          # "fichier.py:fonction", relatif au dossier studio
    },
    'partenaires': [],
    'mentions_interdites': [],     # mots qui ne doivent jamais apparaître (alerte dans la review)
    'son': {
        'musique': None,            # null, "synthese" ou "extension"
        'synthese': {'progression': 're_mineur', 'graine': 2026},
        'extension': None,
        'voix_lufs': -16, 'musique_sous_voix_db': -21, 'musique_pause_db': -11,
        'sonie_cible': -14.0, 'crete_max': -1.5,
    },
    'montage': {
        'seuil_db': -35, 'blanc_min': 0.45, 'marge_avant': 0.10, 'marge_apres': 0.18,
        'cadrage_x': 0.5, 'etalonnage': 'eq=contrast=1.08:saturation=1.15', 'modele': 'small',
    },
    'controles': [],
}

CONTROLES_COMMUNS = [
    'La transcription est juste mot à mot (noms propres, chiffres, accents).',
    'Les traductions sont relues par un locuteur de la langue.',
    'Droit à l’image : accord de chaque personne reconnaissable, aucun enfant identifiable.',
    'Plaques d’immatriculation et documents floutés ou hors cadre.',
    'Logos des partenaires montrés avec leur accord, ni redessinés ni déformés.',
    'Sous-titres lisibles sur téléphone, dans la zone utile.',
    'Son écouté sur un téléphone : la voix devant, aucun clic aux coupes.',
    'La première image porte un texte (elle sert de couverture).',
]


def fusion(base, ajout):
    sortie = copy.deepcopy(base)
    for k, v in (ajout or {}).items():
        sortie[k] = fusion(sortie[k], v) if isinstance(v, dict) and isinstance(sortie.get(k), dict) else v
    return sortie


class Marque:
    def __init__(self, studio):
        self.studio = Path(studio).resolve()
        fichier = self.studio / 'marque.json'
        brut = json.loads(fichier.read_text(encoding='utf-8')) if fichier.exists() else {}
        self.present = fichier.exists()
        # « base » : la marque hérite d'un autre fichier (la charte du projet), puis le complète
        chaine, vus, depuis = [brut], set(), self.studio
        while chaine[-1].get('base'):
            # le chemin d'une base se lit depuis le fichier qui la déclare
            source = chercher(chaine[-1]['base'], depuis)
            if not source or source in vus:
                raise FileNotFoundError(f'marque de base introuvable ou en boucle : {chaine[-1]["base"]}')
            vus.add(source)
            depuis = source.parent
            chaine.append(json.loads(source.read_text(encoding='utf-8')))
        self.d = DEFAUT
        for couche in reversed(chaine):
            self.d = fusion(self.d, couche)

    def __getitem__(self, cle):
        return self.d[cle]

    @property
    def couleurs(self):
        return self.d['couleurs']

    @property
    def vertical(self):
        v = self.d['formats']['vertical']
        return v['largeur'], v['hauteur'], v['zone_utile']['y_min'], v['zone_utile']['y_max']

    @property
    def seconde(self):
        s = self.d['sous_titres'].get('seconde')
        if s is None and self.d['langues'].get('secondes'):
            s = self.d['langues']['secondes'][0]
        return s

    @property
    def controles(self):
        return self.d['controles'] + [c for c in CONTROLES_COMMUNS if c not in self.d['controles']]

    def chemin(self, relatif):
        """Un chemin de marque.json : relatif au dossier studio, sinon au dépôt du projet."""
        return chercher(relatif, self.studio)

    # --- polices -----------------------------------------------------------------

    def polices_css(self):
        """Des @font-face locales pour chaque rôle (titres, texte, sous_titres, arabe…),
        nommées « R-<rôle> » ; les fichiers sont téléchargés une fois dans le cache."""
        regles = []
        for role, spec in self.d['polices'].items():
            if not isinstance(spec, dict):
                continue
            for poids, style, fichier in fichiers_police(spec, self):
                regles.append(f"@font-face {{ font-family: 'R-{role}'; src: url('{Path(fichier).as_uri()}'); "
                              f"font-weight: {poids}; font-style: {style}; }}")
        return '\n'.join(regles)

    def pile(self, role, secours='sans-serif'):
        roles = [role] + (['arabe'] if role != 'arabe' else [])
        return ', '.join(f"'R-{r}'" for r in roles if r in self.d['polices']) + f', {secours}'

    def sens(self, langue):
        """« rtl » ou « ltr » : langues.sens de la marque, sinon le sens usuel de la langue."""
        return (self.d['langues'].get('sens') or {}).get(langue) or ('rtl' if langue in RTL else 'ltr')

    def role_pour(self, role, langue):
        """La police d'un rôle dans une langue : « titres_ar », sinon « arabe_titres », sinon « arabe »
        (pour l'arabe), sinon le rôle lui-même."""
        a = ALIAS_POLICES.get(langue, langue)
        for r in (f'{role}_{langue}', f'{a}_{role}', a):
            if isinstance(self.d['polices'].get(r), dict):
                return r
        return role

    def attributs(self, role, langue):
        """Attributs HTML d'un texte : langue, sens d'écriture et police de son rôle dans cette langue."""
        r = self.role_pour(role, langue)
        sens = ' dir="rtl"' if self.sens(langue) == 'rtl' else ''
        return f' lang="{langue}"{sens} style="font-family: {self.pile(r)}; font-weight: {self.graisse(r)}"'

    def graisse(self, role):
        return self.d['polices'].get(role, {}).get('graisse', 400)


def chercher(relatif, depuis):
    """Un chemin relatif à « depuis », sinon à un de ses dossiers parents jusqu'à la racine du dépôt."""
    if not relatif:
        return None
    p = Path(relatif)
    if p.is_absolute():
        return p if p.exists() else None
    base = Path(depuis).resolve()
    while True:
        if (base / p).exists():
            return (base / p).resolve()
        if (base / '.git').exists() or base.parent == base:
            return None
        base = base.parent


def fichiers_police(spec, marque=None):
    """[(graisse, style, fichier)] pour une police : fichier local, ou Google Fonts."""
    if spec.get('fichier'):
        f = marque.chemin(spec['fichier']) if marque else Path(spec['fichier'])
        if not f:
            raise FileNotFoundError(f'police introuvable : {spec["fichier"]}')
        return [(spec.get('graisse', '100 900'), 'normal', f)]
    gf = spec.get('google_fonts')
    if not gf:
        gf = spec['famille'].replace(' ', '+') + f':wght@{spec.get("graisse", 400)}'
    dossier = CACHE / 'polices' / hashlib.sha1(gf.encode()).hexdigest()[:12]
    index = dossier / 'index.json'
    if index.exists():
        return [tuple(x) for x in json.loads(index.read_text())]
    dossier.mkdir(parents=True, exist_ok=True)
    url = 'https://fonts.googleapis.com/css2?family=' + gf
    # un client sans nom de navigateur reçoit des fichiers TrueType, que tout sait lire
    css = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'curl/8'}), timeout=30).read().decode()
    sortie = []
    for bloc in re.findall(r'@font-face\s*{(.*?)}', css, re.S):
        poids = re.search(r'font-weight:\s*([\d ]+);', bloc).group(1).strip()
        style = re.search(r'font-style:\s*(\w+);', bloc).group(1)
        src = re.search(r'url\((https://[^)]+)\)', bloc).group(1)
        fichier = dossier / (Path(src).name)
        if not fichier.exists():
            urllib.request.urlretrieve(src, fichier)
        sortie.append((poids, style, str(fichier)))
    if not sortie:
        raise RuntimeError(f'Google Fonts n’a rien renvoyé pour « {gf} »')
    index.write_text(json.dumps(sortie))
    return sortie
