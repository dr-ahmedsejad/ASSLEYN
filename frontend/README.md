# معهد الأصلين — Frontend (Next.js)

Interface **entièrement en arabe**, en lecture de droite à gauche, reprenant
l'identité visuelle de SIGA.

## Démarrage

Le backend doit tourner d'abord (voir `../backend/README.md`).

```bash
npm install
cp .env.example .env.local     # API_BASE_URL
npm run dev
```

> Le port **8000 est occupé par le projet SIGA** sur ce poste. Le backend
> ASSLEYN écoute sur **8010**, le front sur **3000**.

## Le pattern BFF

Le navigateur ne parle **jamais** directement à Django.

```
navigateur ──cookie httpOnly──▶ Next.js (serveur) ──session──▶ Django
```

- `src/lib/api.ts` — client serveur : relit le cookie de session et le rejoue
  vers l'API, avec le jeton CSRF sur les écritures.
- `src/lib/auth.ts` — seul endroit où les cookies de session sont posés ou
  effacés (Server Actions).
- `src/app/api/bff/[...path]/route.ts` — relais pour les composants client,
  restreint par **liste blanche** de chemins. Une route ajoutée côté Django
  n'est pas exposée tant qu'elle n'est pas déclarée ici.

Conséquence : aucun jeton n'atteint le JavaScript du navigateur. Un script
injecté ne peut pas voler la session.

## Routes

| Chemin | Écran | Permission |
|---|---|---|
| `/connexion` | Connexion | tous |
| `/mot-de-passe` | Changement de mot de passe | tous |
| `/` | Accueil — relevé personnel, mes matières, ou tableau de bord | selon le rôle |
| `/saisie-notes` | Grille de saisie des notes | `notes.saisir` |
| `/resultats` | Classement d'une section | `notes.consulter` |
| `/deliberation` | Délibération, décisions, publication | `deliberation.gerer` |
| `/structure` | Matières, coefficients, catalogue — **éditable** | `structure.gerer` |
| `/annees` | Années, ouverture de N+1, réinscription en lot | `annees.gerer` |
| `/etudiantes` | Liste des étudiantes, recherche et filtre | `etudiantes.gerer` |
| `/droits` | Rôles, permissions, droits individuels | `comptes.gerer` |
| `/journal` | Journal d'audit des notes | `journal.consulter` |

Les deux redirections défensives (`src/app/(app)/layout.tsx`) sont décidées
côté serveur : pas de session → `/connexion` ; mot de passe temporaire non
changé → `/mot-de-passe`.

## Identité visuelle

Reprise de SIGA (`C:\SIR\ISS_SIGA\frontend_iss`) : même palette, mêmes ombres,
même grammaire de composants — sidebar blanche repliable, topbar collante,
cartes blanches sur fond gris clair, pastilles de statut bordées.

| Rôle | Couleur |
|---|---|
| primaire | `#006633` · dégradé `#004d24 → #008844` |
| accent | `#E5C018` |
| secondaire | `#C82020` |
| fond | `#f8fafc` · texte `#0a0f1a` · gris `#64748b` |

Comme SIGA, le thème est **clair uniquement**. Le logo (`public/logo-institut.png`)
a été extrait des listes PDF officielles de l'institut, masque de transparence
compris.

### Différences imposées par le RTL

- La sidebar est au bord **droit** ; `border-e` (inline-end) pose la
  séparation du bon côté sans condition.
- Le chevron des groupes pointe vers la **gauche** au repos.
- Le CSS n'utilise que des propriétés logiques — `margin-inline-start`,
  `text-start`, `inset-inline-start` — jamais `margin-left` ni
  `text-align: right`.
- Les notes et matricules restent en chiffres occidentaux, isolés du sens du
  texte par la classe `.chiffres` : une note se recopie, l'ambiguïté de
  lecture n'est pas acceptable.

## Composants

```
components/layout/   Shell · Sidebar · NavTree · Topbar · UserMenu
components/ui.tsx    Carte · Alerte · Pastille · BadgeDecision · BadgeEtat
                     Indicateur · BarreProgression · OngletLien
components/          Pagination · GrilleNotes · GestionProgramme
                     TableauClassement · ReleveEtudiante · ActionsDeliberation
lib/nav-config.ts    Arborescence de navigation et filtrage par rôle
```

