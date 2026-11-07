# Journal des versions

## v0.3.1 · 7 novembre 2026

Commit `0f894e0ef17cbb22ae6391f9693abaf630cc4780` (étiquette `v0.3.1` à créer sur GitHub).

- Sous-titres : le mot actif grossi ne mord plus sur l'espace voisin
  (« Liban–Yvelinesest », « etl'association » sur les mots longs). Chaque mot
  garde la place de son grossissement, et la carte ne bouge pas d'un mot actif
  à l'autre. Le grossissement se règle : `sous_titres.agrandissement_actif`
  (1.06 par défaut, 1 pour aucun).

## v0.3.0 · 7 novembre 2026

Commit `991cc03e53f1b2fb40f7bf34408a4cddf7bf5986` (étiquette `v0.3.0` à créer sur GitHub).

- Chaque texte (sous-titres, accroche, carton) reçoit la langue, le sens
  d'écriture (`langues.sens`, arabe en `rtl` par défaut) et la police de sa
  langue (`titres_ar`, `arabe_titres`, `arabe`), qu'elle soit principale ou
  seconde. Corrige une vidéo à voix arabe avec le français dessous : la ligne
  principale et la phrase du carton n'avaient pas `dir="rtl"`, et le point
  final passait du mauvais côté.
- `base` : un chemin de base se lit depuis le fichier qui le déclare (une
  variante peut hériter d'un studio qui hérite lui-même d'une charte).

## v0.2.0 · 7 novembre 2026

Commit `66b3da7ff0f89bb07849a80fa93f6c6bfe89cde6` (étiquette `v0.2.0` à créer sur GitHub).

Nouveaux réglages de `marque.json`, sans effet sur les marques qui ne les
utilisent pas :
- `base` : hériter d'une autre marque (la charte du projet) puis la compléter ;
- `couleurs.degrade` (`haut`, `bas`, `lueur`) pour le fond du carton ;
- `carton_fin.etiquette` (petit titre sous le logo) et `carton_fin.partenaires`
  en liste de noms (choix et ordre des tuiles) ;
- `mentions_interdites` : alerte dans la page de review.

## v0.1.0 · 7 novembre 2026

Commit `f3879871ddfe72024dc6144cdbdda29d13430eb3` (étiquette `v0.1.0` à créer sur GitHub).

Première version, extraite du studio de montage de Nabad et rendue générique :
blancs coupés, transcription Whisper, sous-titres mot par mot avec une seconde
langue, B-roll et flous, musique synthétisée (trois progressions) ou extension,
carton de fin intégré ou extension, page de review aux couleurs de la marque,
export, `outils`, `essai`, `references`, `nouveau`.
