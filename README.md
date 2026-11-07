# studio-video

Un **moteur de montage vidéo commun à plusieurs projets**. On
lui donne un rush où quelqu'un parle ; il rend une vidéo verticale aux couleurs
du projet :

1. les blancs coupés (avec des marges, pour ne pas manger les mots) ;
2. la voix transcrite mot à mot (Whisper) ;
3. les sous-titres qui s'allument mot par mot, avec une seconde langue dessous ;
4. les plans d'illustration (B-roll), les flous de plaques ;
5. la musique de la marque sous la voix, qui reste devant ; −14 LUFS ;
6. le carton de fin de la marque ;
7. une **page de review** pour valider avant l'export ;
8. l'export MP4 1080×1920 H.264/AAC `faststart` et les sous-titres `.srt`.

Rien n'est publié par le moteur.

## Le principe : un moteur, une marque par projet

> **Chaque besoin d'un projet devient un réglage générique, jamais un cas
> spécial.** Le moteur ne contient aucun nom, aucune couleur, aucun texte d'un
> projet. Tout ce qui distingue un projet vit dans *son* dépôt, dans
> `studio/marque.json`.

Un projet contient seulement :

```
studio/
  marque.json            ← couleurs, polices, langues, carton, musique, contrôles
  guide-de-montage.md    ← le style du projet, en mots
  a-roll/  b-roll/       ← rushes (jamais dans git)
  references/notes/      ← analyses de vidéos de référence
  montages/              ← un fichier de réglages par vidéo (dans git)
  export/                ← vidéos finies (dans git)
.claude/skills/<projet>-studio/SKILL.md
```

`studio-video nouveau studio --nom "Mon projet"` crée tout cela.

## Installer

```bash
pip install "studio-video @ git+https://github.com/joe17xe/Studio-vid-o@v0.2.0"
studio-video outils --studio studio --installer   # installe ce qui manque, puis teste chaque outil
```

Il faut aussi `ffmpeg`, un Chromium pour Playwright, et `espeak-ng` pour les
essais. Chaque projet **fige une version** : une évolution du moteur ne change
rien chez lui tant qu'il ne choisit pas de monter de version. On fige par
l'étiquette (`@v0.1.0`) ou, ce qui revient au même, par l'empreinte exacte du
commit (`@f3879871…`) ; les versions et leurs empreintes sont dans
`CHANGELOG.md`.

Réseau : les polices viennent de Google Fonts (`fonts.googleapis.com`,
`fonts.gstatic.com`) ; le modèle Whisper de Hugging Face (`huggingface.co`,
`cdn-lfs.hf.co`, `cdn-lfs-us-1.hf.co`, `cas-bridge.xethub.hf.co`,
`us.aws.cdn.hf.co`). Tout est gratuit, sans compte, et tourne sur la machine :
aucune voix ni image n'est envoyée à un service tiers.

## Les commandes

| Commande | Ce qu'elle fait |
|---|---|
| `studio-video nouveau studio --nom X` | crée le studio d'un projet |
| `studio-video outils --studio studio` | teste chaque outil pour de vrai, et la marque du projet |
| `studio-video essai --studio studio --exporter` | essai complet avec une voix de synthèse, dans `studio/.essai/` |
| `studio-video monter a-roll/x.mp4 --studio studio` | monte, et prépare `export/x-review/index.html` |
| `studio-video monter a-roll/x.mp4 --studio studio --exporter` | export final après validation |
| `studio-video references analyser references/videos/x.mp4 --studio studio` | mesure une vidéo de référence et écrit sa fiche |
| `studio-video references telecharger <lien> --studio studio` | yt-dlp, pour une analyse interne seulement |

Options de `monter` : `--recouper` (refaire les blancs), `--retranscrire`,
`--modele medium`, `--texte fichier.txt` (sans Whisper : texte connu,
horodatage estimé), `--travail <dossier>` (rushes et exports ailleurs que dans
le studio).

## `marque.json`

Tout champ absent prend la valeur par défaut (`studio_video/marque.py`). Les
chemins sont relatifs au dossier studio, sinon à la racine du dépôt du projet.

