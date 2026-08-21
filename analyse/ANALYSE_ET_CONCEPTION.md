# معهد الأصلين — Analyse des données et conception du système

**Projet** : ERP scolaire — Next.js (front) + Django REST Framework (back)
**Sources analysées** : `Résultat Trimestre 1 - A2 - 2025-2026.xlsx` (5 feuilles) + 4 listes PDF officielles
**Date d'analyse** : 2026-08-20
**Statut** : conception validée — développement en cours

> **Décisions arrêtées par la direction (2026-08-20)**
> 1. **Interface entièrement en arabe**, RTL, sans bascule de langue.
> 2. **2 périodes par an**, nommées **فصل** (semestre) et non « trimestre ».
> 3. **Moyenne annuelle = moyenne arithmétique des 2 فصل** (poids égaux).
>
> Le vocabulaire du présent document a été aligné sur ces décisions ; le code utilise `Semester` côté modèle et فصل côté interface.

---

## 1. Ce que disent les données

### 1.1 Structure pédagogique réelle

L'institut est organisé en **5 sections** (أقسام), chacune avec son propre programme et ses propres coefficients (الضارب). Ce n'est **pas** un tronc commun : chaque section a un jeu de matières distinct.

| Section (قسم) | Effectif | Matières et coefficients | Σ coef |
|---|---|---|---|
| **المربيات** (Al‑Murabbiyāt) | 15 | النحو ×4 · اللغة ×2 · الفقه ×3 · القرآن الكريم ×5 | 14 |
| **الحفيدات** (Al‑Ḥafīdāt) | 23 (+1 doublon) | النحو ×4 · اللغة ×2 · الفقه ×3 · القرآن الكريم ×5 | 14 |
| **الحافظات** (Al‑Ḥāfiẓāt) | 15 | النحو ×4 · اللغة ×2 · الفقه ×3 · **السيرة النبوية ×3** · القرآن الكريم ×5 | 17 |
| **المتميزات** (Al‑Mutamayyizāt) | 21 (+1 doublon) | الفقه ×3 · القرآن الكريم ×5 | 8 |
| **عالمات المستقبل** (ʿĀlimāt al‑Mustaqbal) | 22 | محارم اللسان ×3 · الأخضري ×3 · العبقري ×3 · القرآن الكريم ×5 | 14 |

**Catalogue de matières consolidé (8)** : النحو, اللغة, الفقه, السيرة النبوية, القرآن الكريم, محارم اللسان, الأخضري, العبقري.

**Effectif total** : **96 étudiantes** (matricules 24001 → 24096), toutes présentes dans les listes PDF officielles.

> Conséquence de conception majeure : le couple *(matière, coefficient)* n'appartient ni à la matière ni à l'étudiante — il appartient au triplet **(section, فصل, matière)**. C'est exactement le point que vous demandiez (« lier les matières avec le فصل »), et c'est la table pivot centrale du modèle.

### 1.2 Moteur de calcul rétro-conçu — et **validé à 100 %**

J'ai extrait les formules Excel, reconstruit l'algorithme, puis **recalculé les 98 lignes** et comparé aux valeurs du fichier.

**Résultat de la validation : 98/98 moyennes identiques, 98/98 décisions identiques.** Les seuls écarts portent sur 4 rangs saisis à la main (voir §1.3).

Les règles sont donc les suivantes :

**a) Moyenne semestrielle pondérée (فصل)**
```
moyenne = Σ (note_matière × coefficient) / Σ (coefficients)
```
Formule Excel d'origine (المربيات) : `(J2*5 + H2*3 + F2*2 + D2*4) / 14`

**b) Décision par matière — قرار اللجنة**
```
مستوفي        si note ≥ 10
              OU (moyenne ≥ 10 ET note ≥ 7)     ← compensation
غير مستوفي    sinon
```
Point important : la décision d'une matière **dépend de la moyenne générale**. L'ordre de calcul est donc contraint : moyenne d'abord, décisions ensuite. C'est une règle de *compensation* — une note entre 7 et 10 est rattrapée par une moyenne générale suffisante.

**c) Décision globale**
```
ناجحة    si moyenne ≥ 10 ET toutes les notes ≥ 7
استدراك  sinon
```

