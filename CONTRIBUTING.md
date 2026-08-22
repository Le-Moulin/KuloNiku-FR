# Contribuer à KuloNiku FR

Merci de vouloir améliorer le patch. Les contributions humaines et celles
assistées par un agent sont les bienvenues, à condition de rester vérifiables et
de ne jamais publier les fichiers du jeu.

## Proposer une correction sans programmer

Le plus simple est d’utiliser le formulaire
[Proposer une correction française](https://github.com/Le-Moulin/KuloNiku-FR/issues/new?template=translation.yml).

Indiquez si possible :

- le texte vu dans le jeu ;
- votre proposition ;
- le personnage, l’écran ou la situation ;
- une capture montrant la place disponible.

La clé technique est facultative. Pour un souci avec l’application, utilisez
plutôt le formulaire
[Signaler un problème d’installation](https://github.com/Le-Moulin/KuloNiku-FR/issues/new?template=installation.yml).

## Proposer une modification avec Git

La traduction publique se trouve dans `translations/fr.csv`. Une pull request
doit rester courte et indiquer :

- les phrases ou le lot modifiés ;
- la raison du changement ;
- la version du jeu utilisée ;
- ce qui a été vérifié en jeu et ce qui reste à vérifier.

Consultez aussi le [glossaire](docs/TERMINOLOGY.md) pour conserver les choix déjà
harmonisés.

## Relire avec tout le contexte

L’[espace de relecture hors ligne](docs/REVIEW_WORKSPACE.md) réunit les autres
langues, les clés voisines et le contexte depuis votre propre installation du
jeu. Explorez librement les textes et exportez uniquement les passages sur
lesquels vous souhaitez intervenir.

La méthode la plus simple consiste à ouvrir l’application Windows ou macOS,
sélectionner le jeu, ouvrir **Options avancées**, puis cliquer sur **Réviser et corriger
les traductions**. La commande manuelle reste disponible pour les personnes qui
travaillent depuis les sources.

Pour vérifier une formulation en situation, exportez les propositions depuis
l’espace puis utilisez **Importer mon fichier de correction** dans **Options avancées**.
Le fichier est contrôlé et l’installation reste précédée d’une simulation.

L’outil repère automatiquement les clés sans traduction française, propose une
vue en liste et prépare le résumé à joindre à une issue GitHub.

[Suivre le tutoriel et créer votre espace de relecture](docs/REVIEW_WORKSPACE.md)

Une fois le travail exporté, utilisez le formulaire
[Transmettre une relecture préparée](https://github.com/Le-Moulin/KuloNiku-FR/issues/new?template=review.yml).

Ne publiez jamais l’espace HTML généré : il contient les textes sources du jeu.

## Règles communes

- Ne modifiez jamais les clés, variables (`{0}`, `{PLAYER_COLOR}`, etc.), balises,
  retours à la ligne ou marqueurs de mise en forme.
- Préférez un français naturel à une traduction mot à mot.
- Signalez les ambiguïtés et les textes qui n’ont pas encore été vus en jeu.
- Ne publiez jamais `resources.assets`, un fichier du jeu, `work/context.csv` ou
  une extraction complète des autres langues.
- Une capture limitée à l’écran concerné et une courte citation suffisent pour
  expliquer le contexte.

## Contribuer avec un agent

Un agent comme Codex ou Claude peut aider à préparer une contribution, mais sa
sortie doit toujours être relue et vérifiée.

Donnez-lui seulement :

1. le [brief des agents de traduction](translations/AGENT_BRIEF.md) ;
2. un petit lot contenant uniquement les clés concernées ;
3. une note de contexte courte, si nécessaire ;
4. le nom du seul fichier qu’il peut modifier.

Ne transmettez pas d’historique privé, de journal de conversation ou
d’extraction complète du jeu. Le protocole complet est décrit dans le
[guide de traduction assistée par agent](docs/AGENT_WORKFLOW.md).
