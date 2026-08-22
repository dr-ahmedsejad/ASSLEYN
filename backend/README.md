# معهد الأصلين — Backend (Django REST Framework)

API de gestion pédagogique de l'institut : structure annuelle, saisie des
notes, calcul des moyennes, rangs et décisions.

## Démarrage

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements/dev.txt
cp .env.example .env          # puis renseigner DJANGO_SECRET_KEY
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py seed_2025_2026
.venv/Scripts/python.exe manage.py runserver
```

Documentation interactive de l'API : <http://localhost:8000/api/docs/> (mode
développement uniquement). Schéma OpenAPI : `/api/schema/`.

## Organisation

```
config/settings/      base · dev · prod  (aucun secret dans le code)
apps/accounts/        User (3 rôles), Student, Teacher, authentification
apps/academics/       AcademicYear, Semester (فصل), Section, Subject,
                      Curriculum  ← matière × فصل × section → coefficient
apps/grading/         GradingRule (règlement versionné), Grade, GradeHistory
apps/results/         engine.py (moteur pur), services.py, résultats calculés
apps/common/          permissions transverses
```

## Le moteur de calcul

`apps/results/engine.py` est un module **pur** : aucun import Django, aucun
accès base. Il prend des données, il rend des données.

```
moyenne  = Σ (note × coefficient) / Σ (coefficients)

matière  = مستوفي     si note ≥ 10  ou  (moyenne ≥ 10 et note ≥ 7)
           غير مستوفي  sinon

globale  = ناجحة      si moyenne ≥ 10 et toutes les notes ≥ 7
           استدراك     sinon

rang     = classement dense (1, 2, 3, 3, 4)

annuelle = (moyenne فصل 1 + moyenne فصل 2) / 2

