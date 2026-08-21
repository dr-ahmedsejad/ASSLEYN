# ═══════════════════════════════════════════════════════════════════
# ASSLEYN — image du frontend Next.js
#
# Aucune variable n'est injectee a la build. C'est la consequence directe du
# BFF : le navigateur ne connait jamais l'adresse de Django, seul le serveur
# Next l'appelle, et il lit `API_BASE_URL` a l'execution. Une seule image
# sert donc n'importe quel domaine — pas de placeholder a reecrire dans le
# JavaScript livre, pas de build par environnement.
# ═══════════════════════════════════════════════════════════════════

# ─── Etape 1 : construction ────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

# Couche separee : `npm ci` n'est rejoue que si les manifestes changent.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Next attend ce dossier, meme vide.
RUN mkdir -p public

ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ─── Etape 2 : execution ───────────────────────────────────────────
FROM node:22-alpine

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# `node` existe deja dans l'image officielle, sans privileges : on s'en sert
# plutot que d'en creer un autre.
USER node

# Le build autonome se recopie en trois morceaux : le serveur et ses modules,
# les ressources compilees, et le dossier public.
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
COPY --from=builder --chown=node:node /app/public ./public

EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD node -e "require('http').get('http://127.0.0.1:3000/connexion',r=>process.exit(r.statusCode<400?0:1)).on('error',()=>process.exit(1))"

CMD ["node", "server.js"]
