FROM node:22-alpine AS builder

WORKDIR /app
COPY package.json yarn.lock* package-lock.json* ./
RUN npm install --frozen-lockfile 2>/dev/null || npm install

COPY . .

# PLACEHOLDER: VITE_API_URL is injected at build time via --build-arg
# In GitHub Actions this is set to the ALB DNS name
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
