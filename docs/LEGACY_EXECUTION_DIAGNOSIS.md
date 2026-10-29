# Productions historiques : ce qui a réellement tourné

Diagnostic du 29 octobre 2026. Les chemins ci-dessous sont relatifs à `~/Documents/`, sauf les sessions natives. Les anciens fichiers n'ont été ni modifiés ni supprimés. Aucun historique Git n'a été réécrit.

## Conclusion et niveau de preuve

**Les productions existaient réellement avant le 26 octobre.** Les sorties de commandes, journaux FFmpeg, contrôles audio/vidéo et empreintes de livraison le démontrent. Le fonctionnement « une instruction » était une orchestration par l'agent : recherche en ligne, création/adaptation de scripts, téléchargements, examen des images, annotations, rendu, corrections puis livraison. Il ne correspondait pas à une ancienne commande `ultra produce` retrouvée.

Le premier `produce` ne rétablissait qu'une partie de cette chaîne. Son passage de tests synthétiques ne démontrait ni une production sportive réelle, ni l'identité d'un boxeur, ni un KO. Les anciennes productions avaient également des limites : une partie des annotations était heuristique ; l'écoute/visionnage continu n'était généralement pas effectué ; télécharger une vidéo publique ou une piste officielle ne prouvait pas ses droits de rediffusion.

Preuves conservées dans `output/legacy-reconstruction-20261029/` :

- `native_command_evidence.json` : appels Claude et résultats appariés ; un lancement en arrière-plan reste un lancement, pas une preuve de fin.
- `codex_executed_commands.json` : 1 520 enregistrements natifs `CommandExecution`, avec commande, répertoire, statut, code de sortie et extrait. Ils couvrent aussi des tâches connexes utilisant l'environnement Boxing-Tubeviz : ce n'est pas un décompte de 1 520 productions.
- `music_acquisition_commands.json` : recherche et acquisition des bibliothèques musicales.
- `evidence_files.json` : existence et SHA-256 de 38 scripts/manifests/rapports originaux consultés.
- `reconstructed_music_order.json` : ordre et intervalles exacts des quatre bandes-son, copiés des manifests conservés.

Une commande `cat script.py` prouve une lecture, pas son exécution. Un script créé, un prompt, une réponse d'agent ou un lancement asynchrone ne suffisent pas. Les résultats ci-dessous sont **des preuves historiques relues**, pas de nouveaux décodages de masters aujourd'hui absents.

## 1. Marcos-Maidana-Reggaeton

1. **Découverte vidéo exécutée** : `scripts/search_sources.py`, recherches `ytsearch12` par adversaire et contexte, puis métadonnées/formats. Session Claude `~/.claude/projects/-Users-benjamindacunha/b4ced7f8-87f3-46e2-afba-71536ccda152.jsonl`, appel ligne 361, résultat ligne 364 contenant les candidats. `scripts/music_search.py` recherchait séparément les enregistrements musicaux et comparait titres/versions.
2. **Acquisition exécutée** : `scripts/download_music.py`, neuf identifiants sélectionnés, bestaudio → MP3, tags, durées et contrôle de décodage. Appel Claude ligne 344, résultat 352. Les proxies et fenêtres HD venaient de `download_sources.py`, `download_hd.py`, `hd_parallel.sh`. `logs/download_khan.log` contient les téléchargements terminés et le merge. Les fenêtres HD étaient alignées sur les proxies par corrélation, car un seek de téléchargement n'était pas une origine temporelle fiable.
3. **Musique exécutée** : `scripts/build_audio.py`, suppression des silences de bord, gains statiques, neuf morceaux entiers, 1 811,107 s, sans crossfade dans ce master. Appels Claude 430/445, résultats 437/448. Ordre : Gato de Noche → Rompe → Rakata → PUNTO 40 → Caile → Safaera → Bichiyal → CLASSY 101 → Dale Don Dale. `timeline/full_music.json` conserve les artistes et intervalles. L'attribution ultérieure Content ID de Bichiyal reste contradictoire ; ne pas la résoudre par supposition.
4. **Montage exécuté** : `scripts/edit.py`, `build_mix.py`, annotations et sélection corrigée, téléchargement de 548 fenêtres HD, puis 892 plans. La session Codex `~/.codex/sessions/2026/10/25/rollout-2026-10-25T10-52-22-01a172b0-a760-7091-8465-5c0782a52561.jsonl:632` enregistre la fin avec code 0 de `caffeinate -i .../python -u scripts/edit.py render > logs/resume_render.log`. La reprise contient de vrais échecs/réparations de caches avant cette fin.
5. **Export livré** : `analysis/final_checks.json`, `JOURNAL_AGENTS.md` : 1 811,133333 s, 54 334 images, 1080p30, 2 204 091 644 octets. Le contrôle historique porte sur 13 impacts annotés sur 13 à ±80 ms, avec une incertitude d'annotation explicitement présente ; cela ne valide pas tous les coups. Le SHA master/copie Bureau consigné est `ce032f0eba399c42a404944969bf00f4b9242a62dfe02bcaa98760f889daa1dd`.