| Champ | Rôle |
|---|---|
| `base` | (option) une autre marque dont celle-ci hérite, par exemple la charte du projet (`"communication/charte/marque.json"`), ou une variante qui hérite du studio principal ; chaque chemin `base` se lit depuis le fichier qui le déclare ; les champs écrits ici complètent ou remplacent la base |
| `nom` | nom du projet (page de review, essai) |
| `couleurs` | `fond`, `fond_2` (dégradés), `texte`, `texte_doux`, `accent`, `accent_2`, `mot_actif`, `fond_sous_titres`, `voile` (accroche), `seconde_langue`, `lueur` (option : halo du carton) ; `degrade` (option : `haut`, `bas`, `lueur`, pour le fond du carton) |
| `polices` | par rôle : `titres`, `texte`, `sous_titres`, `arabe` (et tout autre rôle). Chaque rôle : `famille`, `graisse`, et `google_fonts` (`"Fraunces:opsz,wght@9..144,600"`) **ou** `fichier` (un `.ttf` du dépôt). Un texte dans une langue prend la police `<rôle>_<langue>` (`titres_ar`), sinon, pour l'arabe, `arabe_<rôle>` (`arabe_titres`) puis `arabe`, sinon le rôle lui-même |
| `langues` | `principale` (langue de Whisper et des sous-titres) et `secondes` (traductions, dans l'ordre) ; `sens` (option, ex. `{"ar": "rtl"}`) : chaque texte reçoit `lang` et le sens d'écriture de sa langue (arabe, hébreu, persan, ourdou de droite à gauche par défaut), quelle que soit sa place (principale ou seconde) |
| `sous_titres` | `taille`, `taille_seconde`, `mots_par_carte`, `caracteres_par_carte`, `seconde` (langue affichée dessous, sinon la première des `secondes`), `separateur` (`trait`, `pouls`, `aucun`), `rayon`, `agrandissement_actif` (grossissement du mot dit, 1.06 par défaut, 1 pour aucun ; chaque mot garde la place de son grossissement, sans toucher ses voisins) |
| `formats.vertical` | `largeur`, `hauteur`, `zone_utile` (`y_min`, `y_max`) |
| `logo`, `logo_fond` | logo du carton ; `logo_fond` (ex. `#FFFFFF`) le pose sur une pastille |
| `partenaires` | `[{"nom", "fichier"}]`, posés sur des tuiles blanches |
| `carton_fin` | `type` : `integre` (rendu par le moteur), `extension` ou `aucun` ; `duree`, `etiquette` (petit titre en capitales espacées sous le logo), `phrase` (par langue), `lien`, `hashtag`, `partenaires` (`true` : toutes les tuiles ; ou la liste des noms à montrer, dans l'ordre), `etiquette_partenaires`, `extension` |
| `son` | `musique` : `null`, `synthese` (musique originale du moteur : `synthese.progression` = `re_mineur`, `fa_majeur`, `sol_majeur` ; `synthese.graine`) ou `extension` ; `voix_lufs`, `musique_sous_voix_db`, `musique_pause_db`, `sonie_cible`, `crete_max` |
| `montage` | `seuil_db`, `blanc_min`, `marge_avant`, `marge_apres`, `cadrage_x`, `etalonnage` (filtre ffmpeg), `modele` (Whisper) |
| `mentions_interdites` | mots qui ne doivent jamais apparaître ; la page de review alerte s'ils sont dans la transcription, une traduction ou l'accroche |
| `controles` | les points à vérifier du projet, ajoutés aux points communs dans la page de review |

### Les extensions

Pour ce qu'un projet a déjà en propre (un carton animé existant, une bande-son
maison), une **extension** branche son code sans le copier dans le moteur :

- `carton_fin.extension = "extensions/x.py:carton"` → `carton(marque, cache)`
  renvoie `{"mp4", "duree", "saut_images", "battements", "tics"}` ;
- `son.extension = "extensions/x.py:musique"` → `musique(marque, duree, cues)`
  renvoie un tableau stéréo 48 kHz.

Une extension reste dans le dépôt du projet. Si un second projet en a besoin,
elle doit devenir un réglage du moteur.

## Le fichier de montage (`montages/<nom>.json`)

Créé au premier passage, puis corrigé à la main ou par Claude :

```json
{
  "rush": "a-roll/interview.mp4",
  "titre": "…",
  "reglages": {"blanc_min": 0.45},
  "segments": [[1.30, 3.30], [4.30, 6.80]],
  "transcription": {"source": "Whisper small", "phrases": [
    {"texte": "Bonjour à tous.", "ar": "مرحبا بالجميع.", "en": "Hello everyone.",
     "mots": [{"mot": "Bonjour", "debut": 1.40, "fin": 1.80}]}]},
  "accroche": {"fr": "…", "ar": "…", "duree": 2.5},
  "broll": [{"a": 5.5, "fichier": "b-roll/village.jpg", "duree": 3.2, "debut": 0, "cadrage_x": 0.5, "note": "…"}],
  "flous": [{"x": 400, "y": 1300, "l": 260, "h": 90, "de": 3.0, "a": 5.5}]
}
```

`segments` et `mots` sont en temps du rush ; `broll`, `flous` et `accroche` en
temps de la vidéo montée (celui de la page de review). Les traductions déjà
écrites sont gardées quand on retranscrit.

## Faire évoluer le moteur

1. Un besoin nouveau d'un projet (une couleur de plus, une autre musique, une
   troisième langue…) devient **un champ de `marque.json`**, avec une valeur par
   défaut qui ne change rien aux autres projets.
2. On le documente dans ce README, on ajoute un test, on lance
   `studio-video essai` avec au moins deux marques différentes.
3. Une nouvelle version (`v0.2.0`) est notée dans `CHANGELOG.md` ; chaque projet
   monte de version quand il le décide.

Ce dépôt est **public** : il ne contient que du code. Jamais de charte, de
logo, de photo, de rush, de nom de mécène ni de clé (voir `CLAUDE.md`).

## Licence

MIT. La musique générée par le moteur est synthétisée, originale et libre de
droits.
