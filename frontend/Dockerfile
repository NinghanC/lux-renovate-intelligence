FROM node:22-alpine

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend ./

CMD ["npx", "vite", "--host", "0.0.0.0", "--port", "5173"]