## 2. Latino-Boxing-Kings

1. **Découverte exécutée** : `scripts/find_sources.py`, 22 requêtes initiales, caches `sources/search_*.json`, puis recherches supplémentaires. Session Codex `.../2026/10/24/rollout-2026-10-24T20-37-40-01a16f6b-3895-7aa1-aaeb-fe9fbb828523.jsonl:97` : code 0 de la recherche. Les manifests couvrent 30 sources de combat/20 boxeurs. Le champ historique `availability` précise que le téléchargement public ne prouve pas une licence de publication.
2. **Acquisition exécutée** : `scripts/download_sources.py`, logs par source, `sources/sources.json` avec fichiers, résolutions, durées et URLs. Le téléchargement global interrompu (ligne 186, code 143) ne prouve pas une fin ; les reprises, logs de sources et manifests renseignés sont les preuves complémentaires.
3. **Bibliothèque musicale réellement acquise avant le montage** : session Claude `af622507-040f-4fe7-99d8-0b7385046959.jsonl`. `resolve.py` interrogeait YouTube Music et produisait `candidates.tsv`, puis `scratchpad/dl.sh` utilisait yt-dlp/FFmpeg pour extraire les MP3 et leurs tags. Appel 211 pour Reggaeton-10, 258 pour Reggaeton-10-B ; résultats 315 et 359 : respectivement 10 et 11 MP3 et vérifications de durée pour les lots B/C. Cette bibliothèque n'était pas fournie par l'API Spotify. Le caractère officiel d'un upload était un contrôle d'identité musicale, pas une autorisation de rediffusion.
4. **Sélection/mix exécutés** : 31 pistes analysées, neuf utilisées dans `timeline/full_music.json` : Yandel 150 → La Bebe (Remix) → DEGENERE → Mujerón → Holanda → Tití Me Preguntó → VENTE CONMIGO → La Jumpa → Dembow y Reggaeton. `analyze_audio.py`, `build_full_music.py` : attaques/sections/énergie, gains, fondus et paroles d'introduction. Les 31 analyses ne sont pas 31 utilisations.
5. **Montage et corrections exécutés** : `edit_full.py`, contrôles de passages, retrait de 7 secondes de remplissage silencieux : 1 808,7 → 1 801,7 s. Même session Codex : rendus corrigés lignes 2012 et 2276, code 0, après essais échoués. `analysis/final_probe.json` confirme 1 801,7 s, H.264 1920×1080, 30 fps. SHA final/copie Bureau consigné : `29c4973b5f2fb9fd59b6c18a6f62650b28a8b802d52149a99df8ee6fc127a8a9` ; journal du 25 octobre, 07:04 UTC.

## 3. « 90s Boxing Kings » : Boxing-Tubeviz / Golden Era hiphop90s

La correspondance retrouvée est `golden_era_30min_tyson_hiphop90s.mp4`. Ce n'était pas un nouveau montage vidéo à chaque remplacement musical.

