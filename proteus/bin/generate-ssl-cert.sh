#!/bin/bash

# Create ssl directory if it doesn't exist
mkdir -p docker/volumes/nginx/ssl

# Generate self-signed certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout docker/volumes/nginx/ssl/nginx.key \
  -out docker/volumes/nginx/ssl/nginx.crt \
  -subj "/C=CN/ST=State/L=City/O=Organization/CN=localhost"

# Set proper permissions
chmod 644 docker/volumes/nginx/ssl/nginx.crt
chmod 600 docker/volumes/nginx/ssl/nginx.key

echo "SSL certificate generated successfully!"
