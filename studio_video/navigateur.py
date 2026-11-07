"""Trouver Chromium, et rendre une page HTML en PNG ou en images successives."""

import glob
import os
from contextlib import contextmanager

RACINES = ('/opt/pw-browsers', os.path.expanduser('~/.cache/ms-playwright'))


def chromium():
    """Chemin du Chromium complet (variable CHROMIUM pour l'imposer), ou None : Playwright choisit."""
    if os.environ.get('CHROMIUM'):
        return os.environ['CHROMIUM']
    for racine in RACINES:
        trouves = sorted(glob.glob(f'{racine}/chromium-*/chrome-linux*/chrome'))
        if trouves:
            return trouves[-1]
    return None


@contextmanager
def onglet(largeur, hauteur):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        nav = p.chromium.launch(executable_path=chromium(), args=['--no-sandbox'])
        page = nav.new_page(viewport={'width': largeur, 'height': hauteur})
        try:
            yield page
        finally:
            nav.close()


def charger(page, fichier_html):
    page.goto(fichier_html.as_uri())
    page.wait_for_function("document.fonts.status === 'loaded' && "
                           "[...document.images].every(i => i.complete && i.naturalWidth > 0)")
