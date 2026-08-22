# Installer KuloNiku FR sur Steam Deck

KuloNiku FR est compatible avec la démo et le jeu complet sur Steam Deck.
L’installation se fait en mode Bureau, sans Terminal ni modification de
SteamOS.

## Télécharger et ouvrir l’application

1. Installez KuloNiku depuis Steam et lancez-le une première fois.
2. Passez en **mode Bureau** : **Steam > Marche/Arrêt > Passer en mode Bureau**.
3. [Téléchargez l’AppImage Steam Deck](https://github.com/Le-Moulin/KuloNiku-FR/releases/latest/download/KuloNiku-FR-Steam-Deck-x86_64.AppImage).
4. Dans **Dolphin > Téléchargements**, faites un clic droit sur le fichier.
5. Ouvrez **Propriétés > Permissions** et cochez **Est exécutable**.
6. Double-cliquez sur l’AppImage, puis choisissez **Lancer** si demandé.

## Installer le français

1. Attendez que l’application affiche **Prêt à installer le français**.
2. Cliquez sur **Installer le français** et confirmez.
3. Après l’installation, cliquez sur **Revérifier**. L’état doit indiquer
   **Installation propre et à jour**.

L’application effectue une simulation et crée une sauvegarde vérifiée avant de
modifier le jeu.

![KuloNiku FR installé et vérifié sur Steam Deck](assets/kuloniku-fr-steam-deck-tested.png)

Si le jeu n’est pas détecté, cliquez sur **Changer…** et sélectionnez son
dossier, celui qui contient `KuloNiku_Data`.

## Jouer en français

1. Fermez l’application et revenez en mode Jeu avec **Return to Gaming Mode**.
2. Lancez KuloNiku depuis Steam.
3. Dans les paramètres de langue, choisissez **Français**.

## Restaurer le jeu original

1. Quittez le jeu et repassez en mode Bureau.
2. Rouvrez l’AppImage.
3. Cliquez sur **Restaurer l’original** et confirmez.

Vous pourrez réinstaller le français plus tard avec la même AppImage.

## En cas de problème

- **L’AppImage ne s’ouvre pas :** vérifiez que **Est exécutable** est coché.
- **Le jeu n’est pas détecté :** utilisez **Changer…**.
- **Le jeu ne démarre plus :** rouvrez l’AppImage et choisissez
  **Restaurer l’original**.

[Questions fréquentes](FAQ.md)
· [Signaler un problème](https://github.com/Le-Moulin/KuloNiku-FR/issues/new?template=installation.yml)
