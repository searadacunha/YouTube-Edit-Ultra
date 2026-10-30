# Montage musical avec actions protégées

La V1 Canelo a été rejetée artistiquement malgré un MP4 techniquement valide. Durée et décodage ne valent ni acceptation éditoriale ni visionnage intégral. **ACTION > BEAT** : conserver préparation, action, résultat et bref après-coup.

## Entrée et musique

`ueu create "Boxeur — style — durée"` orchestre les sources autorisées, annotations vérifiées et rendu. `ueu resume CHEMIN_DU_JOB` reprend les étapes vérifiées. `ultra create` et `ultra produce` restent disponibles pour les projets existants.

Pour une révision vidéo, conserver le mix et la miniature acceptés. Le manifeste explicite peut préciser `prepared_soundtrack` et `music_tracklist` : liste, ou objet contenant `tracks`, avec `title`, `timeline_start`, `timeline_end`. Le moteur ne reconstruit pas ce mix.

`editorial.analyze_structure` utilise FFmpeg/NumPy par défaut : transitoires, énergie, bandes percussives et variations mesurées. Sections et tempo restent estimés; les downbeats ne sont pas certifiés. Pas de grille inventée si la détection échoue. Le cache dépend du SHA-256 du mix, des limites/ordre des pistes et de la version du backend.

Le backend historique BeatSync/cadence reste accessible par `legacy_music_root` explicite; ses composants doivent alors exister. Un autre dépôt de ce Mac n'est plus une dépendance cachée.

## Annotations et contexte

Exemple de ligne de `.shots.json` adjacent, ou du fichier `editorial_shots` d'un manifeste explicite :

```json
{"source":"combat.mp4","safe_start":40,"core_start":40.7,"core_end":43.1,"safe_end":44,"peak":42.1,"label":"contre complet revu","kind":"action","quality":0.9,"provenance":"visual_review","audio_intent":"ambience"}
```

Les cœurs protègent toute l'action et son résultat. Les marges `safe_start/safe_end` sont réellement examinées. `source_sha256` peut lier les annotations aux octets vérifiés. Les `.actions.json` conservent leur provenance, y compris celle de l'enveloppe; l'import ou la fusion ne transforme pas des mouvements détectés en revue visuelle.

Le parcours `ueu` exige une provenance explicite admise. Sinon il conserve les candidats et signale `ACTION_REVIEW_REQUIRED`. L'agent peut examiner les images et compléter des preuves dans la demande courante; s'il ne peut pas vérifier l'action, il annonce le blocage. Aucun score de mouvement ni test synthétique ne prouve la fin d'une combinaison ou une chute après KO.

`kind: "insert"` désigne un insert contextualisé et `peak` peut être `null`. `kind: "intro"` ou `"outro"` réserve du contexte revu en ouverture/conclusion, dans le budget du job. Ne pas inventer une entrée absente des rushs. Un manifeste explicite peut aussi fournir `intro_edits` et `outro_edits`, listes d'objets `Edit` contigus. `not_before/not_after` contraint une fenêtre héroïque.

Les cœurs restent entiers, même au-delà de 12 secondes. Le planificateur choisit des fins naturelles compatibles avec les accents, varie les durées et évite la réutilisation des intervalles. Le retour arrière est borné; un échec n'est pas une preuve exhaustive d'impossibilité. Aucun filler non revu n'est ajouté par défaut.

Le dédoublonnage perceptuel échantillonné compare des encodages différents, préfère les cœurs longs et protège leurs fins échantillonnées. Il ne garantit pas la reconnaissance d'autres angles, recadrages ou événements entre échantillons. Exclusions et limites de calcul restent dans le rapport; un scan incomplet bloque le job.

## Intention audio

| `audio_intent` | Effet dans `render_streamed` |
|---|---|
| `auto` | Comportement historique : source coupée pour labels intro/insert, ambiance discrète ailleurs |
| `mute` | Source muette, musique conservée |
| `ambience` | Source conservée même pour intro/insert, avec plafond ordinaire |
| `featured` | Annonceur/public/impact explicitement choisi, musique baissée de 7 dB |

L'ambiance ordinaire reste au moins 20 dB sous la musique non atténuée. `featured` conserve la source avec gain borné à 2×, attaque musicale de 150 ms et retour de 200 ms. Le marquage n'est pas une détection automatique de parole intéressante. Sans piste audio, `featured` échoue explicitement. Le renderer historique par segments refuse les intentions explicites qu'il ne traite pas.

Le mix suit l'horloge des échantillons, utilise un FLAC temporaire et limite avant quantification. Il évite le décalage AAC par plan rencontré sur Canelo V2. Le true peak se mesure sur l'AAC final : correction audio seule si nécessaire, copie et empreinte identique du flux vidéo, puis nouvelle vérification.

## Rendu et acceptation

Le rendu H.264 à débit borné évite les copies vidéo par plan et refuse l'écrasement. Le plancher est de 12 Go libres après l'opération estimée; disk-guard réserve les opérations lourdes. Ne pas baisser `reserve_bytes`, `DISKGUARD_FLOOR_BYTES` ou reprendre une dérogation ancienne pour un nouveau job. Une interruption conserve un fichier incomplet distinct; la reprise réutilise les étapes vérifiées.

Le job contrôle durée, images, format/ratio/résolution/framerate, décodage intégral, horodatages, noirs/gels/silences, true peak, doublons échantillonnés et cœurs protégés. Tolérance conteneur : 0,15 s; images : une image. Les coupes planifiées restent sur la grille du framerate. Les rapports donnent les seuils et limites.

Pour une révision artistique longue, examiner une courte ouverture avant tout le rendu lorsque les ressources le permettent : progression, identité, inserts, premier contact musical, fins des combinaisons et respirations. Conserver l'aperçu et préciser ce qui a réellement été vu/entendu. Le programme ne remplace pas cette appréciation par un storyboard. Originaux, V1 et autres finales sont préservés; seuls des temporaires du job peuvent être nettoyés après livraison vérifiée.