## Pagination

`components/Pagination.tsx` est rendue en **liens**, pas en boutons : les
listes sont produites par des composants serveur, donc changer de page est une
navigation. L'URL reste partageable, le bouton « précédent » du navigateur
fonctionne, et la pagination marche sans JavaScript. En RTL le chevron « page
précédente » pointe vers la droite.

Utilisée sur `/resultats`, `/deliberation`, `/etudiantes` et `/journal`
(25 lignes par page). **Pas** sur la grille de saisie : une colonne de notes se
saisit d'un bloc, et paginer ferait perdre les lignes modifiées non encore
enregistrées.

## Le poste de saisie

`/saisie-notes` est conçu pour quelqu'un qui saisit un فصل entier — un
assistant de direction — autant que pour un enseignant qui n'a qu'une
matière.

**Deux listes déroulantes liées** (`components/SelecteurMatiere.tsx`) : la
classe, puis ses matières — comme dans SIGA. Chaque option porte son
avancement (`12/24`), donc on voit ce qu'il reste à faire sans ouvrir la
matière. Changer de classe remet le choix de matière à zéro.

`components/PosteDeSaisie.tsx` ajoute au-dessus de la grille :

- une **jauge globale** du فصل (notes saisies / attendues, en %) ;
- le **détail de la classe choisie** — et d'elle seule — chaque matière avec
  sa barre de progression et sa pastille : مكتملة · جارية · لم تبدأ ;
- un bouton **« أول مادة ناقصة »** qui mène droit à la première matière
  incomplète de la classe ;
- une **navigation matière précédente / suivante** sous la grille, pour
  enchaîner sans repasser par le sommaire, plus un saut direct vers la
  prochaine matière incomplète.

En RTL, « suivante » est à gauche et « précédente à droite » : les chevrons
suivent le sens de lecture.

Une matière désignée par `?curriculum=` **commande le فصل affiché**, comme
partout ailleurs : un lien explicite prime sur le contexte. Symétriquement, le
sélecteur de la barre du haut retire `curriculum` de l'URL quand on change de
فصل — sans quoi l'ancien فصل reviendrait par la bande.

Tout vient d'un seul appel à `/grading/avancement/` : l'écran n'ouvre pas une
grille par matière pour savoir où il en est.

## La grille de saisie

`components/GrilleNotes.tsx` est l'écran critique : les enseignants viennent
d'Excel, la saisie doit être au moins aussi rapide.

- `Entrée` et `↓` passent à l'étudiante suivante, `↑` remonte.
- Validation locale pendant la frappe (bornes du barème), envoi **en un seul
  lot** — tout ou rien, comme côté serveur.
- Compteur de modifications non enregistrées et barre de complétude.
- **Une case laissée vide vaut zéro.** La colonne « الحالة » a été retirée à
  la demande de l'institut : la saisie se réduit à une note par ligne. Seules
  les lignes réellement touchées sont envoyées, donc une matière à peine
  ouverte ne se remplit pas de zéros toute seule.
- Le modèle conserve les statuts (غائبة, غياب مبرر, معفاة) : les absences
  importées du fichier d'origine restent distinguées, seule l'interface de
  saisie ne les propose plus.

## Navigation et droits

`lib/nav-config.ts` ne connaît pas les rôles : chaque groupe déclare la
**permission** qui l'ouvre. `/auth/me/` renvoie les permissions effectives de
l'utilisateur, et `resolveGroups()` filtre le sidebar avec.

Le même code garde l'entrée de menu et l'endpoint côté Django : masquer une
entrée sans fermer la route serait du décor. `/droits` porte deux tableaux —
la matrice par rôle, et les exceptions individuelles pour confier une capacité
à une personne en particulier.

### Pages refusées

Le sidebar masque ce qui n'est pas accessible, mais une URL se tape à la main.
Chaque page protégée commence donc par une garde (`lib/acces.ts`) qui rend un
refus lisible (`components/Refus.tsx`) au lieu de casser sur le 403 de l'API.

