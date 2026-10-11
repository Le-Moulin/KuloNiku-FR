# KuloNiku FR 1.4.0

Le patch prend en charge le jeu complet 1.2.0 (build Steam 25780236), testé en jeu sur macOS. La compatibilité avec le jeu complet 1.1.1 et la démo est conservée.

## Changements

- Versions inconnues acceptées lorsque la table I2, l’anglais et des clés françaises compatibles sont présents ; avertissement et repli anglais pour les textes sans traduction compatible.
- Simulation avant installation, sauvegarde vérifiée, écriture atomique et restauration protégée contre le remplacement d’une nouvelle version par un ancien original.
- Injection du français dans `de` et dans `fr` lorsque cette colonne existe, sans changer les autres langues ni les autres objets Unity.
- 346 clés ajoutées, 109 sources modifiées, aucune clé supprimée. Les variantes de traduction conservent les références des anciennes versions.
- 290 traductions françaises natives approuvées. Résultat du nouveau jeu : 13 469 traductions compatibles ; les 50 cellules de repli ont une source anglaise vide.
- Compilation macOS explicitement ciblée sur macOS 11, avec contrôle de la version minimale de chaque binaire ARM64/Intel avant signature.
- Sur macOS, seuls les paquets de traduction strictement plus récents peuvent remplacer le paquet actif ; une empreinte différente ne suffit plus.

## Validation et limites

- 76 tests automatisés réussis ; 4 ignorés faute d’un artefact historique de laboratoire.
- Constructions sur les fichiers réels du nouveau jeu, de l’ancien jeu complet et de la démo ; seul l’objet I2 change.
- Simulation, installation, restauration au SHA-256 exact et réinstallation vérifiées sur copie réelle.
- Compilation du lanceur pour ARM64 et Intel, signature, autotest moteur et huit scénarios de mise à jour vérifiés. Cible macOS 11 ; pas de test sur chaque ancienne version du système.
- Test global en jeu concluant sur le jeu 1.2.0. Huit entrées restent provisoires : `VND8_17`, `VND8_CHOICE_4`, `VNU8_CHOICE_4`, `VNU8_CHOICE_5`, `VNU8_25`, `VNU8_26`, `VNU8_27` et `Tag Mapping/`.
- Deux dépassements de longueur du nouveau lot sont documentés : « Nouvelle recette » et `Tag Mapping/`. Les avertissements de longueur historiques ne remplacent pas une validation visuelle de chaque texte.

Aucun fichier original ou reconstruit du jeu n’est distribué. Les applications Windows, macOS universelle et Steam Deck sont construites par le workflow de publication du tag `v1.4.0`.