1. **Socle vidéo antérieur** : `golden_era_cut.py`, `boxing_score.py`, `golden_era_30min.py`, bibliothèque Boxing-Auto-Edit et moteur Tubeviz. Le code et les timelines conservent 27 sources, zones d'intensité, annotations spécifiques, CLIP et empreintes perceptuelles pour limiter les replays. Les seuils CLIP/« chute » n'étaient pas des preuves universelles de KO. Les logs/timelines documentent le socle ; le détail de chaque téléchargement initial n'a pas été réapparié à une sortie native dans cet audit.
2. **Musique acquise réellement** : même session Claude `af622507-...`, recherche YouTube Music ligne 133, résolution ligne 151, `dl.sh ~/Music/Hip-Hop-90s-50` ligne 293 ; résultat ligne 381 : 50 MP3, 50 vérifiés, 411 Mo. Les résultats de la résolution ne sont pas confondus avec ceux du téléchargement.
3. **Remix exécuté** : `remix_hiphop90s.py` réutilise `build_soundtrack.py` et onze fichiers de cette bibliothèque. Mesure LUFS avec FFmpeg, choix d'entrées musicales autour des temps détectés, transitions, discours Tyson préservé jusqu'à 24,85 s, musique à 25 s. Les onze titres et les véritables débuts (par exemple 182,033 s, pas la cible théorique 180 s) sont dans `logs/hiphop90s_mix.json`.
4. **Échec puis réussite observés** : session Codex `.../2026/10/24/rollout-2026-10-24T19-16-38-01a16f21-09b8-7dd0-b083-945fdd886bcc.jsonl:96`, code 1 (parsing du JSON loudnorm) ; correction `JSONDecoder.raw_decode`, reprise ligne 151, code 0.
5. **Export** : copie du flux vidéo avec `-c:v copy`, nouveau mix AAC. `logs/hiphop90s_checks.json` : 1 800 s, 54 000 images, 1080p, flux vidéo identique, décodage complet code 0, −19,1 LUFS, −1,9 dBFS. SHA master/copie Bureau consigné : `40459fbd0236a61daa02a9753cc55afe15aa77c2422f32159ddb3b7daf62b384`. L'écoute subjective intégrale est explicitement fausse.

## 4. Haaland-Ragnar