rattrapage : note retenue = max(session normale, session de rattrapage)
```

Les seuils, le mode de classement et la politique d'absence ne sont pas
écrits en dur : ils viennent de `GradingRule`, versionné par année et par
section. Chaque résultat calculé conserve la référence de la règle appliquée,
ce qui rend un bulletin reproductible des années plus tard.

**Toutes les comparaisons portent sur la moyenne non arrondie.** L'arrondi
n'intervient qu'à l'affichage — une moyenne de 9,998 s'affiche 10,00 mais
reste un استدراك.

## Tests

```bash
.venv/Scripts/python.exe -m pytest
```

227 tests. Deux d'entre eux méritent d'être connus :

- `test_engine_golden.py` — rejoue les **98 lignes réelles** du fichier
  « Résultat Trimestre 1 - A2 - 2025-2026.xlsx » et vérifie que le moteur
  reproduit **exactement** les 98 moyennes, les 98 décisions globales et
  toutes les décisions par matière produites par l'institut.
- `test_import_and_recompute.py` — même vérification, mais sur la chaîne
  complète : import, base de données, règlement stocké, matérialisation.

Quatre rangs du fichier source sont des erreurs de saisie manuelle avérées
(section الحفيدات, rang 18 au lieu de 19 pour quatre étudiantes à égalité) ;
le test vérifie que le moteur produit la valeur corrigée.

## Commandes

| Commande | Rôle |
|---|---|
| `seed_2025_2026` | Amorce l'année réelle : 5 sections, 8 matières, coefficients, 97 étudiantes, notes du فصل 1, puis calcule. Idempotente. |
| `create_student_accounts` | Crée les comptes manquants. Mot de passe initial : le matricule écrit deux fois. |
| `reset_student_passwords` | Remet les mots de passe à cette règle. Épargne par défaut celles qui ont déjà choisi le leur ; `--tout` passe outre. |
| `importer_programme` | Pose les matières et coefficients d'un فصل depuis un JSON. Idempotente, `--dry-run` disponible. |

Les programmes vivent dans `programmes/*.json` — un fichier par فصل :

```bash
.venv/Scripts/python.exe manage.py importer_programme     programmes/fasl2-2025-2026.json --dry-run
```

Une matière retirée du fichier est **désactivée**, jamais supprimée : elle
peut déjà porter des notes. L'import refuse d'écrire si le فصل est publié.

Le matricule 24097 est attribué à deux personnes dans le fichier source et
n'existe dans aucune liste officielle. La direction a tranché : il reste à
`أمبيغية أمينو` (الحفيدات), et `تبراك اسليمان` (المتميزات) reçoit le 24098.
La table `ARBITRAGES` de `seed_2025_2026` porte cette décision — un import
neuf la reproduit, sans intervention.

Un conflit qui n'y figure pas est refusé et signalé ; `--provisional-matricules`
l'importe alors avec un numéro provisoire de la plage 99xxx.

## Sécurité

- Argon2id pour les mots de passe.
- Session en cookie `httpOnly` + `Secure` + `SameSite=Strict`, posée par le
  BFF Next.js : aucun jeton n'est jamais exposé au JavaScript du navigateur.
- Message de connexion unique : ne révèle jamais si un compte existe.
- Throttling DRF, 30 tentatives de connexion par minute et par adresse.
- CSP stricte, HSTS, `X-Frame-Options: DENY` (voir `settings/prod.py`).
- **Filtrage au niveau du queryset** : une étudiante qui forge l'identifiant
  du résultat d'une camarade obtient un 404, pas la donnée.
- Journal `asleyn.audit` : connexions, changements de notes, modifications de
  coefficients, décisions de jury, publications.

### Mots de passe

Huit caractères au minimum, **numérique autorisé**. Le mot de passe de
première connexion d'une étudiante est son matricule écrit deux fois — 24060
ouvre avec `2406024060` — et son remplacement est imposé dès l'ouverture de
session. Aucune feuille de mots de passe à imprimer puis à détruire : chaque
étudiante connaît déjà son numéro.

Huit chiffres, c'est cent millions de combinaisons : dérisoire face à une
machine qui essaie hors ligne, hors d'atteinte en ligne où le verrouillage
n'accorde que cinq essais. C'est cette barrière-là qui tient, pas la longueur.

Deux validateurs de Django sont volontairement absents : `NumericPassword`
refuserait les mots de passe numériques, et `UserAttributeSimilarity`
refuserait un mot de passe dérivé du nom d'utilisateur — ce qui est exactement
la règle retenue. `CommonPassword` reste : il écarte `12345678`.

### Ouverture d'un compte

`POST /rbac/utilisateurs/`. Le **nom complet est saisi**, jamais déduit de
l'identifiant : `sejad` est une chaîne technique, et la translittérer en arabe
produit une orthographe que l'intéressé ne reconnaît pas comme la sienne.

Deux chemins, parce que ce sont deux gestes différents :

- **Personnel** — identifiant, nom complet, mot de passe, rôle. Les quatre sont
  obligatoires ; l'identifiant est comparé sans tenir compte de la casse.
- **Étudiante** — un matricule suffit. Le nom vient de son dossier et n'est pas
  retapé : deux orthographes pour une même personne, c'est une personne de
  trop. L'identifiant est le matricule, le mot de passe initial le matricule
  écrit deux fois. Un nom envoyé avec le matricule est ignoré.

Le mot de passe posé par l'administration est provisoire quelle que soit sa
qualité — il a transité par une autre personne — et son remplacement est imposé
à la première connexion.

`PATCH /rbac/utilisateurs/{id}/` corrige un nom après coup, nécessaire parce que
les premiers comptes ont été ouverts sans champ de nom. Pour une étudiante, la
correction suit jusqu'à son dossier : le compte et le dossier ne peuvent pas
porter deux noms différents.

### Verrouillage progressif

`apps/accounts/verrouillage.py`. Cinq échecs ferment le compte **5 minutes** ;
cinq de plus, **15** ; cinq encore, **30**. Les paliers montent tant que les
blocages se succèdent dans la journée, puis le compteur repart de zéro.

Le blocage porte sur le nom d'utilisateur, pas sur l'adresse : l'institut sort
par une seule connexion internet, bloquer l'IP fermerait la porte à toute une
classe. Le revers est connu — qui connaît un identifiant peut en bloquer
l'accès — d'où l'écran de déblocage, qui rouvre en un geste.

Pendant le blocage, **le bon mot de passe est refusé comme les autres** : une
réponse différente ferait du compte fermé un oracle.

`django-axes` a été retiré. Il verrouille bien, mais à durée fixe ; l'escalade,
le minuteur affiché, la liste des comptes fermés et leur réouverture se lisent
tous dans le journal des tentatives, qui devait de toute façon exister pour
tracer les adresses. Deux comptabilités du même phénomène auraient fini par se
contredire.

### Journal des connexions et fréquentation

`LoginAttempt` enregistre **chaque** tentative — réussie ou non — avec l'issue,
l'adresse IP et le navigateur. L'identifiant est conservé tel qu'il a été
saisi, même inconnu : c'est précisément ce qu'on veut lire après coup.

De ce même journal découlent les statistiques de fréquentation : nombre de
visites, visiteuses distinctes, échecs, et les **dix étudiantes les plus
assidues**. Une visite est une connexion réussie — le navigateur ne joignant
jamais Django directement, il n'y a pas de page vue côté API à compter.

| Route | Permission |
|---|---|
| `POST /rbac/utilisateurs/` | `comptes.gerer` |
| `PATCH /rbac/utilisateurs/{id}/` | `comptes.gerer` |
| `GET /securite/journal/` | `journal.consulter` |
| `GET /securite/statistiques/` | `journal.consulter` |
| `GET /securite/verrous/` | `comptes.gerer` |
| `POST /securite/verrous/{id}/deverrouiller/` | `comptes.gerer` |
| `POST /securite/utilisateurs/{id}/reinitialiser-mot-de-passe/` | `comptes.gerer` |

Un blocage débloqué est **clos, pas effacé** : effacer l'incident retirerait à
l'administration le seul indice d'une attaque en cours.

La réinitialisation ne demande pas l'ancien mot de passe — l'administration
intervient justement quand il est perdu. Le nouveau est renvoyé **une seule
fois**, n'est stocké nulle part en clair, doit être changé à la première
connexion, et lève au passage un éventuel blocage.

## Les deux sessions

Chaque فصل comporte une **session normale** (الدورة العادية) et une
**session de rattrapage** (الدورة الاستدراكية). Le فصل porte un
`current_session` : il repasse en saisie une seconde fois sans effacer la
premiere.

- Une étudiante n'est convoquée au rattrapage que dans les matières
  déclarées `غير مستوفي` à l'issue de la session normale, et seulement si
  sa décision retenue était `استدراك`. La grille de saisie ne montre
  qu'elles ; l'API refuse toute autre écriture.
- La note retenue est la **meilleure des deux** : on ne perd jamais de points
  en repassant. Les politiques `REPLACE` et `BEST_CAPPED` existent dans le
  moteur et se choisissent dans le règlement.
- Chaque session a son propre `SemesterResult` : celui de la session normale
  reste consultable, c'est lui qui a fondé la convocation. Le résultat annuel
  prend le rattrapage quand il existe, la session normale sinon.

## Les seuils par قسم

Ni la barre de réussite ni le plancher de compensation ne sont figés. En
délibération, la commission fixe les deux **par قسم et par فصل** :

```
POST /api/v1/semesters/{id}/seuil/   {section, pass_threshold,
                                      compensation_floor?, note}
GET  /api/v1/semesters/{id}/seuils/  seuils en vigueur
```

`compensation_floor` est facultatif : omis, le plancher garde sa valeur. Il
est refusé s'il dépasse la barre de réussite — une note éliminatoire ne peut
pas se situer au-dessus d'elle. Et si la barre descend sous le plancher, celui-ci
s'aligne dessus plutôt que de rendre le règlement incohérent.

Une nouvelle version de `GradingRule` est créée à chaque décision, avec son
auteur et son motif ; l'ancienne survit, donc un bulletin déjà émis reste
explicable. La résolution va du plus précis au plus général :
`(année, section, فصل)` → `(année, section)` → `(année)`.

## L'année suivante

```
POST /api/v1/years/{id}/dupliquer/       structure de l'année N vers N+1
POST /api/v1/enrollments/reinscrire/     réinscription en lot
```

La duplication recopie les فصول, les programmes, les coefficients et le
règlement. Elle ne recopie **ni les notes ni les inscriptions** : une nouvelle
année part d'une page blanche. La réinscription est un acte séparé, où
l'administration choisit la section de destination — aucun parcours
automatique n'est supposé entre les أقسام.

## Avancement de la saisie

```
GET /api/v1/grading/avancement/?semester=<id>&session=<NORMAL|RESIT>
```

Retourne, pour tout un فصل, l'état de chaque matière : effectif attendu,
notes renseignées, statut (`COMPLETE` / `PARTIELLE` / `NON_COMMENCEE`),
groupé par قسم. En **trois requêtes**, quel que soit le nombre de matières —
sans quoi l'écran de saisie ouvrirait une grille par matière pour connaître
son avancement.

Une note « renseignée » est une note dont le statut a été arrêté, **absence
comprise** : décider qu'une étudiante était absente, c'est avoir traité son
cas. En session de rattrapage, l'effectif attendu n'est pas la classe entière
mais les seules convoquées de la matière.

Un enseignant n'y voit que ses matières affectées ; le personnel de l'institut,
tout le فصل.

## Contrôle d'accès

Quatre rôles : **مدير** (administration), **مساعد الإدارة**, **أستاذ**,
**طالبة**.

L'autorisation ne repose pas sur le nom du rôle mais sur des **codes de
permission** (`apps/accounts/rbac.py`). Le catalogue est en code : chaque code
garde un endpoint réel et une entrée de menu. Ce qui se configure en base,
c'est **qui en dispose**.

| Code | Ouvre |
|---|---|
| `notes.saisir` | grille de saisie en écriture |
| `notes.consulter` | grilles en lecture, classements |
| `deliberation.gerer` | seuils, décisions, transitions, publication |
| `structure.gerer` | sections, matières, coefficients, règlement |
| `etudiantes.gerer` | dossiers, inscriptions, réinscription |
| `annees.gerer` | années et duplication |
| `journal.consulter` | audit des notes |
| `comptes.gerer` | comptes et attribution des droits |
| `resultats.personnels` | son propre relevé |
| `tableau.consulter` | la page d'accueil |

Attributions par défaut :

| Rôle | Droits |
|---|---|
| **مدير** | tout, non révocable |
| **مساعد الإدارة** | `notes.saisir` seulement — son écran est le poste de saisie |
| **أستاذ** | `tableau.consulter`, `notes.saisir`, `notes.consulter` |
| **طالبة** | `resultats.personnels` |

`notes.saisir` **implique de lire sa grille** : la feuille de saisie et
l'avancement acceptent `notes.saisir` **ou** `notes.consulter`. Sans quoi
quelqu'un chargé de saisir ne pourrait pas ouvrir son propre tableau. Les
classements de section, eux, restent derrière `notes.consulter`.

Deux niveaux d'attribution :

- **Par rôle** (`RolePermission`) — la matrice éditable dans `/droits`.
- **Par personne** (`UserPermission`) — une exception qui accorde une
  capacité que le rôle ne donne pas, ou qui la retire alors qu'il la donne.
  C'est ce qui permet de confier la saisie des notes à quelqu'un en
  particulier sans créer un rôle de plus.

```
effectives = permissions du rôle
           + exceptions accordées
           - exceptions retirées
```

**L'administration peut tout, et ne peut pas s'en priver.** `permissions()`
court-circuite le calcul pour un `مدير` ou un superutilisateur, la matrice
affiche ses cases verrouillées, et l'API refuse de lui retirer un droit ou de
lui poser une exception. Sans quoi une fausse manipulation laisserait le
système sans personne pour le réparer.

**Le menu et l'API partagent la même source.** `/auth/me/` renvoie les
permissions effectives ; le front construit sa navigation avec, et chaque
endpoint exige le même code. Masquer une entrée sans fermer la route serait
du décor — `apps/accounts/tests/test_rbac.py` vérifie les deux ensemble.

Le périmètre reste gouverné par les données : accorder `notes.saisir` à un
enseignant ne lui ouvre **que** ses matières affectées. Pour saisir partout,
il faut un rôle d'administration ou d'assistance.

```
POST /api/v1/rbac/matrice/            matrice par rôle
PUT  /api/v1/rbac/utilisateurs/{id}/  exceptions individuelles
```

## Cycle de vie d'un فصل

```
مسودة  →  مفتوح للإدخال  →  مغلق  →  منشور
DRAFT       OPEN            CLOSED    PUBLISHED
```

- Les enseignants n'écrivent **qu'en** `OPEN`.
- La clôture déclenche un recalcul complet avant délibération.
- Les étudiantes ne lisent **qu'en** `PUBLISHED`.
- Les coefficients ne sont plus modifiables une fois le فصل publié.

## Souveraineté du jury

Le moteur *propose* une décision (`decision_computed`). Le conseil peut la
surcharger (`decision_final`) avec un motif obligatoire et une trace
nominative. Un recalcul ultérieur met à jour le calcul **sans effacer** la
décision retenue.

## Base de données

SQLite en développement, PostgreSQL en production (`DATABASE_URL`). Les
contraintes critiques sont posées **en base**, pas seulement dans le code :

- matricule unique — le conflit du fichier source devient impossible ;
- une seule note par (étudiante, matière, فصل, session) ;
- une note chiffrée existe si et seulement si le statut est « مسجلة » ;
- une seule section par étudiante et par année ;
- une seule année active à la fois.
