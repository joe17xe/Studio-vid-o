# studio-video · consignes pour Claude

Moteur de montage vidéo **commun à plusieurs projets**, dépôt
**public**, licence MIT.

## Règles

- **Rien de propre à un projet dans ce dépôt.** Pas de nom de projet dans le
  code, pas de couleur, texte, logo, photo, rush, charte, nom de partenaire ou
  de mécène, adresse de serveur, clé. Tout cela vit dans le `studio/marque.json`
  du projet.
- **Chaque besoin devient un réglage générique** : un champ de `marque.json`
  avec une valeur par défaut qui ne change rien aux autres projets, documenté
  dans le README (tableau `marque.json`), avec un test.
- Ce qu'un seul projet possède déjà (un carton animé, une bande-son) se branche
  par une **extension** de ce projet, pas par du code ici.
- Avant de pousser : `python3 -m pytest -q tests`, puis `studio-video essai`
  sur au moins deux marques (un studio vierge créé par `studio-video nouveau`,
  et un vrai projet). Regarder les images clés.
- Les messages de commit sont publics : en français, sans information
  confidentielle, sans identifiant de modèle.
- Une version publiée (`vX.Y.Z`) ne se modifie pas : on en publie une nouvelle
  et on la note dans `CHANGELOG.md`.
