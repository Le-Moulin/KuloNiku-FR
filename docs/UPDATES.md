# Mises à jour du jeu, des traductions et de l’installateur

Ce document couvre les interfaces macOS, Windows et Steam Deck, leur moteur de
patch commun et les petits lots de traduction téléchargeables séparément.
L’AppImage Steam Deck n’active pas les mises à jour intégrées : une
nouvelle AppImage doit être téléchargée manuellement. Le projet distingue trois
versions indépendantes.

| Axe | Exemple | Action |
|---|---|---|
| Jeu Steam | table I2 ou fichier modifié | simuler le fichier actuel, sauvegarder, puis repatcher |
| Traductions | nouveau lot français | télécharger le petit lot vérifié, puis mettre à jour directement |
| Application / moteur | nouvel installateur ou moteur de patch | informer, sans installation forcée |

## État local

`kuloniku-fr status CHEMIN_DU_JEU` compare :

- l’empreinte du fichier actuellement installé ;
- le manifeste de la dernière sauvegarde ;
- la présence du libellé français ;
- l’empreinte du lot de traduction local ;
- la version du moteur qui a effectué l’installation.

Il n’écrit rien. Une mise à jour Steam est signalée comme un fichier à simuler
et repatcher, jamais comme une invitation à écraser silencieusement le jeu.

## Contrat de release

Chaque tag publie les applications macOS/Windows, leurs empreintes SHA-256, un
lot autonome `translations.zip` et un petit
`update-manifest.json`. Celui-ci contient une empreinte distincte pour la
traduction du jeu complet et celle de la démo, l’empreinte du téléchargement et
la version minimale du moteur capable de lire ce format de lot. Cette version
minimale n’augmente pas à chaque nouvelle version de l’application.

Depuis la version `1.3.0`, l’AppImage Steam Deck et son empreinte sont publiées
avec les paquets Windows et macOS dans chaque release stable.

Les interfaces interrogent la dernière release publiée sur GitHub sans bloquer
leur usage. Une version plus récente de l’application ou du moteur est signalée
par un bouton qui ouvre la release : elle n’est jamais téléchargée ni installée
silencieusement.

Sur macOS comme sur Windows, cette vérification de l’application démarre dès
l’ouverture, même si le jeu n’a pas été trouvé. Le contrôle des traductions
reste effectué après l’identification de l’édition installée.

Si l’empreinte de traduction de l’édition détectée diffère, les applications
macOS et Windows téléchargent automatiquement le petit lot, contrôlent son
SHA-256, l’ouvrent dans un cache utilisateur puis demandent au moteur de
confirmer son empreinte logique avant de le proposer. Le jeu n’est jamais
patché sans confirmation.

La disponibilité d’une nouvelle application est signalée indépendamment du lot
de traductions. Si le lot reste compatible avec le moteur courant, il est tout
de même téléchargé et peut être appliqué immédiatement. S’il demande un moteur
plus récent, aucun fichier n’est appliqué et le téléchargement de la nouvelle
application devient prioritaire. Lorsque le moteur courant suffit, la mise à
jour du jeu conserve la sauvegarde originale ; aucune restauration préalable
n’est demandée.

## Versions proposées

L’application recherche la dernière version publiée dans le dépôt
`Le-Moulin/KuloNiku-FR`. Une application stable ignore toujours les
préversions et reste sur le canal stable. Seules les applications elles-mêmes
publiées en bêta, RC ou autre préversion peuvent proposer une nouvelle
préversion ; elles acceptent également une version stable plus récente.

## Après une mise à jour Steam

Depuis `1.4.0`, la présence d'une colonne française dans le jeu ne signifie pas
que KuloNiku FR est installé. Seule la correspondance exacte avec le fichier
patché enregistré permet de reconstruire depuis sa sauvegarde précédente.
Si Steam a remplacé le fichier, le moteur travaille sur le fichier actuel et
crée une nouvelle sauvegarde vérifiée. Les anciennes sauvegardes sont conservées,
mais ne sont pas proposées pour restaurer une version différente du jeu.

Une version non testée reste installable lorsque le fichier est identifié sans
ambiguïté, que la table I2 est lisible et réécrivable à l'identique, que l'anglais
et l'emplacement allemand existent et que des traductions compatibles
correspondent. Un avertissement indique que cette version n'a pas encore été
testée. Toute tentative échouée conserve le fichier précédent et n'active pas
sa nouvelle sauvegarde comme point de restauration.

Le moteur écrit le français dans l'emplacement allemand utilisé par le menu et
dans la colonne française lorsqu'elle existe. Il n'ajoute pas cette colonne aux
anciennes versions. Les autres langues et les colonnes techniques restent intactes.

Pour chaque entrée, la priorité est : français du jeu approuvé, français
communautaire compatible, puis anglais du jeu actuel. `native-approvals.csv`
contient seulement les empreintes des textes natifs approuvés et de leurs
références ; un changement de texte invalide l'approbation. Les contrôles de
variables, balises et retours à la ligne restent obligatoires à l'exécution.
`full-overrides.csv` conserve les variantes liées aux nouvelles références sans
remplacer le profil historique, afin de garder la compatibilité des versions
précédentes et de la démo. Les paquets utilisant ces règles demandent le moteur
`1.4.0` au minimum.

Le manifeste local n’est pas pris comme preuve suffisante. À chaque ouverture,
le moteur relit la table du jeu, vérifie si le libellé français existe et calcule
le SHA-256 du véritable `resources.assets`. Si Steam remet un original ou une
nouvelle version, cette empreinte ne correspond plus ni au fichier patché ni à
l’original sauvegardé : l’état devient `game_updated` et une nouvelle simulation
est obligatoire avant de créer une nouvelle sauvegarde et de repatcher.

## Passage à une nouvelle version du jeu

1. conserver localement l’extraction de la version précédemment prise en charge ;
2. extraire la nouvelle table dans `work/` ;
3. exécuter `prepare-update-batches` ;
4. relire les clés ajoutées et celles dont l’anglais ou l’indonésien a changé ;
5. fusionner, propager les dialogues de secours identiques et lancer `lint` ;
6. conserver le profil historique et ajouter les empreintes et variantes de la nouvelle source ;
7. reconstruire puis réextraire afin de prouver l’égalité des valeurs attendues ;
8. tester visuellement avant de publier le lot de traduction.

Les clés retirées peuvent rester dans `fr.csv` : elles ne sont injectées que si
elles existent. La démo conserve ses anciennes formulations dans son seul
fichier d’exceptions plutôt que dans une deuxième traduction complète.

## Références de sécurité GitHub

- [API officielle des releases](https://docs.github.com/en/rest/releases/releases)
- [Téléchargement et empreintes des assets](https://docs.github.com/en/rest/releases/assets)
- [Vérification de l’intégrité d’une release](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/verify-release-integrity)
