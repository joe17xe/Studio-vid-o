# Studio de montage · {NOM}

Le studio de {NOM} utilise le moteur commun **studio-video**
(https://github.com/joe17xe/Studio-vid-o, version `{VERSION}`). Ce dossier ne
contient que ce qui est propre au projet : la marque (`marque.json`), le guide,
les fichiers de montage, les exports.

| Dossier | On y met | Dans git ? |
|---|---|---|
| `a-roll/` | les rushes principaux (la voix) | non |
| `b-roll/` | les plans d'illustration | non |
| `references/` | `videos/` (jamais versionnées) et `notes/` (leur analyse) | les notes |
| `montages/` | un fichier de réglages par vidéo | oui |
| `export/` | les vidéos finies, couvertures, sous-titres `.srt` | oui |

## La consigne type

> Monte ma nouvelle vidéo [NOM DU FICHIER] du dossier A-Roll : coupe tous les
> blancs, ajoute les sous-titres et la musique, suis le guide de montage,
> utilise les clips du dossier B-Roll. Prépare une page de review pour que je
> valide, puis exporte la vidéo dans Export.

## Les commandes

```bash
pip install "studio-video @ git+https://github.com/joe17xe/Studio-vid-o@{VERSION}"
studio-video outils --studio {DOSSIER}                 # installer et tester
studio-video essai --studio {DOSSIER} --exporter       # essai sans vrai rush
studio-video monter a-roll/x.mp4 --studio {DOSSIER}    # montage + page de review
studio-video monter a-roll/x.mp4 --studio {DOSSIER} --exporter
```
