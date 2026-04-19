FROM node:20-alpine
# node:20-alpine ships with a built-in `node` user (UID 1000); no useradd needed.
# Resolves Trivy DS-0002 (containers must specify USER).
WORKDIR /app
COPY --chown=node:node package*.json ./
USER node
RUN npm install
COPY --chown=node:node . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]
