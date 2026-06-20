# ── Stage 1: Build React app ──────────────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

# VITE_API_URL is only needed at build time if you want the JS bundle to
# call the backend directly. With the nginx proxy approach we use here,
# the JS always calls relative URLs (/validate, /audit/sample etc.)
# and nginx forwards them to the backend — so VITE_API_URL can be empty.
ARG VITE_API_URL=
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# ── Stage 2: Serve with nginx + runtime env substitution ─────────────────────
FROM nginx:alpine

# Install gettext for envsubst (substitutes ${BACKEND_URL} in nginx.conf at startup)
RUN apk add --no-cache gettext

COPY --from=builder /app/dist /usr/share/nginx/html

# nginx.conf template — ${BACKEND_URL} is replaced at container startup
COPY nginx.conf /etc/nginx/templates/default.conf.template

EXPOSE 80

# envsubst replaces ${BACKEND_URL} in the nginx template before nginx starts
# BACKEND_URL should be the internal gateway URL, e.g.:
#   http://gateway-service.expense-audit-dev.local:8000
# This is set as an environment variable in the ECS task definition
CMD ["/bin/sh", "-c", \
     "envsubst '${BACKEND_URL}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
