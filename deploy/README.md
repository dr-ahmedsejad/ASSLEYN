# Déploiement

Cinq conteneurs : PostgreSQL, Redis, Django, Next.js, Nginx. Les images sont
**construites sur la machine de déploiement** — aucun registre, aucune image
publiée. `docker compose build` lit les `Dockerfile` de `backend/` et de
`frontend/`.

```bash
git clone https://github.com/dr-ahmedsejad/ASSLEYN.git /opt/asleyn
cd /opt/asleyn/deploy
./deploy.sh init
```

`init` demande le domaine, tire les secrets au hasard dans `.env`, crée les
dossiers montés, construit les deux images et démarre la pile. Il attend que
chaque service soit *sain* avant de passer au suivant : un échec s'arrête là,
avec ses journaux, plutôt que de laisser une pile à moitié debout.

---

## Reprendre les données existantes

La base démarre vide si `initdb/` l'est — les migrations construisent alors un
schéma sans étudiantes. Pour repartir des données réelles, y déposer un dump
**avant le premier démarrage** :

```bash
pg_dump --no-owner --no-privileges asleyn | gzip > initdb/00-donnees.sql.gz
```

Les deux drapeaux ne sont pas facultatifs : sans eux, le dump contient des
`ALTER … OWNER TO` qui désignent des rôles absents du conteneur, et l'import
s'interrompt.

Le contenu de `initdb/` n'est lu qu'**au tout premier démarrage**. Une fois le
volume `pg_data` créé, il est ignoré : `./deploy.sh reset-db` pour repartir de
zéro (destructif), `./deploy.sh restore` pour verser une sauvegarde dans une
base déjà en service.

---

## Exploitation

| Commande | Effet |
|---|---|
| `./deploy.sh update` | `git pull`, reconstruction, redémarrage. Les migrations passent avant que gunicorn n'accepte une requête. |
| `./deploy.sh backup` | Sauvegarde SQL compressée, vérifiée, 30 dernières conservées. |
| `./deploy.sh restore F` | Verse une sauvegarde (destructif, sauvegarde préalable automatique). |
| `./deploy.sh reset-db` | Repart du contenu de `initdb/` (destructif). |
| `./deploy.sh manage …` | Commande Django : `createsuperuser`, `create_student_accounts`… |
| `./deploy.sh logs [svc]` | Journaux. |
| `./deploy.sh status` | État des conteneurs, volumes, disque. |

Sauvegarde automatique — une ligne de `crontab -e` :

```
30 2 * * * cd /opt/asleyn/deploy && ./deploy.sh backup >> /var/log/asleyn-backup.log 2>&1
```

---

## Deux variantes de mise en ligne

**Domaine public** (défaut, `nginx.conf`). Le certificat est émis sur l'hôte,
avant le premier démarrage :

```bash
docker compose stop nginx
certbot certonly --standalone -d resultats.example.mr
docker compose start nginx
```

Le renouvellement passe ensuite par `certbot-webroot/`, sans interruption.

**Réseau local** (`nginx.lan.conf`), pour un serveur dans l'établissement :

```bash
./deploy.sh setup-lan 192.168.1.50
```

puis, dans `.env` : `DOMAIN=192.168.1.50` et
`ASLEYN_NGINX_CONF=./nginx.lan.conf`.

HTTPS reste indispensable même en local : la session Django est marquée
`Secure`, et un navigateur ne renvoie pas un cookie `Secure` sur une page en
clair. En HTTP simple, personne ne resterait connecté.

---

## Ce que cette pile fait différemment de SIGA

**Aucune adresse d'API dans le JavaScript livré.** SIGA injecte l'URL du
backend à la construction, puis la réécrit au vol dans Nginx (`sub_filter` sur
un placeholder) parce que le navigateur appelle Django directement. ASSLEYN
suit le patron BFF : le navigateur ne connaît pas Django, seul le serveur Next
l'appelle, et il lit `API_BASE_URL` à l'exécution. Une seule image sert donc
n'importe quel domaine, Nginx ne filtre rien, et le jeton de session ne quitte
jamais le serveur.

**Le domaine n'est pas écrit dans les fichiers du dépôt.** SIGA `sed` son
`docker-compose.yml` à l'installation, ce qu'un `git pull` remet en cause.
Ici, `${ASLEYN_DOMAIN}` est substitué au démarrage par l'image Nginx
(`NGINX_ENVSUBST_FILTER=ASLEYN_`, pour que `$host` et `$scheme` restent des
variables Nginx). Les fichiers versionnés ne bougent jamais.

**C'est le dossier `initdb/` qui est monté, pas le fichier de dump.** Docker
crée un répertoire à la place d'un fichier de montage absent : monter
`./dump.sql.gz` directement fait échouer PostgreSQL sur un « dump » qui est un
dossier, le jour où l'on démarre sans dump.

**Les conteneurs tournent sans privilèges** et rien ne se compile dans l'image
backend : `psycopg`, `argon2-cffi` et `cryptography` publient toutes des roues
binaires, l'image reste sur `slim` sans `gcc`. Le frontend utilise le build
autonome de Next (`output: "standalone"`), qui n'embarque que les modules
réellement atteints.

**La sonde interroge la base.** Un Django qui a perdu PostgreSQL répond encore
sur son port ; `/healthz/` vérifie la base et renvoie 503 sinon. Elle est
exemptée de la redirection HTTPS — sans quoi la sonde interne recevrait un 301
et Docker déclarerait le service en panne.

---

## Ports

Par défaut 80 et 443. Si la machine héberge déjà une autre application, poser
`HTTP_PORT` et `HTTPS_PORT` dans `.env` suffit — rien d'autre à changer.

Adminer n'est pas démarré par défaut. `docker compose --profile admin up -d`
l'expose sur `127.0.0.1:8092` uniquement : pour l'atteindre, un tunnel SSH
(`ssh -L 8092:127.0.0.1:8092 user@serveur`). Une console SQL ouverte sur le
réseau serait la porte d'entrée la plus large de toute la pile.
