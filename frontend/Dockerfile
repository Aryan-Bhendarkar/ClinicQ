# ---- build stage: Node compiles the React app ----
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# ---- runtime stage: unprivileged Nginx serves static files (runs as uid 101, port 8080) ----
FROM nginxinc/nginx-unprivileged:1.27-alpine
ENV BACKEND_URL=http://backend:8000

# Pull in Alpine security fixes released after the base image was built, then drop root again.
USER root
RUN apk upgrade --no-cache
USER 101

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
EXPOSE 8080
