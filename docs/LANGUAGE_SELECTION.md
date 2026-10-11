# Sélection de la langue française

Depuis `1.4.0`, lorsque le jeu contient déjà une colonne française, le patch
écrit le même texte final dans cette colonne et dans l'emplacement allemand.
L'emplacement allemand reste nécessaire tant que le menu n'expose pas le français
natif. Les anciennes versions conservent leur fonctionnement sans ajout de langue.
Restaurer remet exactement le fichier sauvegardé avant le patch, y compris les
textes français fournis par le jeu lorsqu'ils existent.

## Fonctionnement actuel

L’installateur n’impose pas automatiquement la langue. Après installation,
l’utilisateur choisit « Français » dans les paramètres du jeu.

## Valeur enregistrée par le jeu

KuloNiku utilise les préférences Unity du domaine
`com.gambirstudio.kuloniku`. La clé `I2 Language` contient le nom interne de
l’emplacement sélectionné. Comme le patch réutilise l’emplacement allemand, la
valeur interne correspondant au français est actuellement `German`.

La démo et le jeu complet ont le même identifiant d’application et partagent
donc cette préférence.

## Après une restauration

La restauration remet les textes allemands d’origine sans modifier la préférence
`I2 Language`. Si « Français » était sélectionné, l’interface apparaît donc en
allemand au lancement suivant. Il suffit de choisir une autre langue dans les
paramètres. Les sauvegardes de partie ne sont pas concernées.
