# syntax=docker/dockerfile:1
# Build context: repository root (needs infrastructure/nginx).
FROM node:22.12-alpine AS build
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27.3-alpine
RUN rm /etc/nginx/conf.d/default.conf
COPY infrastructure/nginx/nginx.conf /etc/nginx/conf.d/domainvitals.conf
COPY infrastructure/nginx/snippets/ /etc/nginx/snippets/
COPY --from=build /src/dist /usr/share/nginx/html
EXPOSE 80 443
