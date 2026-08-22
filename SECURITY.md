# Sécurité

## Signaler un problème

N’ouvrez pas de ticket public si le problème peut permettre l’exécution de code,
le remplacement d’un fichier arbitraire, le contournement d’une vérification
d’empreinte ou l’usurpation d’une mise à jour.

Utilisez la fonction privée
[« Report a vulnerability »](https://github.com/Le-Moulin/KuloNiku-FR/security/advisories/new)
de l’onglet **Security** du dépôt GitHub.

Pour un faux positif antivirus sans détail exploitable, utilisez le formulaire
public de [problème d’installation](https://github.com/Le-Moulin/KuloNiku-FR/issues/new?template=installation.yml)
en indiquant la release, la plateforme et
l’empreinte du fichier, sans joindre de données personnelles.

## Modèle de confiance

- aucune donnée jouable ni fichier complet du jeu n’est distribué ;
- toute installation commence par une simulation ;
- la sauvegarde et les téléchargements sont vérifiés par SHA-256 ;
- les remplacements sont atomiques et restaurables ;
- une mise à jour distante ne doit jamais être exécutée automatiquement ;
- les paquets officiels proviennent uniquement des releases GitHub du projet.

## Analyses antivirus des releases

Après leur publication, les paquets Windows, macOS et Steam Deck sont soumis
automatiquement au service public VirusTotal. Les liens vers les rapports et les
empreintes SHA-256 correspondantes sont ajoutés aux notes de chaque release.

Ces analyses sont informatives : elles agrègent les résultats de plusieurs
moteurs, mais ne constituent ni une certification ni une garantie d’absence de
risque. Les fichiers soumis au service public peuvent être partagés par
VirusTotal avec ses partenaires de sécurité. Ils sont déjà distribués
publiquement dans les releases de ce projet.

Une détection, même isolée, doit être examinée humainement avant toute
conclusion. Les exécutables construits avec PyInstaller peuvent notamment
produire des faux positifs. Pour les signaler, utilisez le formulaire public de
problème d’installation indiqué plus haut en précisant la release, le paquet,
son SHA-256 et le lien du rapport VirusTotal.
