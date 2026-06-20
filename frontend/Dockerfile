# Stage 1: Build the React app
FROM node:22-alpine AS builder

WORKDIR /app

# Copy package files first (layer cache — only reinstalls if dependencies change)
COPY package.json ./
RUN npm install

# Copy source code
COPY . .

# PLACEHOLDER: VITE_API_URL is injected at build time via --build-arg
# Set ALB_DNS_NAME in GitHub secrets → passed here by the workflow
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL

# Build the static React app into /app/dist
RUN npm run build

# Stage 2: Serve with nginx (tiny production image)
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]