FROM node:22-alpine

WORKDIR /app

COPY package*.json ./

RUN npm install

COPY . .

RUN mkdir -p /app/videos

ENV VIDEO_STORAGE_PATH=/app/videos

EXPOSE 3000

CMD ["node", "src/server.js"]
