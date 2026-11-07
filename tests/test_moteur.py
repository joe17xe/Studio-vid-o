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


def test_base_heritee_puis_completee(tmp_path):
    (tmp_path / '.git').mkdir()
    (tmp_path / 'charte').mkdir()
    (tmp_path / 'charte' / 'marque.json').write_text(json.dumps(
        {'nom': 'Charte', 'couleurs': {'accent': '#111111', 'fond': '#222222'}, 'mentions_interdites': ['X']}))
    (tmp_path / 'studio').mkdir()
    (tmp_path / 'studio' / 'marque.json').write_text(json.dumps(
        {'base': 'charte/marque.json', 'couleurs': {'accent': '#333333'}}))
    m = Marque(tmp_path / 'studio')
    assert m['nom'] == 'Charte'
    assert m.couleurs['accent'] == '#333333' and m.couleurs['fond'] == '#222222'
    assert m['mentions_interdites'] == ['X']


def test_carton_partenaires_choisis_et_degrade(tmp_path):
    from studio_video.carton import page_carton
    (tmp_path / '.git').mkdir()
    for n in ('a', 'b'):
        (tmp_path / f'{n}.png').write_bytes(b'x')
    (tmp_path / 'studio').mkdir()
    (tmp_path / 'studio' / 'marque.json').write_text(json.dumps({
        'polices': {}, 'couleurs': {'degrade': {'haut': '#ABCDEF', 'lueur': 'rgba(1,2,3,.5)'}},
        'partenaires': [{'nom': 'A', 'fichier': 'a.png'}, {'nom': 'B', 'fichier': 'b.png'}],
        'carton_fin': {'partenaires': ['B'], 'etiquette': 'SIGNATURE', 'phrase': {'fr': 'Merci.'}}}))
    html, _ = page_carton(Marque(tmp_path / 'studio'))
    assert 'b.png' in html and 'a.png' not in html
    assert '#ABCDEF' in html and 'rgba(1,2,3,.5)' in html
    assert html.index('SIGNATURE') < html.index('Merci.')


def test_sens_et_police_par_langue(tmp_path):
    from studio_video.carton import page_carton
    (tmp_path / 'marque.json').write_text(json.dumps({
        'polices': {'titres': {'famille': 'A', 'fichier': 'x.ttf'}, 'arabe': {'famille': 'B', 'fichier': 'x.ttf'},
                    'arabe_titres': {'famille': 'C', 'fichier': 'x.ttf', 'graisse': 700}},
        'langues': {'principale': 'ar', 'secondes': ['fr']},
        'carton_fin': {'phrase': {'ar': 'نربط، نُلهم، نعمل.', 'fr': 'Relier.'}}}))
    m = Marque(tmp_path)
    assert m.sens('ar') == 'rtl' and m.sens('fr') == 'ltr'
    assert m.role_pour('titres', 'ar') == 'arabe_titres'
    assert m.role_pour('texte', 'ar') == 'arabe'
    assert m.role_pour('titres', 'fr') == 'titres'
    a = m.attributs('titres', 'ar')
    assert 'dir="rtl"' in a and 'lang="ar"' in a and "R-arabe_titres" in a and '700' in a
    assert 'dir=' not in m.attributs('texte', 'fr')
    m.polices_css = lambda: ''             # pas de téléchargement de police dans ce test
    html, _ = page_carton(m)
    assert '<p class="titre" lang="ar" dir="rtl"' in html


def test_base_de_base_lue_depuis_son_fichier(tmp_path):
    (tmp_path / 'depot' / '.git').mkdir(parents=True)
    (tmp_path / 'depot' / 'charte').mkdir()
    (tmp_path / 'depot' / 'charte' / 'marque.json').write_text(json.dumps({'nom': 'Charte'}))
    (tmp_path / 'depot' / 'studio').mkdir()
    (tmp_path / 'depot' / 'studio' / 'marque.json').write_text(json.dumps({'base': 'charte/marque.json'}))
    (tmp_path / 'variante').mkdir()
    (tmp_path / 'variante' / 'marque.json').write_text(json.dumps(
        {'base': str(tmp_path / 'depot' / 'studio' / 'marque.json'), 'langues': {'principale': 'ar'}}))
    m = Marque(tmp_path / 'variante')
    assert m['nom'] == 'Charte' and m['langues']['principale'] == 'ar'


def test_agrandissement_du_mot_actif_reglable(tmp_path):
    from studio_video.montage import css_calques
    m = Marque(tmp_path)
    m.polices_css = lambda: ''
    assert m['sous_titres']['agrandissement_actif'] == 1.06
    assert 'scale(1.06)' in css_calques(m)
    (tmp_path / 'marque.json').write_text(json.dumps({'sous_titres': {'agrandissement_actif': 1}}))
    m = Marque(tmp_path)
    m.polices_css = lambda: ''
    assert 'scale(1)' in css_calques(m)


def test_marque_surchargee_par_une_video(tmp_path):
    from studio_video.montage import charger_montage
    (tmp_path / 'marque.json').write_text(json.dumps({'carton_fin': {'modele': 'fin-route', 'lien': 'a'}}))
    (tmp_path / 'montages').mkdir()
    (tmp_path / 'montages' / 'x.json').write_text(json.dumps(
        {'rush': 'a-roll/x.mp4', 'marque': {'carton_fin': {'modele': 'fin-don'}}}))
    m = Marque(tmp_path)

    class Args:
        modele = None
    charger_montage(tmp_path / 'a-roll' / 'x.mp4', tmp_path, m, Args)
    assert m['carton_fin']['modele'] == 'fin-don' and m['carton_fin']['lien'] == 'a'
