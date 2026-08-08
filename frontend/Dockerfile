# ---- build Vue app ----
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
# npmmirror 降低国内构建时 npm 超时概率
RUN npm ci --registry=https://registry.npmmirror.com

COPY . .

# Browser calls same-origin /api/v1; nginx proxies to backend
ENV VITE_API_BASE_URL=/api/v1

# Skip vue-tsc here: CI (Deploy to Server typecheck job) + local pre-push already gate types.
# Re-running vue-tsc on a small VPS inside docker often exceeds SSH command_timeout (40m).
RUN npm run build:docker

# ---- serve static + proxy API ----
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