La racine `/` n'a de sens que pour qui dispose de `tableau.consulter` ou d'un
relevé personnel ; les autres y sont redirigés vers leur écran de travail —
un assistant atterrit directement sur `/saisie-notes`.

## Le contexte de travail

La barre du haut porte un **sélecteur de فصل** : on choisit une fois, et
tous les écrans s'y tiennent — saisie des notes, résultats, délibération,
structure. C'est ce que fait `ContextSwitcher` dans SIGA.

- Le choix est mémorisé dans un cookie `httpOnly` posé par une Server Action
  (`lib/contexte-actions.ts`), puis relu à chaque rendu (`lib/contexte.ts`).
- **Un paramètre `?fasl=` dans l'URL reste prioritaire** : un lien partagé
  continue de pointer sur ce qu'il désigne, le contexte ne le détourne pas.
- Un cookie périmé (فصل supprimé, année archivée) est ignoré : la
  résolution retombe sur le فصل ouvert, puis sur le premier de la liste.
- Changer de contexte retire `fasl` et `page` de l'URL courante et conserve
  les autres filtres (قسم, دورة).

Les onglets de فصل qui existaient dans chaque page ont été retirés : deux
endroits pour choisir la même chose, c'était deux sources de vérité. Chaque
écran affiche désormais le فصل courant en titre, en lecture seule.

`/saisie-notes` en tire le plus grand parti : la liste des matières se limite
au فصل choisi, et une matière d'un autre فصل atteinte par un vieux lien
est signalée au lieu d'être affichée.

## Les deux sessions

Chaque écran de notes et de résultats porte un onglet **الدورة العادية /
الدورة الاستدراكية**. En rattrapage, la grille ne liste que les
étudiantes convoquées dans la matière et rappelle leur note de session
normale, celle que le rattrapage doit améliorer. La saisie n'est possible que
dans la session que le فصل a ouverte — l'autre reste consultable.

L'ouverture de la session de rattrapage se fait depuis `/deliberation`, après
publication de la session normale.

## Les seuils par قسم

`/deliberation` porte un tableau des seuils, une ligne par قسم : la
commission saisit **عتبة النجاح** et **حد التعويض**, un motif facultatif,
et la section est recalculée immédiatement.

Le plancher ne peut pas dépasser la barre : la contrainte est vérifiée côté
client pour éviter un aller-retour, et refusée par le serveur de toute façon.
L'écran indique si les seuils affichés sont propres au فصل ou hérités de
l'année.

## L'édition des coefficients

`components/GestionProgramme.tsx` — `/structure`. Ajouter une matière au
programme d'un فصل, changer son coefficient, la désactiver, la retirer, et
enrichir le catalogue global des matières.

Trois garde-fous, tenus par l'API et affichés ici :

- modifier un coefficient **recalcule toute la section** ;
- rien n'est modifiable une fois le فصل publié ;
- une matière qui porte déjà des notes ne se supprime pas — on la désactive.


## Mobile d'abord

L'interface est pensée pour un téléphone avant un écran large.

- Sidebar : tiroir plein écran en dessous de `lg`, colonne fixe repliable
  au-dessus.
- **La grille de saisie n'est pas un tableau** mais une liste en grille CSS :
  sur téléphone le nom et le matricule s'empilent à gauche du champ de note,
  et à partir de `sm` chaque donnée retrouve sa colonne. Aucun défilement
  latéral pour saisir — c'est l'écran où cela compte le plus.
- Champs de saisie à **16 px et 44 px de haut sur mobile** : en dessous de
  16 px, iOS zoome automatiquement à la mise au point.
- Les tableaux de consultation (classement, journal) défilent, eux, **dans
  leur carte** : la page ne défile jamais horizontalement.
- Filtres, actions et formulaires passent à la ligne (`flex-wrap`) ; les
  libellés de filtre prennent toute la largeur sur mobile.
- Padding des cartes : `p-4` sur mobile, `p-5` au-dessus de `sm`.
