FROM node:18-alpine

WORKDIR /usr/src/app

# Create app directory
# Copy dependency manifests first for better layer caching
COPY services/user-service/package*.json ./

# Install app dependencies
# Including Sequelize ORM and PostgreSQL driver
RUN npm install

# Bundle app source
COPY services/user-service/ .

# Copy shared utilities for APM and logging
COPY shared/ ../shared/

# Copy root .env file for intentional vulnerability
COPY .env .env

# Default environment (overridden in prod by Secrets Manager)
ENV NODE_ENV=development \
    PORT=3001

EXPOSE 3001

# Start the (intentionally vulnerable) user-service
CMD ["node", "src/app.js"]