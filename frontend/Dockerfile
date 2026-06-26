# 构建阶段
FROM docker.1ms.run/library/node:18-alpine AS builder

WORKDIR /app

# 复制依赖文件
COPY package*.json ./

# 安装依赖（包含 devDependencies，Vite 需要）
RUN npm ci

# 复制源代码
COPY . .

# 构建生产版本
ARG NODE_ENV=production
ENV NODE_ENV=${NODE_ENV}
RUN npm run build

# 生产阶段
FROM docker.1ms.run/library/nginx:alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 5174

CMD ["nginx", "-g", "daemon off;"]
