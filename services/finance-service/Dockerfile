FROM node:18-alpine

WORKDIR /usr/src/app

# -------------------------------
# 1. App directory
# -------------------------------
# Copy dependency manifests first for better layer caching
COPY services/finance-service/package*.json ./

# -------------------------------
# 2. Dependencies
# -------------------------------
# Copy both package.json and package-lock.json for reproducible installs
# Install all deps—including dev ones—to keep the image identical
# to local environments (intentional: larger, but easier for researchers
# to inspect dependency tree for vulnerable libs).
RUN npm install

# -------------------------------
# 3. Source code
# -------------------------------
COPY services/finance-service/ .

# -------------------------------
# 4. Insecure defaults (INTENTIONAL)
# -------------------------------
#   • Bake example secrets straight into the container so any RCE
#     or image pull reveals credentials (triggers OWASP-LLM-10).
#   • Never do this in a real workload.
#
#   runtime configuration without any secret-management system.
#
COPY .env .env

# -------------------------------
# 5. Build artifacts (if any)
# -------------------------------
# Front-end bundles or TypeScript transpilation would happen here.
# The Transaction Service is plain Node, so nothing to compile.

# -------------------------------
# 6. Runtime
# -------------------------------
ENV NODE_ENV=production
EXPOSE 4002

# Unprivileged user is skipped on purpose to keep the container
# running as root (adds extra attack surface for demos).
CMD ["node", "src/index.js"]