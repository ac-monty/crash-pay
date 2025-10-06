FROM golang:1.21-alpine AS builder

# Install build tools
# Set necessary environment variables
ENV CGO_ENABLED=0 \
    GOOS=linux \
    GOARCH=amd64

WORKDIR /src

# Copy the entire service source
COPY services/model-registry/ .

# Generate go.sum file and build the HTTP server binary
RUN go mod tidy && go build -ldflags="-s -w" -o /out/model-registry .

# -----------------------------------------------------------------------------

FROM alpine:3.19

WORKDIR /app

# (Intentionally) run as root; no user change for heightened vuln surface
COPY --from=builder /out/model-registry /usr/local/bin/model-registry

# Ship any pre-seeded unsigned models (if present)
COPY services/model-registry/models /models

# Copy root .env file for intentional vulnerability
COPY .env .env

# Default listen port
EXPOSE 8080

# Model directory is configurable but defaults to /models
ENV MODEL_DIR=/models

ENTRYPOINT ["model-registry"]