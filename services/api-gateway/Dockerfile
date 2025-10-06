FROM node:18-alpine

WORKDIR /usr/src/app

# 1. Create app directory
# 2. Copy dependency manifests first for better layer caching
COPY services/api-gateway/package*.json ./

# 3. Install dependencies (no audit/fix, legacy peer deps allowed – intentionally lax)
RUN npm install --legacy-peer-deps --no-audit --progress=false

# 4. Copy source code into the container
COPY services/api-gateway/ .

# 5. Copy shared utilities for APM and logging
COPY shared/ ../shared/

# 6. Bake plaintext environment variables into the image (intentional mis-step)
COPY .env .env

# 7. Expose the API Gateway port
EXPOSE 3000

# 8. Start the vulnerable API Gateway with proper APM initialization
CMD ["npm", "start"]