**d) Rang**
Tri par moyenne décroissante, **ex æquo au même rang, puis incrémentation de 1** (*dense ranking* : 1, 2, 3, 3, 4, 5…). Cette convention est confirmée sur 2 sections différentes (الحفيدات rangs 3, 3, 4 ; المتميزات rangs 15, 15, 16).

**e) Note absente**
Une cellule vide est traitée comme **0** dans la moyenne, et déclenche `غير مستوفي` sur la matière.

**Constantes du règlement** : seuil de réussite = 10, plancher de compensation = 7, barème = /20.

### 1.3 Anomalies détectées dans le fichier source

Ces points sont à corriger — et le système proposé les rend structurellement impossibles.

| # | Anomalie | Détail | Gravité |
|---|---|---|---|
| 1 | **Matricule 24097 dupliqué** | Attribué à **deux étudiantes différentes** : `أمبيغية أمينو` (الحفيدات) et `تبراك اسليمان` (المتميزات). De plus, 24097 **n'existe dans aucune liste PDF officielle** (les listes s'arrêtent à 24096). | 🔴 Bloquante |
| 2 | **4 rangs faux** | الحفيدات lignes 22 à 25 (`زينب أحبلالة`, `تانة الشيخ ولد بكيا`, `اماه محمدالأمين أحمدو`, `النياه محمدفال`) portent le rang **18** au lieu de **19** (elles sont à égalité avec `النياه الحسين`, rang 19). | 🟠 Majeure |
| 3 | **Formules cassées (latentes)** | Feuille الحافظات : les décisions de اللغة et الفقه testent `J2` (note de السيرة) au lieu de `F2` et `H2`. Feuille الحفيدات : la cellule G16 référence la ligne **17**. Sans impact sur les valeurs actuelles par coïncidence, mais faux dès qu'une note change. | 🟠 Majeure |
| 4 | **Formules écrasées par des valeurs** | Seule la **ligne 2** de chaque feuille contient encore des formules ; toutes les autres lignes sont des valeurs statiques collées. Toute correction de note ne se propage plus. | 🔴 Bloquante |
| 5 | **Absence ≠ zéro** | Rien ne distingue « absente », « absente justifiée » et « a eu 0 ». 34 étudiantes ont une moyenne de 0 sur toutes matières — vraisemblablement des non-présentées, mais elles occupent des rangs et sont marquées `استدراك`. | 🟠 Majeure |
| 6 | **Aucune trace** | Pas d'auteur de saisie, pas d'horodatage, pas d'historique de modification des notes. | 🟠 Majeure |
| 7 | **Un seul فصل** | Le fichier ne couvre que le فصل 1. Aucun mécanisme de moyenne annuelle n'existe. | ℹ️ À construire |

---

## 2. Conception du système

### 2.1 Principes directeurs

1. **Le calcul n'est jamais saisi.** Moyennes, décisions et rangs sont des données *dérivées*, recalculées par un moteur unique et déterministe. Aucun utilisateur ne peut taper une moyenne ou un rang.
2. **Le règlement est une donnée, pas du code.** Seuils (10), plancher de compensation (7), mode de rang (dense), politique d'absence, pondération annuelle sont stockés en base et **versionnés**. Changer le règlement en 2027 ne demande aucun déploiement, et les bulletins de 2026 restent reproductibles à l'identique.
3. **Souveraineté du jury.** Le moteur *propose* une décision ; le conseil peut la **surcharger** avec une justification obligatoire et une trace nominative. La décision calculée reste visible à côté de la décision retenue.
4. **Cycle de vie du فصل.** Un فصل passe par `BROUILLON → SAISIE OUVERTE → CLÔTURÉ → PUBLIÉ`. Les enseignants n'écrivent qu'en *SAISIE OUVERTE*, les étudiantes ne lisent qu'en *PUBLIÉ*. C'est le mécanisme qui empêche une note de bouger après délibération.
5. **Tout est tracé.** Chaque note conserve son historique complet (ancienne valeur, nouvelle valeur, auteur, date, motif).

### 2.2 Modèle de données (Django)

