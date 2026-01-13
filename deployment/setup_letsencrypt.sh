#!/bin/bash
# Let's Encrypt TLS Certificate Setup
# Configure DOMAIN and EMAIL below before running
# Installs certbot, obtains certificate, sets up automatic renewal

set -e

# ============= CONFIGURATION =============
# Edit these values for your deployment
DOMAIN="${CERT_DOMAIN:-your-domain.com}"
EMAIL="${CERT_EMAIL:-admin@your-domain.com}"
# =========================================

SERVICE_USER="pastebin"
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
DEPLOYMENT_DIR="/opt/pastebin"

echo "Setting up Let's Encrypt certificates for ${DOMAIN}..."

# Install certbot if not already installed
if ! command -v certbot &> /dev/null; then
    echo "Installing certbot..."
    apt-get update
    apt-get install -y certbot python3-certbot-dns-cloudflare certbot-nginx
fi

# Create/verify certificate using DNS-01 challenge
echo "Requesting certificate via DNS-01 challenge..."
if [ ! -d "${CERT_DIR}" ]; then
    certbot certonly \
        --preferred-challenges=dns \
        --dns-cloudflare \
        --dns-cloudflare-credentials ~/.certbot/cloudflare.ini \
        -d "${DOMAIN}" \
        --email "${EMAIL}" \
        --agree-tos \
        --non-interactive \
        --register-unsafely-without-email || true
    
    # Fallback to HTTP-01 if DNS fails
    if [ ! -d "${CERT_DIR}" ]; then
        echo "DNS-01 failed, attempting HTTP-01..."
        certbot certonly \
            --preferred-challenges=http \
            --webroot \
            -w /var/www/certbot \
            -d "${DOMAIN}" \
            --email "${EMAIL}" \
            --agree-tos \
            --non-interactive \
            --register-unsafely-without-email
    fi
fi

# Set proper permissions
echo "Setting certificate permissions..."
chmod 0644 "${CERT_DIR}/fullchain.pem"
chmod 0644 "${CERT_DIR}/chain.pem"
chmod 0600 "${CERT_DIR}/privkey.pem"

# Change ownership if service user exists
if id "${SERVICE_USER}" &>/dev/null; then
    chown -R "${SERVICE_USER}:${SERVICE_USER}" "${CERT_DIR}"
fi

# Copy to deployment directory for application
if [ -d "${DEPLOYMENT_DIR}" ]; then
    cp "${CERT_DIR}/fullchain.pem" "${DEPLOYMENT_DIR}/certs/cert.pem"
    cp "${CERT_DIR}/privkey.pem" "${DEPLOYMENT_DIR}/certs/key.pem"
    chmod 0644 "${DEPLOYMENT_DIR}/certs/cert.pem"
    chmod 0600 "${DEPLOYMENT_DIR}/certs/key.pem"
    if id "${SERVICE_USER}" &>/dev/null; then
        chown "${SERVICE_USER}:${SERVICE_USER}" "${DEPLOYMENT_DIR}/certs/"*
    fi
fi

# Create systemd timer for automatic renewal
echo "Setting up automatic certificate renewal..."
cat > /etc/systemd/system/certbot-renewal.service << 'EOF'
[Unit]
Description=Certbot Renewal
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/certbot renew --quiet --post-hook "systemctl reload pastebin-service"
EOF

cat > /etc/systemd/system/certbot-renewal.timer << 'EOF'
[Unit]
Description=Certbot Renewal Timer
Requires=certbot-renewal.service

[Timer]
OnBootSec=1h
OnUnitActiveSec=12h
RandomizedDelaySec=1h
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Enable and start the timer
systemctl daemon-reload
systemctl enable certbot-renewal.timer
systemctl start certbot-renewal.timer

echo "Certificate setup complete!"
echo "Certificate path: ${CERT_DIR}"
echo "Renewal timer enabled and started"

# Verify certificate
echo "Verifying certificate installation..."
openssl x509 -in "${CERT_DIR}/cert.pem" -text -noout | grep -A 2 "Subject:\|Issuer:\|Not Before\|Not After"
