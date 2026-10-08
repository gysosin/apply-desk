#!/bin/sh
# Create a local CA and an HTTPS certificate for applydesk.localhost in ~/.config/applydesk-tls.
# Trust applydesk-ca.crt once in your OS/browser (see docs/apply-desk.md).
set -eu
D="$HOME/.config/applydesk-tls"
mkdir -p "$D" && cd "$D"
[ -f applydesk-ca.key ] || openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -sha256 \
  -subj "/CN=Apply Desk Local CA" -keyout applydesk-ca.key -out applydesk-ca.crt
openssl req -newkey rsa:2048 -nodes -subj "/CN=applydesk.localhost" -keyout server.key -out server.csr
printf "subjectAltName=DNS:applydesk.localhost\nbasicConstraints=CA:FALSE\nextendedKeyUsage=serverAuth\n" > ext.cnf
openssl x509 -req -in server.csr -CA applydesk-ca.crt -CAkey applydesk-ca.key -CAcreateserial \
  -days 825 -sha256 -extfile ext.cnf -out server.crt
rm -f server.csr ext.cnf
chmod 600 applydesk-ca.key server.key
echo "Certificate written to $D"