```
AcademicYear                 année scolaire « 2025-2026 », active o/n
 └─ Semester (فصل)           n° 1..2, dates, état, poids annuel (1/1)
 └─ Enrollment               inscription : étudiante × section × année

Section                      المربيات, الحفيدات, الحافظات, المتميزات, عالمات المستقبل
Subject                      catalogue global des 8 matières (code + nom AR + nom FR)

Curriculum   ★ table pivot   (section, semester, subject) → coefficient, actif
                             unique(section, semester, subject)
                             ← c'est ici que « matière ↔ فصل » est liée

TeachingAssignment           (curriculum, teacher) — qui enseigne quoi, où, quand
Assessment      (option.)    (curriculum, type: devoir/composition, poids)

Grade                        (enrollment, curriculum[, assessment])
                             value 0..20 nullable · status: SAISIE|ABSENT|ABSENT_JUSTIFIÉ|DISPENSÉE
                             saisi_par, saisi_le, modifié_le
                             unique(enrollment, curriculum, assessment)
GradeHistory                 audit immuable de chaque écriture

GradingRule                  (année[, section]) : seuil_reussite=10,
                             plancher_compensation=7, mode_rang=DENSE,
                             absence=COMPTE_ZERO, arrondi, version

SemesterResult  calculé      (enrollment, semester) → moyenne, rang, décision_calculée,
                             décision_retenue, motif_surcharge, décidé_par,
                             règle_version, calculé_le
SubjectResult   calculé      (semester_result, curriculum) → note_retenue, décision
AnnualResult    calculé      (enrollment, year) → moyenne_annuelle, rang_annuel, décision

User                         rôle: ADMIN | ENSEIGNANT | ÉTUDIANTE
                             (OneToOne vers Teacher ou Student)
Student                      matricule UNIQUE, nom AR, nom FR, date naissance, tuteur
Teacher                      identité, matières habilitées
```

**Points de conception à noter :**

- `Curriculum` porte le coefficient **par فصل** : le coefficient de القرآن peut légitimement passer de 5 (فصل 1) à 6 (فصل 2) sans réécrire l'historique.
- `matricule` est `unique=True` au niveau base — l'anomalie n°1 devient impossible.
- `Grade.value` est `nullable` **avec** un `status` explicite : la distinction absence/zéro (anomalie n°5) est enfin représentable.
- `SemesterResult` est **matérialisé** (stocké, pas calculé à la volée) pour garantir qu'un bulletin PDF émis reste identique s'il est réimprimé, et pour que le classement soit interrogeable en SQL.

### 2.3 Moteur de calcul

Un module Python **pur** (`results/engine.py`) : aucune dépendance à Django, aucun I/O, entrées et sorties sous forme de dataclasses. Cela le rend testable exhaustivement et réutilisable (recalcul batch, simulation, export).

```python
def compute_semester(students_grades, curriculum, rule) -> list[SemesterResultDTO]
    # 1. moyenne pondérée par étudiante  (absences selon rule.absence_policy)
    # 2. décision par matière            (avec compensation, dépend de la moyenne)
    # 3. décision globale
    # 4. classement                      (rule.ranking_mode)
```

**Moyenne annuelle** (à construire, absente du fichier source) :
```
moyenne_annuelle = Σ (moyenne_fasl_i × poids_i) / Σ (poids_i)    avec poids = 1 / 1
                 = (moyenne_fasl_1 + moyenne_fasl_2) / 2
```
Soit la **moyenne arithmétique des 2 فصل**, conformément à la décision de la direction. Les poids restent stockés en base : passer un jour à une pondération inégale ne demandera aucun développement. Le rang annuel suit la même règle *dense*. La décision annuelle réutilise les mêmes seuils, appliqués aux moyennes annuelles par matière.

**Test de non-régression fondateur** : les 96 étudiantes réelles du T1 2025‑2026 sont intégrées comme *golden fixture*. Le moteur doit reproduire **exactement** les 98 moyennes et 98 décisions du fichier Excel (déjà vérifié analytiquement), et corriger les 4 rangs erronés. Les données normalisées sont déjà prêtes dans `analyse/seed/`.

### 2.4 Rôles et permissions

| Capacité | Admin | Enseignant | Étudiante |
|---|:--:|:--:|:--:|
| Gérer années, فصول, sections, matières, coefficients | ✅ | — | — |
| Ouvrir / clôturer / publier un فصل | ✅ | — | — |
| Créer comptes et affectations | ✅ | — | — |
| Saisir / modifier des notes | ✅ | ✅ *ses affectations, فصل ouvert uniquement* | — |
| Voir les notes d'une section | ✅ | ✅ *ses matières* | — |
| Voir moyennes, rang, décisions de la section | ✅ | 🔸 *lecture seule* | — |
| Surcharger une décision de jury | ✅ *avec motif* | — | — |
| Consulter **son** relevé et **son** rang | ✅ | — | ✅ *si فصل publié* |
| Télécharger son bulletin PDF | ✅ | — | ✅ *si publié* |
| Consulter l'audit des notes | ✅ | 🔸 *ses matières* | — |

