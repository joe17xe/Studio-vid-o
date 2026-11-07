"""Tests rapides, sans ffmpeg ni Chromium : la logique des coupes, des sous-titres et de la marque."""

import json

from studio_video.marque import DEFAUT, Marque, fusion
from studio_video.montage import cartes, mots_de, parole_depuis_blancs, repartir, vers_montage

REGLAGES = {'marge_avant': 0.1, 'marge_apres': 0.2, 'mots_par_carte': 4, 'caracteres_par_carte': 24}


def test_blancs_coupes_avec_marges():
    segs = parole_depuis_blancs([0.0, 3.0], [1.0, 4.0], 6.0, REGLAGES, 30)
    assert segs == [[0.9, 3.2], [3.9, 6.0]]


def test_blancs_proches_fusionnes():
    segs = parole_depuis_blancs([2.0], [2.2], 4.0, dict(REGLAGES, marge_avant=0.1, marge_apres=0.1), 30)
    assert len(segs) == 1


def test_temps_du_montage():
    segs = [[1.0, 2.0], [3.0, 5.0]]
    assert vers_montage(1.5, segs) == 0.5
    assert vers_montage(2.5, segs) == 1.0      # dans un blanc coupé : début du morceau suivant
    assert vers_montage(4.0, segs) == 2.0


def test_insecables_restent_entiers():
    assert mots_de('environ 6 000 habitants') == ['environ', '6 000', 'habitants']


def test_cartes_et_premiere_image():
    mots = repartir(mots_de('Bonjour, ceci est un essai du studio de montage.'), [[0.5, 3.5]])
    cs = cartes([{'texte': '', 'mots': mots}], [[0.0, 10.0]], REGLAGES)
    assert cs[0]['debut'] == 0.0                # texte dès la première image
    assert all(len(c['mots']) <= 4 for c in cs)
    assert cs[0]['mots'][-1]['mot'] == 'Bonjour,'   # coupe à la ponctuation


def test_marque_par_defaut_et_fusion(tmp_path):
    (tmp_path / 'marque.json').write_text(json.dumps({'nom': 'X', 'couleurs': {'accent': '#123456'},
                                                      'langues': {'secondes': ['en']}}))
    m = Marque(tmp_path)
    assert m['nom'] == 'X' and m.couleurs['accent'] == '#123456'
    assert m.couleurs['fond'] == DEFAUT['couleurs']['fond']      # le reste vient du défaut
    assert m.seconde == 'en'
    assert fusion({'a': {'b': 1, 'c': 2}}, {'a': {'b': 3}}) == {'a': {'b': 3, 'c': 2}}


def test_chemin_relatif_au_depot(tmp_path):
    (tmp_path / '.git').mkdir()
    (tmp_path / 'logos').mkdir()
    (tmp_path / 'logos' / 'l.png').write_bytes(b'x')
    (tmp_path / 'studio').mkdir()
    m = Marque(tmp_path / 'studio')
    assert m.chemin('logos/l.png') == (tmp_path / 'logos' / 'l.png').resolve()
    assert m.chemin('absent.png') is None
