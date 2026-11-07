"""Créer le studio d'un nouveau projet : dossiers, marque.json, guide, README, skill, .gitignore."""

import copy
import json
import re
import unicodedata
from datetime import date
from importlib import resources
from pathlib import Path

from . import __version__
from .marque import DEFAUT


def slug(texte):
    t = unicodedata.normalize('NFKD', texte).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-') or 'projet'


def modele(nom):
    return (resources.files('studio_video') / 'modeles' / nom).read_text(encoding='utf-8')


def nouveau(dossier, nom):
    dossier = Path(dossier).resolve()
    racine = dossier
    while not (racine / '.git').exists() and racine.parent != racine:
        racine = racine.parent
    if not (racine / '.git').exists():
        racine = dossier.parent
    relatif = dossier.relative_to(racine).as_posix()
    valeurs = {'{NOM}': nom, '{SLUG}': slug(nom), '{DOSSIER}': relatif, '{VERSION}': f'v{__version__}',
               '{DATE}': date.today().strftime('%d/%m/%Y')}

    def remplir(texte):
        for k, v in valeurs.items():
            texte = texte.replace(k, v)
        return texte

    crees = []

    def ecrire(chemin, texte):
        if not chemin.exists():
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_text(texte, encoding='utf-8')
            crees.append(chemin.relative_to(racine).as_posix())

    for sous in ('montages', 'export', 'references/notes'):
        ecrire(dossier / sous / '.gitkeep', '')
    ecrire(dossier / 'a-roll' / 'LISEZMOI.md', modele('LISEZMOI-a-roll.md'))
    ecrire(dossier / 'b-roll' / 'LISEZMOI.md', modele('LISEZMOI-b-roll.md'))
    ecrire(dossier / 'references' / 'videos' / 'LISEZMOI.md', modele('LISEZMOI-references.md'))
    marque = copy.deepcopy(DEFAUT)
    marque['nom'] = nom
    marque['_aide'] = ('Réglages du moteur studio-video (README du moteur, « marque.json ») ; '
                       'tout champ absent prend la valeur par défaut du moteur.')
    ecrire(dossier / 'marque.json', json.dumps(marque, ensure_ascii=False, indent=2) + '\n')
    ecrire(dossier / 'guide-de-montage.md', remplir(modele('guide-de-montage.md')))
    ecrire(dossier / 'README.md', remplir(modele('README-studio.md')))
    ecrire(racine / '.claude' / 'skills' / f'{slug(nom)}-studio' / 'SKILL.md', remplir(modele('SKILL.md')))
    gi = racine / '.gitignore'
    lignes = remplir(modele('gitignore.txt'))
    if f'{relatif}/a-roll/*' not in (gi.read_text(encoding='utf-8') if gi.exists() else ''):
        with gi.open('a', encoding='utf-8') as f:
            f.write(lignes)
        crees.append('.gitignore (lignes du studio ajoutées)')
    return crees