Le filtrage est appliqué **au niveau du queryset** (`get_queryset` restreint par rôle), pas seulement à l'affichage : une étudiante ne peut pas atteindre les données d'une autre même en forgeant l'URL.

### 2.5 Architecture technique

```
Navigateur
    │  HTTPS, cookie de session httpOnly + SameSite=Strict
    ▼
Next.js 15 (App Router, TypeScript)   ← BFF : le navigateur ne voit jamais de jeton
    │  Server Components + Route Handlers
    │  Interface 100 % arabe, dir="rtl" (next-intl, locale ar)
    │  Tailwind + shadcn/ui · TanStack Query · Zod
    ▼
Django 5 + Django REST Framework      ← API + logique métier + moteur de calcul
    │  drf-spectacular (OpenAPI → types TS générés)
    │  Celery + Redis (recalculs, génération PDF, envois)
    ▼
PostgreSQL 16                          ← contraintes d'intégrité en base
```

**Choix expliqués :**

- **Pattern BFF** (Backend For Frontend) : le front Next.js parle à Django *côté serveur*. Le jeton d'accès n'atteint jamais le JavaScript du navigateur — élimine par construction toute une classe de vols de jeton par XSS. C'est nettement plus sûr que de stocker un JWT dans `localStorage`.
- **Types générés** : le schéma OpenAPI de DRF génère les types TypeScript du front. Impossible d'avoir un front désynchronisé du back après un changement de modèle.
- **PostgreSQL** : les contraintes critiques (matricule unique, une seule note par étudiante×matière×فصل) sont posées **en base**, pas seulement dans le code applicatif.
- **RTL natif** : l'interface est **entièrement en arabe**, conçue RTL de bout en bout (propriétés logiques CSS : `margin-inline-start`, jamais `margin-left`), polices arabes embarquées. Aucune bascule de langue n'est prévue ; l'infrastructure i18n reste néanmoins en place pour un ajout ultérieur sans refonte.

### 2.6 Sécurité

**Authentification**
- Argon2id pour le hachage des mots de passe (pas le PBKDF2 par défaut de Django).
- Sessions en cookie `httpOnly` + `Secure` + `SameSite=Strict`, gérées par le BFF Next.js.
- **2FA obligatoire pour les comptes administrateurs** (`django-otp`, TOTP).
- Verrouillage progressif après échecs répétés (`django-axes`), avec journalisation IP.
- Première connexion étudiante : mot de passe temporaire + changement forcé.

**Autorisation**
- Permissions DRF par objet, filtrage systématique au niveau queryset.
- Le rôle est porté par le serveur, jamais déduit d'une donnée envoyée par le client.

