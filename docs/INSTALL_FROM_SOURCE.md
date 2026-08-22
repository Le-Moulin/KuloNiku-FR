# Installation depuis les sources

Cette méthode s’adresse aux personnes qui souhaitent examiner, modifier ou
tester le code. Pour une installation normale, utilisez plutôt la
[dernière release](https://github.com/Le-Moulin/KuloNiku-FR/releases).

## Prérequis

- [Python](https://www.python.org/) ;
- [uv](https://docs.astral.sh/uv/) ;
- une installation légitime de la démo ou du jeu complet.

## Installer

Fermez le jeu, puis installez les dépendances :

```sh
uv sync
```

Lancez d’abord la simulation. Elle ne modifie aucun fichier.

Sous Windows :

```powershell
uv run kuloniku-fr install "C:\Program Files (x86)\Steam\steamapps\common\KuloNiku"
```

Sous macOS :

```sh
uv run kuloniku-fr install "/chemin/vers/KuloNiku.app"
```

Sous Linux ou Steam Deck :

```sh
uv run kuloniku-fr install "/chemin/vers/steamapps/common/KuloNiku"
```

Sous Windows et Linux, le chemin doit désigner le dossier contenant
`KuloNiku_Data`.

Si le diagnostic est correct, relancez la même commande avec `--apply` :

```sh
uv run kuloniku-fr install "/chemin/vers/KuloNiku.app" --apply
```

Relancez ensuite le jeu depuis Steam et choisissez **Français** dans les
paramètres.

## Restaurer le jeu

Commencez par une simulation de la restauration :

```sh
uv run kuloniku-fr restore "/chemin/vers/KuloNiku.app"
```

Si le diagnostic est correct, ajoutez `--apply` :

```sh
uv run kuloniku-fr restore "/chemin/vers/KuloNiku.app" --apply
```

L’outil utilise la sauvegarde vérifiée créée lors de l’installation.

## Détails techniques

- [Architecture et compatibilité](DISTRIBUTION.md)
- [Mises à jour](UPDATES.md)
- [Sécurité](../SECURITY.md)
