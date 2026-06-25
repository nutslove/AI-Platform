# Frontend: Vite ビルド → nginx で静的配信
# --- build stage ---
FROM node:20-alpine AS build

WORKDIR /app

# 依存を先にインストールしてキャッシュを効かせる
COPY package.json package-lock.json* ./
RUN npm install

COPY . .
RUN npm run build

# --- runtime stage ---
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
