FROM node:18-alpine

WORKDIR /usr/src/app

# ---- Application Setup --------------------------------------------------
# Install dependencies first (leverages Docker cache)
COPY services/mock-external-api/package*.json ./
RUN npm install

# Copy source code
COPY services/mock-external-api/ .

# Copy root .env file for intentional vulnerability
COPY .env .env

# ---- Runtime Configuration ----------------------------------------------
ENV PORT=3003

# HTTP only – do NOT expose TLS inside the container
EXPOSE 3003

# Use npm run dev for development with nodemon
CMD ["npm", "run", "dev"]