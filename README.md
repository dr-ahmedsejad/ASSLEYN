# معهد الأصلين — نظام إدارة النتائج

Système de gestion pédagogique de l'institut : sections, matières,
coefficients par فصل, saisie des notes, calcul des moyennes, rangs, décisions
et résultats annuels.

**Interface entièrement en arabe (RTL) · Next.js + Django REST Framework**

---

## Organisation du dépôt

```
analyse/          Analyse des données sources et conception du système
  ANALYSE_ET_CONCEPTION.md
  seed/           Données normalisées extraites des fichiers d'origine

backend/          API Django REST + moteur de calcul     → backend/README.md
frontend/         Interface Next.js en arabe RTL          → frontend/README.md

Résultat Trimestre 1 - A2 - 2025-2026.xlsx     ┐ fichiers sources,
لائحة قسم ....pdf  (4 listes officielles)       ┘ inchangés
```

---

## Démarrage

Deux terminaux.

```bash
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements/dev.txt
cp .env.example .env                      # renseigner DJANGO_SECRET_KEY
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py seed_2025_2026
.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8010
```

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Interface : <http://localhost:3000> · API : <http://127.0.0.1:8010>

> **Ports** — le projet SIGA occupe déjà 8000 et 3001 sur ce poste. ASSLEYN
> utilise **8010** (backend) et **3000** (frontend).

---

## Ce que le système fait

**Structure.** Une année, deux **فصول**, deux sessions par فصل. Chaque section a son propre
programme : la table `Curriculum` lie *(section × فصل × matière)* à un
coefficient. Un coefficient peut changer d'un فصل à l'autre sans réécrire
l'historique.

**Saisie.** L'enseignant ne voit que ses matières et n'écrit que pendant que
le فصل est ouvert. Chaque écriture est journalisée : ancienne valeur,
nouvelle valeur, auteur, date, motif.

**Calcul.** Automatique à chaque enregistrement. Aucune moyenne, aucun rang
ne se saisit à la main.

```
moyenne  = Σ (note × coefficient) / Σ (coefficients)
matière  = مستوفي si note ≥ 10, ou (moyenne ≥ 10 et note ≥ 7)
globale  = ناجحة si moyenne ≥ 10 et toutes les notes ≥ 7
rang     = classement dense (1, 2, 3, 3, 4)
annuelle = (moyenne فصل 1 + moyenne فصل 2) / 2
rattrapage = max(session normale, session de rattrapage)
```

Ces seuils ne sont pas écrits en dur : ils viennent de `GradingRule`,
versionné par année et par section. Chaque résultat conserve la référence de
la règle appliquée.

**Rattrapage.** Chaque فصل a une session normale et une session de
rattrapage. Une étudiante n'y repasse que les matières déclarées
`غير مستوفي`, et on retient la meilleure des deux notes : repasser ne peut
jamais faire perdre de points. Le résultat de la session normale reste
consultable — c'est lui qui a fondé la convocation.

**Seuils par classe.** La barre de réussite (10) **et** le plancher de
compensation (7) se fixent en délibération, par قسم et par فصل. Chaque décision crée une version datée et signée du
règlement, et recalcule la section dans la foulée.

**Année suivante.** Ouvrir l'année N+1 recopie la structure — فصول,
programmes, coefficients — sans les notes ni les inscriptions. Les étudiantes
y sont réinscrites en lot, dans la section que l'administration choisit.

**Délibération.** Le moteur *propose* une décision ; le conseil peut la
surcharger avec un motif obligatoire et une trace nominative. Le calcul reste
visible à côté de la décision retenue, et un recalcul ne l'efface pas.

**Publication.** `مسودة → مفتوح للإدخال → مغلق → منشور`. Les étudiantes ne
voient leurs résultats qu'une fois publiés.

---

## La garantie de justesse

Le moteur a été reconstitué à partir des formules du fichier
« Résultat Trimestre 1 - A2 - 2025-2026.xlsx », puis **vérifié sur les 98
lignes réelles** de l'institut.

```bash
cd backend && .venv/Scripts/python.exe -m pytest
```

227 tests, dont deux jeux de référence qui rejouent les données réelles :
le moteur reproduit **exactement** les 98 moyennes, les 98 décisions globales
et toutes les décisions par matière produites par l'institut — d'abord en
isolation, puis à travers la chaîne complète (base, règlement stocké,
matérialisation).

