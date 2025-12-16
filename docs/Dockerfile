# 1. Базовый образ
FROM node:lts AS base
ENV FORCE_COLOR=1
RUN corepack enable
WORKDIR /opt/docusaurus

# 2a. Режим разработки (Dev)
FROM base AS dev
WORKDIR /opt/docusaurus
EXPOSE 3000
# Запуск с установкой зависимостей, если их нет
CMD [ -d "node_modules" ] && npm run start -- --host 0.0.0.0 --poll 1000 || npm install && npm run start -- --host 0.0.0.0 --poll 1000

# 2b. Сборка для продакшена (Prod)
FROM base AS prod
WORKDIR /opt/docusaurus
COPY . /opt/docusaurus/
RUN npm ci
RUN npm run build

# 3. Сервер для раздачи статики (Serve)
FROM prod AS serve
EXPOSE 3000
CMD ["npm", "run", "serve", "--", "--host", "0.0.0.0", "--no-open"]