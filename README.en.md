# KuloNiku FR

**Community French translation mod for _KuloNiku: Bowl Up!_**

[View KuloNiku: Bowl Up! on Steam](https://store.steampowered.com/app/3357960/KuloNiku_Bowl_Up/)
· [Version française](README.md)

![Tests](https://github.com/Le-Moulin/KuloNiku-FR/actions/workflows/ci.yml/badge.svg)
![macOS tested](https://img.shields.io/badge/macOS-tested-2ea44f)
![Windows tested](https://img.shields.io/badge/Windows-tested-2ea44f)
![Steam Deck tested](https://img.shields.io/badge/Steam%20Deck-tested-2ea44f)

![KuloNiku: Bowl Up! home screen translated into French](docs/assets/kuloniku-fr-home.jpg)

KuloNiku FR brings French to both the demo and the full game. It is free,
unofficial, and does not contain any complete game file.

## Install the patch

Download the installer for your device — Windows, macOS, or Steam Deck — from
the [KuloNiku FR releases
page](https://github.com/Le-Moulin/KuloNiku-FR/releases), then follow the
installation instructions.

![macOS installer ready to install the French translation](docs/assets/kuloniku-fr-installer-macos.png)

After installation, launch the game from Steam and select **Français** in the
settings.

Want to inspect or modify the code? See the
[source installation guide](docs/INSTALL_FROM_SOURCE.en.md).

## Easy to undo

Before modifying the game, the application runs a simulation and creates a
verified backup. The **Restore** action returns the original file.

The patch is rebuilt from your own installation: no complete game file is
downloaded or distributed.

---

## An adaptation, not a word-for-word translation

Each line is compared with the languages shipped with the game, then adapted to
its context and the available screen space. Particular care is given to
Indonesian dishes and character voices. All translations have been reviewed;
some length overages still need visual in-game checks.

<p>
  <img src="docs/assets/kuloniku-fr-settings.jpg" width="49%" alt="French selected in the language settings">
  <img src="docs/assets/kuloniku-fr-gameplay.jpg" width="49%" alt="A recipe and tutorial translated into French">
</p>

## Contribute

You do not need to know how to code. The local **review workspace** compares all
available game languages, nearby keys, and the current French text. It also detects
missing translations automatically after a game update.

In the Windows or macOS app, select the game, open **Options avancées**, then choose
**Réviser et corriger les traductions**. The workspace opens in your browser
without modifying the game or sending its text online. Exported suggestions can
then be installed temporarily with **Importer mon fichier de correction** for
an in-game check.

[Discover the review workspace and follow the French tutorial](docs/REVIEW_WORKSPACE.md)

<a href="docs/REVIEW_WORKSPACE.md">
  <img src="docs/assets/kuloniku-fr-review-workspace.png" alt="KuloNiku FR review workspace with filters, language comparison, and contribution tools">
</a>

You can also:

- [submit a prepared review](https://github.com/Le-Moulin/KuloNiku-FR/issues/new?template=review.yml);
- [suggest a French correction](https://github.com/Le-Moulin/KuloNiku-FR/issues/new?template=translation.yml);
- [report an installation issue](https://github.com/Le-Moulin/KuloNiku-FR/issues/new?template=installation.yml);
- attach a screenshot to show the context or an overflowing string.

Never attach a game file or a complete extraction. To contribute with Git,
Codex, Claude, or another agent, see the [contribution guide](CONTRIBUTING.md).

## Why this project?

I wanted to discover KuloNiku, but the number of English ingredients, recipes,
and culinary terms was a real barrier to enjoying it. I first looked for a
careful way to translate the demo. The result convinced me to buy the full game
instead of giving up. It also shows how localization can help new players
discover and support a game.

I built this project with Codex around one simple rule: every change should be
understandable, verifiable, and reversible. The patch is not a raw machine
translation. Each line was reviewed against the languages shipped with the game,
its available screen space, and, whenever possible, its scene context.

Indonesian was especially valuable for respecting the studio’s roots, its food,
and the intent of certain dialogues. The French wording aims to feel natural and
fit the interface.

## Documentation

The [project documentation](docs/README.md) brings together the FAQ,
compatibility notes, translation quality, and technical information.

---

## Unofficial project

_KuloNiku: Bowl Up!_, its text, artwork, and trademarks belong to their rights
holders, including Gambir Studio and Raw Fury. This project is neither affiliated
with nor endorsed by them. It will be removed or archived upon request or if an
official French localization is released.

## Other community translations

Other communities provide their own KuloNiku translations:

- [unofficial Korean patch](https://github.com/killterm/Localization-KuloNikuBowlUp);
- [Japanese translation tool](https://steamcommunity.com/app/3357960/discussions/0/807974496347632869/);
- [AI-assisted Russian translation](https://boosty.to/ketsuneko/posts/5acd1b69-3ade-4a08-9319-95373059a4a6), available under its author’s terms.

KuloNiku FR was created independently and did not use any file or translation
from these projects. These links are provided to help players find the community
for their language.
