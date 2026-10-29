# Production autonome locale

```sh
ultra doctor
ultra produce "Canelo Alvarez 30 minutes reggaeton"
ultra produce "Terence Crawford 30 minutes R&B 2000s"
```

Le moteur recherche les fichiers dans Documents, Music, Movies, Downloads et Desktop ; aucune copie manuelle vers `library/` n'est nécessaire. `--root DOSSIER` limite le scan et peut être répété. `--offline` désactive la découverte/téléchargement vidéo. Une playlist Spotify demandée nécessite toujours l'API.

Les sorties sont isolées dans `output/productions/<horodatage>/`. Un `production_report.json` explique chaque blocage. Avec assez de ressources autorisées : MP4, miniature photographique extraite, storyboard, timeline, intégrité des fenêtres, sources, tracklist, exclusions, métadonnées et vérification technique. Les exports restent `TECHNICAL_PASS_REVIEW_REQUIRED` : la reconnaissance sportive n'est pas certifiée.

## Catalogue et autorisations persistantes

État par défaut : `~/.local/share/youtube-edit-ultra/`. JSON atomiques, verrou interprocessus, SHA-256 des médias et cache ffprobe. Les morceaux utilisés restent exclus même si leur fichier est supprimé. `--state-dir` permet un catalogue isolé (tests). Ne pas ajouter ce dossier à Git.

```sh
ultra catalogue scan
ultra catalogue authorize /chemin/source.mp4 --evidence "Contrat ou permission du titulaire, référence et périmètre"
ultra catalogue authorize /chemin/musique.wav --evidence "Permission pour ce montage et cet usage"
ultra catalogue authorize-url https://exemple.org/source.mp4 --kind video --athlete "Canelo Alvarez" --evidence "Autorisation de téléchargement et de réutilisation, référence"
```

Une autorisation locale porte sur le contenu SHA-256, pas seulement le nom du fichier. `authorize-url` atteste les deux permissions, téléchargement et réutilisation, et conserve l'URL pour les productions suivantes. Pour de l'audio autorisé distant, `--kind audio --style reggaeton --artist "..." --title "..."` renseigne l'identité ; jamais une URL Spotify.

La découverte publique conserve URL, titre, chaîne et licence déclarée. Aucun téléchargement depuis une chaîne inconnue sur la seule mention CC. Le champ `trusted_cc_publishers` de `config.json` peut contenir les URL de chaînes dont l'utilisateur a établi l'autorité : seules leurs sources marquées CC BY sont admissibles automatiquement. Toute attribution/licence reste à contrôler pour l'usage prévu. Les fichiers sans preuve restent des candidats bloqués.

`config.json` accepte `roots` (liste de chemins), `playlists` (style → URI) et `trusted_cc_publishers`. Aucun token ne doit y être placé. Les caches et le catalogue sont réutilisables. Les manifests historiques malformés bloquent la sélection fiable ; les autres erreurs de scan restent visibles.

## Spotify : connexion unique, lecture complète

Créer/utiliser une application Spotify Developer et enregistrer exactement `http://127.0.0.1:8769/callback` comme redirect URI, puis :

```sh
ultra spotify login --client-id IDENTIFIANT_PUBLIC
# Ouvrir l'URL imprimée, consentir dans Spotify.
ultra spotify finish 'http://127.0.0.1:8769/callback?code=...&state=...'
ultra spotify list
ultra spotify sync spotify:playlist:IDENTIFIANT --style rnb-2000s
```

Le callback se recopie depuis la barre d'adresse après redirection ; aucun serveur local n'est nécessaire et la page peut indiquer connexion refusée. Ne pas partager cette URL. Codes PKCE/tokens sont stockés en fichiers privés 0600 et le token est rafraîchi. Les scopes concernent uniquement la lecture des playlists. L'accès effectif dépend du compte, des permissions et du mode de l'application Spotify.

Avec une connexion existante, `produce` cherche une playlist de style au nom compatible et mémorise une correspondance unique ; plusieurs correspondances demandent une association explicite avec `sync`. Les pages `/playlists/{id}/items` sont parcourues jusqu'à la fin avec total/snapshot contrôlés. Les entrées locales, nulles ou indisponibles sont comptées. Les URI, artistes et métadonnées restent dans les rapports. Une erreur 401/403/429 ou une pagination incomplète ne devient jamais une playlist vide prétendument complète.

L'association audio exige le même titre/version et artiste, plus une durée compatible si disponible. Les familles de titres sont utilisées uniquement pour exclure les variantes déjà employées. Pour `rnb-2000s`, une date 2000–2009 documentée dans les tags ou métadonnées est nécessaire ; une date d'album réédité peut conduire à une exclusion conservatrice. Ces métadonnées ne constituent pas une autorisation musicale.

Références officielles : [PKCE](https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow), [playlist items](https://developer.spotify.com/documentation/web-api/reference/get-playlists-items), [redirect URI](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri).

## Vérification et limites

`produce` appelle les fonctions existantes de création, sans répétition musicale ni publication. L'analyse de mouvement et les modèles locaux optionnels fournissent des candidats ; `--strict-actions` exige des annotations `<source>.actions.json`. Les fenêtres complètes ont priorité sur le beat. Les doublons binaires sont écartés ; les replays/réencodages visuellement identiques exigent encore une relecture.

Vérification : FFprobe (H.264, durée, flux), décodage FFmpeg complet, décalage temporel audio/vidéo, crête audio et signalement des noirs/gels/silences. Ce contrôle ne prouve ni les noms des boxeurs, ni les KO, ni la synchronisation artistique de chaque impact. Le storyboard aide la revue sans la remplacer.

Tests : `.venv/bin/pytest`. Le test de bout en bout crée une vidéo et une musique originales synthétiques, exécute `produce`, décode le MP4, mesure la corrélation audio, puis vérifie qu'un second montage refuse la même chanson. Ce test vérifie la chaîne technique, pas un combat réel.

Reconstitution étayée et essai sur médias réels : [LEGACY_EXECUTION_DIAGNOSIS.md](LEGACY_EXECUTION_DIAGNOSIS.md). L’essai réel dure 16,021 s ; il ne valide pas la reconnaissance des KO ni un montage Canelo de 30 minutes.

## Comportement vérifié le 29 octobre : accès et permissions séparés

Une demande de genre seule peut continuer avec les fichiers locaux autorisés si Spotify est absent ou inaccessible, même si une playlist de genre avait été mémorisée. Le rapport indique `local_fallback` et `membership_verified=false`. Une playlist explicitement demandée (`--playlist`, URL/URI dans le prompt, ou mention Spotify/playlist) reste obligatoire : aucune substitution silencieuse. Les règles d'exclusion des morceaux connus restent actives dans les deux modes.

`readiness_report.json` distingue fichiers techniquement accessibles, durée brute autorisée, musique admissible après fondus, preuves de permission manquantes et couverture éditoriale non vérifiée. Les durées brutes ne prouvent ni 30 minutes d'actions ni l'absence de replays. Le nom du dossier personnel n'est plus utilisé comme indice d'identité du sportif.

Recherche et acquisition utilisent le module `yt_dlp` de l'environnement Python courant lorsqu'il est installé ; le binaire global n'est qu'un recours. `doctor` affiche la commande et la version réellement choisies. Cela corrige la sélection d'une ancienne version globale ; cela ne garantit pas de résoudre un refus HTTP du fournisseur.
