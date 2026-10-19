#!/bin/sh
set -eu

directory="$1"
image="axllent/mailpit:v1.31.6@sha256:23fe39e81bde596a918000b3135c0f85dc8bb4c9ea6be274b051143f3e300387"

mkdir -p "$directory"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=127.0.0.1" \
  -addext "subjectAltName=IP:127.0.0.1,DNS:localhost" \
  -keyout "$directory/key.pem" -out "$directory/cert.pem" 2>/dev/null
printf 'goat:s3cret-pass\n' > "$directory/auth.txt"
chmod 0644 "$directory/key.pem" "$directory/cert.pem" "$directory/auth.txt"

start() {
  docker rm -f "$1" >/dev/null 2>&1 || true
  docker run -d --name "$1" -v "$directory:/tls:ro" \
    -e MP_SMTP_DISABLE_RDNS=true -e MP_DISABLE_VERSION_CHECK=true \
    -p "127.0.0.1:$2:1025" -p "127.0.0.1:$3:8025" "$image" \
    --smtp-tls-cert /tls/cert.pem --smtp-tls-key /tls/key.pem \
    --smtp-auth-file /tls/auth.txt "$4" >/dev/null
}

start goatnotify-mailpit-starttls 11587 18587 --smtp-require-starttls
start goatnotify-mailpit-tls 11465 18465 --smtp-require-tls
