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
| `create_student_accounts` | Crée les comptes manquants avec mot de passe temporaire, export CSV optionnel. |
| `importer_programme` | Pose les matières et coefficients d'un فصل depuis un JSON. Idempotente, `--dry-run` disponible. |

Les programmes vivent dans `programmes/*.json` — un fichier par فصل :

```bash
.venv/Scripts/python.exe manage.py importer_programme     programmes/fasl2-2025-2026.json --dry-run
```

Une matière retirée du fichier est **désactivée**, jamais supprimée : elle
peut déjà porter des notes. L'import refuse d'écrire si le فصل est publié.

`seed_2025_2026` refuse par défaut la seconde étudiante portant le matricule
24097 — ce numéro est attribué à deux personnes dans le fichier source et
n'existe dans aucune liste officielle. `--provisional-matricules` l'importe
avec un numéro provisoire de la plage 99xxx.

## Sécurité

- Argon2id pour les mots de passe, 12 caractères minimum.
- Session en cookie `httpOnly` + `Secure` + `SameSite=Strict`, posée par le
  BFF Next.js : aucun jeton n'est jamais exposé au JavaScript du navigateur.
- `django-axes` : verrouillage après 5 échecs sur (utilisateur, IP).
- Message de connexion unique : ne révèle jamais si un compte existe.
- Throttling DRF, 10 tentatives de connexion par heure.
- CSP stricte, HSTS, `X-Frame-Options: DENY` (voir `settings/prod.py`).
- **Filtrage au niveau du queryset** : une étudiante qui forge l'identifiant
  du résultat d'une camarade obtient un 404, pas la donnée.
- Journal `asleyn.audit` : connexions, changements de notes, modifications de
  coefficients, décisions de jury, publications.

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
