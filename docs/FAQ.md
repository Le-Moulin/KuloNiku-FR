# Questions fréquentes

## Le patch fonctionne-t-il avec Steam ?

Oui. Il modifie uniquement la copie locale du jeu après une simulation et une
sauvegarde vérifiée. Le jeu se lance ensuite normalement depuis Steam.

## Comment l’installer sur Steam Deck ?

Utilisez l’AppImage native en mode Bureau. Elle recherche automatiquement le
jeu sur le stockage interne, les bibliothèques Steam et la carte microSD.

Il suffit d’autoriser l’exécution du fichier dans **Propriétés > Permissions**.
N’utilisez ni `sudo`, ni `pacman`, ni Protontricks, Wine ou l’installateur
Windows. Consultez le [guide Steam Deck](STEAM_DECK.md).

L’installation, le lancement, la restauration et la réinstallation ont été
validés sur un véritable Steam Deck avec la démo et le jeu complet.

## Démo ou jeu complet ?

Les deux sont reconnus automatiquement. La version complète est la référence.
La démo reçoit uniquement les adaptations nécessaires à son ancienne version
des textes.

## Pourquoi l’allemand disparaît-il ?

Le menu actuel masque une neuvième langue. Le patch réutilise donc l’emplacement
allemand et conserve l’anglais comme repli sûr. Restaurer le fichier original
rend immédiatement l’allemand au jeu.

## Pourquoi le jeu passe-t-il en allemand après la restauration ?

Lorsque vous choisissez **Français**, le jeu mémorise en réalité l’emplacement
interne de l’allemand. Restaurer ou désinstaller le patch remet les textes
allemands, mais ne change pas cette préférence : l’interface peut donc apparaître
en allemand au lancement suivant.

C’est normal et cela n’affecte pas votre sauvegarde. Ouvrez les paramètres du jeu
et choisissez simplement la langue souhaitée.

## Que se passe-t-il après une mise à jour Steam ?

Steam peut remettre un fichier original ou nouveau. La commande `status`
relit le vrai fichier, contrôle la présence du français et compare son SHA-256 ;
elle ne se fie pas seulement à une date ou à un numéro enregistré localement.
L’installateur refait alors une simulation sur la nouvelle version avant toute
écriture.

## Dois-je retélécharger l’application pour chaque correction française ?

Non. L’application peut télécharger et vérifier le petit lot de traduction
publié sur GitHub. Elle demande seulement une nouvelle version complète si ce
lot déclare avoir besoin d’un moteur plus récent.

Cette mise à jour intégrée reste désactivée sur Steam Deck. Téléchargez la
nouvelle AppImage lorsqu’une version est annoncée.

## Une nouvelle phrase peut-elle casser le jeu ?

Les traductions sont liées à l’empreinte des textes anglais et indonésien. Si
leur sens change, l’ancienne version française n’est pas injectée : l’anglais
installé reste affiché jusqu’à la prochaine traduction.

## Puis-je annuler ?

Oui. Chaque installation crée d’abord une sauvegarde dont l’empreinte SHA-256
est vérifiée. La commande ou le bouton **Restaurer l’original** remet cette
sauvegarde.

## Pourquoi macOS affiche-t-il parfois un avertissement ?

L’application macOS n’est pas notariée par Apple. Ne contournez jamais un
avertissement pour un fichier obtenu ailleurs que dans les releases officielles
du projet. La procédure d’ouverture sûre est indiquée dans la note de release.

## Mon antivirus Windows réagit : que faire ?

N’ajoutez pas d’exclusion générale. Fermez le programme, conservez l’alerte et
ouvrez un rapport d’installation avec la version téléchargée, son empreinte et
une capture. Le code et la fabrication des paquets sont publics.

## Comment proposer une meilleure formulation ?

Pour comparer le français aux autres langues et voir les clés voisines, ouvrez
l’application, sélectionnez le jeu, ouvrez **Options avancées** puis cliquez sur **Réviser
et corriger les traductions**. Suivez ensuite le
[tutoriel de l’espace de relecture](REVIEW_WORKSPACE.md).

Vous pouvez aussi exporter vos propositions puis utiliser **Importer mon fichier
de correction** dans **Options avancées**. Elles seront vérifiées, simulées et installées
temporairement pour un contrôle direct en jeu.

Utilisez le formulaire GitHub
[« Proposer une correction française »](https://github.com/Le-Moulin/KuloNiku-FR/issues/new?template=translation.yml).
Aucune
connaissance de Git n’est nécessaire. Indiquez le contexte et, si possible, une
capture limitée à l’écran concerné.

## Le projet continuera-t-il si le français devient officiel ?

Le patch n’a pas vocation à concurrencer une traduction officielle. Il pourra
être archivé comme outil et comme base technique pour d’autres communautés.
