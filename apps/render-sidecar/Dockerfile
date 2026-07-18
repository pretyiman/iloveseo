FROM ghcr.io/puppeteer/puppeteer:latest

WORKDIR /app
USER root

COPY package.json ./
RUN npm install

COPY src ./src

USER pptruser
EXPOSE 4000

CMD ["node", "src/index.js"]
