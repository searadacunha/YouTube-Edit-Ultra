# Reconstitution du workflow — 29 octobre 2026

Les anciens montages utilisaient déjà plusieurs scripts Python pilotés par un agent. Il ne s'agissait pas d'une ancienne commande `ultra` autonome à restaurer à l'identique.

| Étape | Preuves conservées sous `~/Documents/` | Fonctionnement retrouvé |
|---|---|---|
| Recherche | `Marcos-Maidana-Reggaeton/scripts/search_sources.py`, `Haaland-Ragnar/scripts/find_sources.py` | Requêtes par sportif/adversaire, `yt-dlp ytsearch`, caches JSON, contrôle des formats |
| Acquisition | `Latino-Boxing-Kings/scripts/download_sources.py`, `Marcos-Maidana-Reggaeton/scripts/download_music.py` | URLs choisies, téléchargement, ffprobe, empreintes, métadonnées ; disponibilité publique distincte des droits de publication |
| Musique | `scripts/build_audio.py`, `build_full_music.py`, `analyze_audio.py` dans ces projets | Décodage, analyse des attaques/rythmes, fondus, mix fini ; sélection en partie manuelle |
| Montage | `Haaland-Ragnar/scripts/build_timeline.py`, `render.py`, `Latino-Boxing-Kings/scripts/edit_full.py`, `Boxing-Tubeviz/golden_era_30min.py` | Timelines explicites et FFmpeg ; choix/relecture des actions nécessaires |
| Livrables | `Haaland-Ragnar/scripts/storyboard.py`, scripts `verify.py` et `publication/` des projets | Images réelles extraites, planches, métadonnées, vérification technique |

L'orchestrateur réutilise le moteur actuel (`create`, `vision`, `events`, `planner`, `music`, `render`, `thumbnail`) et ajoute la découverte, les permissions persistantes, Spotify et l'historique. Les anciens téléchargements ne constituent pas une preuve de permission pour de nouveaux usages.

## Médias manquants et récupération

Constats en lecture seule du 29 octobre 2026 :

- `~/Documents/Systeme/sauvegardes/cleanup_old_videos_20261026.txt` liste **793 chemins**, tous absents au contrôle. Son en-tête attribue le nettoyage du 26 octobre à une demande de libération du disque. Les scripts, timelines, journaux et dossiers de publication devaient être conservés.
- `~/FILE_INDEX.md` décrit les nettoyages du 25–26 octobre : rushes/caches/audio de Maidana, Latino, Valero, Haaland, Manchester et Mayweather ; plusieurs dossiers sous `~/Music/`. Les projets Inoue et Quaresma ont également fait l'objet de suppressions permanentes documentées.
- Un autre manifeste existe : `~/Documents/Cristiano-RealMadrid-DBZ/logs/cleanup_after_delivery_20261026.txt`.
- La Corbeille était vide au contrôle. Aucune modification ni vidage n'a été effectué pendant cette mission.
- `tmutil listbackups` a répondu `No machine directory found for host.` Les snapshots locaux listés étaient trois snapshots `com.apple.os.update-*`, sans sauvegarde Time Machine ordinaire identifiée. Aucun montage/restauration n'a été tenté.

Cela explique les chemins historiques manquants ; ce n'est pas la preuve qu'aucune sauvegarde externe/cloud n'existe. Récupération possible uniquement si une copie externe, une sauvegarde ou la source autorisée d'origine reste accessible. Ne pas annoncer une restauration à partir d'un manifeste seul.

## Historique musical et limites

Les manifests `full_music.json`, `music_timeline.json`, `hiphop90s_mix.json` et `mix.json` permettent de conserver les exclusions même quand les fichiers sont absents. `audio_analysis.json` sert seulement à retrouver les titres des sources déjà liées à une timeline ; une analyse seule ne prouve pas une utilisation. L'inventaire distingue les médias disponibles et leurs historiques.

Les anciens projets supprimés ne sont pas tous reconstructibles. L'attribution du second morceau de Haaland est contradictoire entre les sources et le Content ID consigné dans son README : conserver les deux identités comme exclusions conservatrices. Une absence dans l'historique accessible ne prouve pas qu'un morceau n'a jamais été utilisé ailleurs.

## État Git préservé

Le `main` local (`3e21fb4`) et `origin/main` (`2fa87b6`) avaient des racines distinctes. La branche de travail `codex/produce-20261029` est issue de `origin/main`. Le `main` local n'a pas été réécrit. Les anciens projets, médias et journaux n'ont pas été supprimés.

Diagnostic détaillé avec commandes réellement exécutées, codes de sortie et preuves de livraison : [LEGACY_EXECUTION_DIAGNOSIS.md](LEGACY_EXECUTION_DIAGNOSIS.md).
