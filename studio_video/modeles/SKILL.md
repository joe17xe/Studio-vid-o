---
name: {SLUG}-studio
description: Studio de montage de {NOM} (moteur commun studio-video) - monter une vidéo parlée déposée dans {DOSSIER}/a-roll/ - blancs coupés, transcription Whisper, sous-titres mot par mot, B-roll, musique sous la voix à −14 LUFS, carton de fin, page de review puis export. À utiliser dès qu'on dit « monte ma vidéo », « coupe les blancs », « ajoute les sous-titres ».
---

# Studio de montage · {NOM}

La marque est dans `{DOSSIER}/marque.json`, le style dans
`{DOSSIER}/guide-de-montage.md`. Le moteur est `studio-video` (version
`{VERSION}`), décrit dans son README.

1. `studio-video outils --studio {DOSSIER}` (première fois dans la session).
2. `studio-video monter a-roll/<fichier> --studio {DOSSIER}` : crée
   `{DOSSIER}/montages/<nom>.json` et la page de review.
3. Relire la transcription, écrire les traductions (à faire relire), placer
   les B-roll, l'accroche, les flous ; relancer ; regarder les images clés.
4. Donner la page de review ; attendre « c'est validé » ; puis `--exporter`.
5. Committer l'export, sa couverture, ses `.srt` et le fichier de montage sur
   une branche. Ne rien publier sans l'accord de l'équipe.

Un besoin que le moteur ne couvre pas ne se code pas ici : il devient un
réglage générique du moteur (voir son README, « Faire évoluer le moteur »).
