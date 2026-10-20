FROM node:22-alpine AS build
WORKDIR /repo/my-classroom/frontend
RUN npm install -g pnpm@11.19.0
COPY my-classroom/frontend/package.json my-classroom/frontend/pnpm-lock.yaml my-classroom/frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY my-classroom/frontend .
COPY shared /repo/shared
COPY src/foundation /repo/src/foundation
RUN pnpm run build
FROM nginxinc/nginx-unprivileged:1.28-alpine
COPY --from=build /repo/my-classroom/frontend/dist /usr/share/nginx/html
COPY my-classroom/frontend/nginx.conf /etc/nginx/templates/default.conf.template
EXPOSE 8080