Quatre rangs du fichier source sont des erreurs de saisie manuelle avérées
(section الحفيدات) ; le test vérifie que le moteur produit la valeur corrigée.

---

## Anomalies du fichier source

L'analyse complète est dans [`analyse/ANALYSE_ET_CONCEPTION.md`](analyse/ANALYSE_ET_CONCEPTION.md).

| Anomalie | Traitement |
|---|---|
| Matricule **24097 attribué à deux étudiantes**, absent des listes officielles | `matricule` unique en base ; l'import refuse la seconde et le signale |
| 4 rangs faux dans الحفيدات | Rangs recalculés, jamais saisis |
| Formules cassées (décisions testant la mauvaise colonne) | Une seule implémentation, testée |
| Formules écrasées par des valeurs collées | Le calcul est un service, pas une cellule |
| Absence indistinguable d'un zéro | Statut explicite : مسجلة · غائبة · غياب مبرر · معفاة |
| Aucune trace de qui a saisi quoi | `GradeHistory` immuable + journal d'audit |

**Action attendue de la direction** : attribuer un matricule aux deux
étudiantes qui portent le 24097.

---

## Contrôle d'accès

Quatre rôles — مدير, مساعد الإدارة, أستاذ, طالبة — mais
l'autorisation repose sur des **permissions**, pas sur le nom du rôle. La
matrice s'édite dans `/droits`, et une capacité peut aussi se confier à une
personne en particulier sans changer son rôle.

Le même code garde l'entrée de menu et l'endpoint : masquer sans fermer la
route serait du décor. L'administration, elle, peut tout et ne peut pas s'en
priver.

## Sécurité

- Argon2id, 12 caractères minimum, changement forcé à la première connexion.
- Session en cookie `httpOnly` + `SameSite=Strict` posée par le BFF Next.js :
  aucun jeton n'atteint le JavaScript du navigateur.
- Verrouillage après 5 échecs ; message de connexion unique qui ne révèle
  jamais si un compte existe.
- Filtrage **au niveau du queryset** : forger l'identifiant du résultat d'une
  camarade renvoie 404, pas la donnée.
- Relais BFF restreint par liste blanche de chemins.
- Journal d'audit : connexions, notes, coefficients, décisions, publications.

---

## Interface

Identité visuelle reprise de SIGA — même palette (`#006633` / `#E5C018` /
`#C82020`), mêmes ombres, sidebar repliable et topbar collante — adaptée au
RTL : sidebar à droite, propriétés CSS logiques uniquement. Le logo a été
extrait des listes PDF officielles de l'institut.

| Chemin | Écran | Rôles |
|---|---|---|
| `/connexion` · `/mot-de-passe` | Accès | tous |
| `/` | Relevé personnel, mes matières, ou tableau de bord | selon le rôle |
| `/saisie-notes` | Poste de saisie : avancement par قسم + grille | `notes.saisir` |
| `/resultats` | Classement d'une section | أستاذ · مدير |
| `/deliberation` | Décisions du jury et publication | مدير |
| `/structure` | Matières et coefficients — éditable | مدير |
| `/annees` | Années, ouverture de N+1, réinscription | مدير |
| `/etudiantes` | Liste, recherche, filtre par قسم | `etudiantes.gerer` |
| `/droits` | Rôles, permissions, droits individuels | `comptes.gerer` |
| `/journal` | Audit des modifications de notes | مدير |

La barre du haut porte un **sélecteur de فصل** : on le choisit une fois
et tous les écrans s'y tiennent. Le choix est mémorisé par cookie ; une URL
qui désigne explicitement un فصل reste prioritaire.

Les listes sont paginées (25 lignes) par des liens, donc partageables et
utilisables sans JavaScript. La grille de saisie, elle, n'est pas paginée :
une colonne de notes se saisit d'un bloc.

---

## Reste à faire

Les étapes 1 à 3 du plan sont livrées (socle, structure, moteur), ainsi que
les écrans de saisie, de résultats et de délibération. Restent :

- bulletins PDF en arabe RTL (WeasyPrint) à la publication, logo de
  l'institut en en-tête ;
- tableaux de bord de pilotage et alertes de saisie incomplète ;
- 2FA pour les comptes administrateurs (dépendances déjà en place) ;
- collecte des enseignants et de leurs affectations — absents des fichiers
  fournis ;
- déploiement PostgreSQL et sauvegardes.
