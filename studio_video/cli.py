"""Ligne de commande : studio-video <commande> (ou python3 -m studio_video <commande>)."""

import argparse
import sys
from pathlib import Path

from . import __version__


def main(argv=None):
    a = argparse.ArgumentParser(prog='studio-video', description='Moteur de montage vidéo commun (studio-video).')
    a.add_argument('--version', action='version', version=f'studio-video {__version__}')
    s = a.add_subparsers(dest='commande', required=True)

    def studio(p, aide='dossier du studio du projet (celui de marque.json)'):
        p.add_argument('--studio', default='studio', help=aide)

    p = s.add_parser('outils', help='installer (option) et tester chaque outil')
    studio(p)
    p.add_argument('--installer', action='store_true')
    p.add_argument('--url', help='tester aussi un téléchargement yt-dlp')

    p = s.add_parser('monter', help='monter un rush : page de review, puis --exporter')
    p.add_argument('rush')
    studio(p)
    p.add_argument('--travail', help='dossier des rushes et exports (défaut : le studio)')
    p.add_argument('--texte', help='texte dit, si Whisper n’est pas disponible (horodatage estimé)')
    p.add_argument('--exporter', action='store_true')
    p.add_argument('--recouper', action='store_true')
    p.add_argument('--retranscrire', action='store_true')
    p.add_argument('--modele', help='modèle Whisper : small (défaut), medium, large-v3')

    p = s.add_parser('essai', help='essai de bout en bout avec une voix de synthèse')
    studio(p)
    p.add_argument('--travail')
    p.add_argument('--exporter', action='store_true')
    p.add_argument('--whisper', action='store_true')

    p = s.add_parser('references', help='télécharger ou analyser une vidéo de référence')
    s2 = p.add_subparsers(dest='action', required=True)
    t = s2.add_parser('telecharger')
    t.add_argument('lien')
    t.add_argument('--nom')
    studio(t)
    n = s2.add_parser('analyser')
    n.add_argument('video')
    n.add_argument('--sans-whisper', action='store_true')
    studio(n)

    p = s.add_parser('nouveau', help='créer le studio d’un nouveau projet')
    p.add_argument('dossier', nargs='?', default='studio')
    p.add_argument('--nom', required=True, help='nom du projet, par exemple « Mon projet »')

    args = a.parse_args(argv)
    if args.commande == 'outils':
        from .outils import verifier_tout
        sys.exit(0 if verifier_tout(args.studio if Path(args.studio).exists() else None, args.url, args.installer) else 1)
    if args.commande == 'monter':
        from .montage import monter
        monter(args.rush, Path(args.studio).resolve(), args, args.travail)
    elif args.commande == 'essai':
        from .essai import essai
        dossier = essai(args.studio, args.travail, args.exporter, args.whisper)
        print(f'essai dans {dossier}')
    elif args.commande == 'references':
        from . import references
        st = Path(args.studio).resolve()
        if args.action == 'telecharger':
            references.analyser(references.telecharger(args.lien, args.nom, st), st)
        else:
            references.analyser(Path(args.video), st, args.sans_whisper)
    elif args.commande == 'nouveau':
        from .nouveau import nouveau
        for f in nouveau(args.dossier, args.nom):
            print(f'  + {f}')


if __name__ == '__main__':
    main()