1. **Découverte** : `scripts/find_sources.py`, adapté du projet Ronaldo, 24 requêtes par saison/club/match, Norvège, scènes Ragnar et ambiances ; `ytsearch10`, quatre workers, caches par requête. Les caches et sources renseignées attestent les résultats ; la seule présence de la liste de requêtes n'établit pas que chaque requête a été relancée à chaque version.
2. **Acquisition** : proxies 360p, sources HD entières ou fenêtres via `download_proxies.py`/`download_hd.py`, correction d'offset par `align_sections.py`. Métadonnées et registres réutilisables, pas besoin de télécharger tous les rushes en HD avant de planifier.
3. **Musique** : deux sources `cixr-7fMWwU` et `KOTHh0EXLGU`, analyses par quatre dépôts épinglés (`analysis/audio_analysis.json`). Leurs noms sont liés aux sources réellement présentes dans `timeline/soundtrack_v5.json`. Le second titre/son attribution Content ID restent ambigus. `build_audio.py` a réellement produit 334,84227 s : session Claude `1d6bc6c0-39dc-448e-913d-27d20bf3db80.jsonl`, appel 1494, résultat 1501, après correction de sérialisation NumPy.
4. **Montages successifs exécutés** : `build_timeline.py`, `render.py`, versions v1 à v4 et patch v5. Les logs v1/v2 comportent les temps CPU et durée totale. La session Codex `.../2026/10/25/rollout-2026-10-25T10-43-35-01a172a8-9b87-78b0-af03-c5ee82b9653f.jsonl` conserve les rendus v3/v4 (908/1392, code 0), deux échecs du patch v5 (1570/1669), puis sa réussite ligne 1704 (timestamps d'images corrigés).
5. **Livraison du 25 octobre démontrée** : `analysis/delivery_v5.json`, vérifié historiquement à 12:48:45 UTC : fichier final et `~/Desktop/Haaland × Ragnar.mp4`, 872 854 157 octets, SHA `03080b1dfd1a38b6d18dd50a4cdef66ab9fc453470387eb95baa92d56fa129d8`. Insertion de 3 s à 180–183 s, source 314,7–317,7, reprise musicale à 183 s ; durée du mix v5 337,84227 s. 37 cibles de synchronisation et 20 078 paquets vidéo préservés. `full_continuous_watch_with_listen=false`.

## Comparaison et corrections apportées à produce

| Étape | Régression ou manque constaté | Correction exécutée / limite restante |
|---|---|---|
| Découverte | Une requête, cinq résultats, anciens caches ignorés | Trois requêtes sportives de dix résultats, jusqu'à trois requêtes historiques complémentaires, cache par requête, deux workers, erreurs partielles conservées. Import des anciens `sources.json`, `proxies.json`, `sources/search*` sans exécuter les anciens scripts. |
| Ressources persistantes | Les preuves de sources n'étaient pas indexées ; URLs autorisées recontactées inutilement | 1 478 URLs historiques distinctes importées au scan mesuré. Réutilisation d'une copie locale autorisée, même si l'hôte n'est plus disponible. Pas de permission déduite d'un cache. |
| Médias directs | Tout passait par yt-dlp, même un fichier original HTTPS | Téléchargement direct par curl pour les extensions média, validation ffprobe avant promotion du fichier partiel, cache par URL. Échec HTTP explicite ; aucun cookie, proxy ou contournement d'authentification. |
| Historique musical | `audio_analysis.json` était traité comme une utilisation | Analyse = identité seulement ; liaison par chemin à une timeline. Migration conservatrice des anciennes exclusions erronées vers `unconfirmed_history`, sans jeter leur preuve. 89 occurrences de timelines et 65 anciennes entrées non confirmées au scan mesuré, contre 154 toutes confondues auparavant. Une timeline seule reste étiquetée « export non revérifié ». |
| Niveau sonore | Fondus sans mesure préalable | Reprise du calcul LUFS/gain statique du remix 90s, limite de crête, rapport `audio_levels.json`, fondu final. Pas d'invention de grille harmonique. |
| Syntaxe | Sujet obligatoirement présent dans une petite liste | Syntaxe `<sujet> <durée> <style>` acceptée hors des presets, sans inventer l'identité des images. |
| Licences | Pas de crédits dans les métadonnées finales | Provenance/permission musicale conservées et crédits documentés propagés dans la description locale. |
| Analyse sémantique | Le CLI ne remplace pas l'inspection de l'agent | Maintenu explicite : mouvements ≠ KO ; annotations/revue nécessaires. Pas de modèle de KO validé sur ces anciens rushes absents. |
| Montage avancé | Proxy→HD, discours/ducking, courbes d'intensité, correspondance perceptuelle intersources et sélection musicale éditoriale non portés intégralement | Composants historiques identifiés et préservés ; pas de port aveugle de scripts liés à un sportif. Les plans courts de l'ancien Golden Era ne satisfont pas nécessairement la nouvelle contrainte d'actions complètes. Ces fonctionnalités ne sont pas déclarées restaurées. |

L'exigence de droits n'est pas une panne à supprimer. Les anciens téléchargements prouvent l'acquisition ; ils ne suffisent pas à autoriser une nouvelle diffusion. L'agent peut documenter une licence publique explicite et enregistrer la ressource sans demander à l'utilisateur de chercher/déplacer le fichier. Un accès Spotify manquant, une licence non établie ou une durée de matière insuffisante restent de vrais blocages.

## Démonstration sur des médias réels

La commande `ultra produce "Boxing 16s orchestral"` a téléchargé deux vidéos réelles et une musique depuis leurs liens originaux publics, puis utilisé le moteur actuel `create` et FFmpeg. Les pages de licence ont été recherchées et lues par l'agent ; leurs preuves sont dans `real-media/permission_evidence.json`. L'agent a inspecté les images et créé deux annotations avant la reprise `--strict-actions`. Aucun fichier n'a été préparé par l'utilisateur.

Les tentatives restent conservées : échec de l'extracteur yt-dlp sur les URLs de fichiers, acquisition directe réussie, arrêt strict faute d'annotations, puis rendu. L'accès direct est celui proposé par les pages Commons, sans authentification ou modification des restrictions. Le moteur ne découvre pas à lui seul la propriété intellectuelle ni l'identité sportive.

Sortie : `output/legacy-reconstruction-20261029/real-exports/20261029-105924-286000/boxing-16s/` : MP4, miniature, storyboard, timeline, tracklist, métadonnées, sources, rapport de niveaux et vérifications. Deux fenêtres, 0–14 s de shadowboxing d'Evworo et 3,5–5,5 s du fragment historique *Men Boxing* ; aucune répétition ni remplissage ajouté. Le film historique est de basse résolution ; la sortie 1080p ne recrée pas son détail. Accompagnement US Marine Corps Band, domaine public ; contribution dérivée proposée sous CC BY-SA 3.0, crédits inclus.

Contrôles réels : durée 16,021029 s, H.264 1920×1080 à 30 fps, décodage complet, aucune alerte noir/gel/silence, crête −7,8 dBFS, décalage de début des flux 21,029 ms. Corrélation audio avec la source sur les 12 premières secondes : 0,9928376, meilleur décalage 5 ms. Images sources et 32 images du rendu examinées ; pas d'écoute/visionnage continu. Rapport reproductible : `real_media_acceptance.json`, script `verify_real_demo.py`.

**C'est une démonstration technique réelle de 16 secondes, pas un Canelo/reggaeton de 30 minutes et pas une validation des KO.** La chaîne agent + CLI fonctionne pour ce jeu autorisé. La parité éditoriale complète et la production arbitraire depuis le seul CLI ne sont pas établies. Les tests de code complètent cette preuve, ils ne la remplacent pas.

## Suppressions et récupération

Le Bureau du 25 octobre et les fichiers absents aujourd'hui sont compatibles : les suppressions sont postérieures aux preuves de livraison. Les journaux Latino/Boxing-Tubeviz mentionnent déjà des suppressions le 25 ; le manifeste `Systeme/sauvegardes/cleanup_old_videos_20261026.txt` liste ensuite 793 chemins de médias/caches supprimés. `~/FILE_INDEX.md` décrit ces opérations. Il serait incorrect de dater toute disparition du seul 26 octobre.

La Corbeille a été inspectée sans modification et était vide ; aucun Time Machine ordinaire n'a été trouvé, seulement des snapshots de mise à jour macOS. Cela n'exclut pas une sauvegarde externe/cloud. Aucun ancien média n'a été restauré par magie à partir d'un manifest, et aucune suppression supplémentaire n'a été faite ici.

## Contrôle final du 29 octobre

61 tests passent en 2,82 s ; lint ciblé E9/F et `git diff --check` passent. Le lint stylistique complet conserve des avertissements, non présentés comme un succès. Les 38 fichiers historiques empreintés sont inchangés. Une réexécution du cas réel réutilise ses téléchargements et refuse sa chanson déjà utilisée. Le nouvel essai Canelo en ligne exécute quatre requêtes et conserve 31 candidats sans erreur de recherche ; il bloque précisément sur Spotify non connecté et l’absence de vidéos/musiques correspondantes avec permissions documentées. Voir `acceptance_summary.json` et `canelo-live/20261029-110206-208000/production_report.json`.

## Revalidation de production — 29 octobre, après 11:30 UTC

Le résultat courant est décrit dans [PRODUCTION_VALIDATION.md](PRODUCTION_VALIDATION.md) et le dossier local `output/final-validation-20261029/`. Il ne remplace pas les preuves historiques ci-dessus. L'acquisition de l'interview Tyson autorisée le 21 octobre a maintenant réussi, puis son décodage intégral a passé. Le choix du téléchargeur utilisait auparavant le PATH global (2026.07.04), malgré le module 2026.10.21 disponible dans le venv ; recherche, acquisition et doctor utilisent maintenant le même choix d'environnement. Il n'est pas établi que la seule version explique l'ancien HTTP 403.

La bibliothèque `~/Music/Hip-Hop-90s-50/` est présente : 50 pistes numérotées plus un fichier Roy Jones, 51 fichiers au total. Toute lecture des notes de nettoyage suggérant sa disparition intégrale est contredite par les fichiers actuels. Leur présence ne constitue ni une permission de montage ni une absence d'usage antérieur : 12 familles sont déjà dans l'historique accessible. Les fichiers vidéo/audio des trois anciens projets restent absents.

Spotify indisponible ne bloque plus une demande de genre seule disposant de musique locale admissible ; une playlist explicitement demandée reste une contrainte. Les rapports distinguent présence, permissions, durée brute et couverture éditoriale non vérifiée. Aucun montage réel de 30 minutes n'a été produit pendant cette revalidation ; les 70 tests réussis ne valident pas cet objectif.
