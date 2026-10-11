# Brief compact pour les agents de traduction

## Univers et ton

KuloNiku: Bowl Up! est un jeu chaleureux de cuisine et de gestion, avec humour,
caractères hauts en couleur et moments plus émouvants. Le joueur ou la joueuse
hérite de **Bakuso**, le restaurant de boulettes de viande autrefois célèbre de
sa grand-mère, dans la petite ville de **KuloNiku**. Il faut restaurer sa gloire,
servir les habitants, améliorer et décorer le restaurant, nouer des amitiés et
éclaircir les mystères du passé familial.

La rivale la plus visible est **Stella**, cheffe rock star de **Souper Starz**.
Les rivalités se règlent lors de **duels culinaires** (« Meatball Brawls » dans
la communication anglaise), jugés sur la technique, la stratégie et les demandes
du public. Les personnages peuvent être amis, rivaux, ou les deux.

Personnages et noms propres rencontrés : Stella, Mami, Ume, Rosso, Lado, Shuga,
Mr. Crois, Cassie, Noka, Dan, Mr. Chu, Elio, Runa, Nekora, Tyro, Chil et Sai.
Ne pas franciser les noms propres sans preuve explicite dans les autres langues.

## Voix récurrentes

- **Stella** : rivale théâtrale, sûre d'elle et mordante, avec énergie de rock
  star; garder ses sarcasmes et exclamations sans la rendre artificiellement
  vulgaire.
- **Mami** : franche, chaleureuse et encourageante; registre oral simple.
- **Ume** : timide, polie et hésitante; conserver bégaiements, reprises et
  points de suspension sans les amplifier.
- **Shuga** : décontracté, amical, vocabulaire de musique et de rythme; argot
  français léger et durable, sans anglicismes gratuits.
- **Lado** : professionnel, exigeant et très formel; vocabulaire de standards,
  méthode et qualité.
- **Dan** : grandiloquent, mystérieux, parle comme un agent secret et appelle
  parfois le protagoniste « Faucon »; assumer ce jeu de rôle.
- **Cassie** : amicale, pragmatique et citadine; cofondatrice de Bakuso.
- **Noka** : passionnée de plantes; préserver les images végétales et son
  enthousiasme.
- **Elio** : batteur libre et enjoué; ton énergique et spontané.
- **Runa** : calme, précise et imperturbable.
- **Nekora** : maid féline mignonne et imprévisible; adapter les jeux de mots de
  chat quand ils fonctionnent en français, sans traduire son nom.
- **Tyro** : enfant passionné de dinosaures; vocabulaire enfantin et rugissements.
- **Chil** : très détendu et serviable; registre familier naturel, jeux autour
  de « chill » seulement lorsqu'ils restent compréhensibles.
- **Sai** : savant fou enthousiaste; emphase scientifique et expériences
  dangereuses traitées avec humour.
- **Mr. Chu** : marchand ambulant habile et légèrement roublard.

Le genre du personnage joueur n'est pas garanti par une clé générique. Éviter
« chef/cheffe », « nouveau/nouvelle » ou tout autre accord genré lorsqu'une
formulation neutre reste naturelle; sinon marquer la ligne `provisional`.

## Niveau d’adaptation attendu

- Produire un français naturel de jeu vidéo, comme une localisation officielle,
  et non un calque mot à mot.
- Préserver la voix du personnage visible dans le lot : registre, énergie,
  hésitations, humour, arrogance, tendresse et jeux de mots.
- Comparer systématiquement toutes les langues du fichier source, y compris le japonais et le français natif lorsqu’ils existent. L’indonésien
  éclaire souvent les plats et la culture; l’espagnol, l’allemand et le portugais
  aident à lever les ambiguïtés; le chinois et le thaï peuvent confirmer le sens.
- En cas de divergence, utiliser l'anglais comme référence prioritaire pour les
  faits, nombres, règles et état narratif, car il peut contenir une révision plus
  récente. Utiliser l'indonésien comme référence prioritaire pour la culture, les
  plats, le vocabulaire et l'intention locale. Si anglais et indonésien divergent
  fortement, documenter la décision : le fichier comporte au moins un champ
  anglais accidentellement rédigé en indonésien.
- Pour les plats indonésiens ou noms traditionnels, conserver le nom consacré
  lorsqu’il n’existe pas d’équivalent français exact. Ajouter une courte
  description seulement si l’interface et les autres langues le font déjà.
- Rechercher l’usage culinaire français en cas de doute réel. Préférer les sources
  institutionnelles, restaurateurs/spécialistes ou dictionnaires culinaires.
- Respecter le genre et le nombre induits par le contexte. Si le contexte reste
  insuffisant, choisir une formulation neutre ou marquer `provisional`.

## Contraintes inviolables

- Ne modifier que le fichier de sortie attribué.
- Ne jamais modifier `key` ni l’ordre des lignes.
- Préserver exactement variables et balises : `[X]`, `[NAME]`, `{0}`, `<br>`,
  `[COLOR=…]`, commandes de dialogue, ponctuation technique et retours à la ligne.
- Viser une longueur française inférieure ou égale à `max_source_chars` quand
  cela reste naturel. Un dépassement justifié est préférable à un contresens;
  l’expliquer brièvement dans `notes`.
- `status=reviewed` si la traduction est sûre; `status=provisional` si une
  validation en jeu, narrative ou culinaire reste nécessaire.
- Le fichier produit contient exactement : `key,fr,status,notes`.

## Terminologie déjà fixée

- Bakuso, KuloNiku, Souper Starz : noms propres inchangés.
- Settings → Paramètres; Gameplay → Jouabilité; Accessibility → Accessibilité.
- Main Menu → Menu principal; Resume → Reprendre; Paused → En pause.
- Meatball → Boulette lorsqu’il s’agit de l’ingrédient générique.
- Brawl / Meatball Brawl → Duel culinaire dans les textes courants; conserver
  un éventuel titre stylisé seulement si la clé ou plusieurs langues l'imposent.
- Fish balls → Boulettes de poisson; rice vermicelli → Vermicelles de riz.
- Fish cake → Surimi Narutomaki.
- Broth/soup base selon le contexte : Bouillon ou Soupe, ne pas uniformiser sans
  regarder la clé et les autres langues.
- Cozy Mode → Mode détente.
- Tous les tutoriels tutoient le joueur.
- Écrire `oe` et non la ligature `œ`, absente de la police des bulles.
- Les noms natifs de touches (`Left Shift`, `Space`, etc.) restent inchangés :
  ils ne sont traduits dans aucune langue officielle.

Le fichier de lot est volontairement le seul contexte textuel détaillé fourni.
Il contient toutes les traductions officielles disponibles pour ses seules clés.

Synopsis de référence : description officielle de KuloNiku: Bowl Up! publiée par
Gambir Studio et Raw Fury sur Steam, complétée par les textes multilingues extraits
de la version installée.