**Durcissement**
- `SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `X_FRAME_OPTIONS=DENY`.
- Content-Security-Policy stricte, sans `unsafe-inline`.
- Throttling DRF (anonyme et authentifié), en particulier sur l'endpoint de connexion.
- CORS restreint à l'origine du front ; secrets en variables d'environnement, jamais en dépôt.
- Sauvegardes PostgreSQL chiffrées, quotidiennes, avec restauration testée.

**Protection des données**
- Les étudiantes sont majoritairement mineures : donnée minimale, pas d'export en clair, journal des accès aux dossiers.
- Le rang d'une étudiante lui est visible, mais **le classement nominatif complet n'est pas exposé aux étudiantes** (à confirmer avec la direction — c'est un choix de politique, pas technique).

### 2.7 Automatismes ERP

1. **Recalcul automatique** : toute écriture de note déclenche un recalcul asynchrone de la section concernée (moyennes → décisions → rangs). Aucune action manuelle, aucune formule à recopier.
2. **Bulletins PDF** générés en lot à la publication du فصل — mise en page RTL arabe (WeasyPrint + police Amiri/Cairo), reproduisant la présentation actuelle : matières, coefficients, notes, décision par matière, moyenne, rang, décision du jury.
3. **Tableau de bord direction** : taux de réussite par section et par matière, moyenne de section, effectifs à l'استدراك, matières les plus en difficulté, évolution فصل 1 → فصل 2.
4. **Alertes** : notes manquantes à J‑3 de la clôture, étudiante en risque d'استدراك, enseignant n'ayant pas terminé sa saisie.
5. **Import initial** : commande d'import des listes officielles et des résultats T1 depuis les fichiers actuels — les données normalisées sont déjà produites (`analyse/seed/`).
6. **Reconduction d'année** : duplication de la structure (sections, matières, coefficients) d'une année sur la suivante en une action.

### 2.8 Écrans principaux

- **Enseignant — grille de saisie** : tableau de type tableur (une ligne par étudiante, navigation clavier, saisie au fil de l'eau, enregistrement automatique, indicateur de complétude). C'est l'écran critique : les enseignants viennent d'Excel, l'ergonomie doit être au moins aussi rapide.
- **Admin — structure** : années, فصول, sections, matières, **affectation des coefficients par فصل**, ouverture/clôture.
- **Admin — délibération** : classement de section, décisions calculées, surcharge avec motif, publication.
- **Étudiante — mon relevé** : notes par matière avec coefficient, moyenne, rang, décision, les deux فصل, moyenne annuelle, bulletin PDF.

---

## 3. Plan de livraison proposé

| Étape | Contenu | Résultat vérifiable |
|---|---|---|
| **1. Socle** | Projet Django + Next.js, PostgreSQL, authentification, rôles, durcissement sécurité | Connexion fonctionnelle dans les 3 rôles |
| **2. Structure** | Années, فصول, sections, matières, `Curriculum` (matière×فصل×coefficient), import des 96 étudiantes | Structure 2025‑2026 réelle en base |
| **3. Moteur** | Module de calcul + règlement versionné + **test golden sur les 98 lignes réelles** | Le système reproduit exactement le T1 existant |
| **4. Saisie** | Grille enseignant, cycle de vie du فصل, audit des notes | Un enseignant saisit un فصل complet |
| **5. Résultats** | Délibération, surcharge jury, publication, espace étudiante, bulletins PDF RTL | Bulletins فصل 1 générés et publiés |
| **6. Annuel & pilotage** | Moyenne et rang annuels, tableaux de bord, alertes, exports | Année complète clôturée |

---

## 4. Points à trancher avant le développement

Ces décisions changent le modèle ou le règlement — j'ai retenu une hypothèse par défaut pour chacune, à confirmer ou corriger.

| # | Question | Hypothèse retenue par défaut |
|---|---|---|
| 1 | ~~**Langue de l'interface**~~ | ✅ **Tranché** : arabe uniquement, RTL, sans bascule |
| 2 | **Matricule 24097** | Deux étudiantes distinctes ont ce numéro et il est hors listes officielles → deux matricules valides à attribuer par la direction |
| 3 | ~~**Moyenne annuelle**~~ | ✅ **Tranché** : 2 فصل par an, moyenne arithmétique des deux |
| 4 | **Coefficients par فصل** | Identiques aux 2 فصل au départ, mais modifiables فصل par فصل |
| 5 | **Absence** | Compte pour 0 (conforme au fichier actuel), mais tracée comme absence — politique modifiable dans le règlement |
| 6 | **Note par matière** | Une note unique par matière et par فصل (comme aujourd'hui) ; le sous-modèle « devoir + composition » est prévu mais désactivé |
| 7 | **Visibilité du classement** | L'étudiante voit son propre rang et l'effectif, pas le classement nominatif complet |
| 8 | **Enseignants** | Non renseignés dans les sources fournies — à collecter, avec l'affectation matière × section |

---

## 5. Fichiers produits par cette analyse

```
analyse/
├── ANALYSE_ET_CONCEPTION.md            ce document
└── seed/
    ├── sections.json                   5 sections + matières + coefficients
    ├── subjects.json                   catalogue des 8 matières
    ├── students.json                   98 lignes (96 étudiantes + doublon 24097)
    └── grades_t1_2025_2026.json        363 notes du فصل 1, absences distinguées (value: null)
```

Ces fichiers sont directement exploitables comme données d'amorçage (étape 2 du plan) et comme jeu de test du moteur de calcul (étape 3).

*Aucun fichier source n'a été modifié.*
