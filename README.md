# 0xfe Pastebin (Hardened + Observability)

A minimalist, secure, CLI-focused pastebin service written in Rust with comprehensive security hardening and monitoring.

## Features

### Security & Hardening
- **TLS 1.3+**: Automated Let's Encrypt certificates with zero-downtime renewal
- **Input Validation**: Strict boundary validation preventing injection attacks
- **Rate Limiting**: Tiered per-IP limits (5 req/s, 60 req/min, 100 req/hour)
- **Brute-Force Protection**: Exponential backoff on failed authentication
- **Network Hardening**: TCP/IP fingerprinting resistance via sysctl tuning
- **SSH Hardening**: Generic banner, modern ciphers, key-only authentication
- **Content Integrity**: SHA256 hashing for tamper detection
- **Privacy**: IP address hashing for rate limiting without storing PII

### Content Handling
- **Intelligent Serving**: Smart content negotiation for CLI vs browsers
  - `curl/wget` → Raw unwrapped bytes
  - Browsers → HTML wrapper (for text) or inline (for media)
- **Magic Byte Detection**: File type detection via signature analysis
- **Proper MIME Types**: Code served as text/plain, images inline, archives as attachment
- **Streaming Upload**: Never loads full file into RAM

### Observability
- **Prometheus Metrics**: `/metrics` endpoint with detailed application/system metrics
- **Structured Logging**: JSON output to stdout with trace correlation IDs
- **Health Checks**: Deep system verification at `/health`
- **Status Dashboard**: Real-time metrics at `/status` with zero JavaScript
- **OpenTelemetry**: Distributed tracing support (Jaeger/Tempo)
- **Audit Trail**: Access logging with IP hashes and view counts

### Database
- **SQLite** (embedded, zero-config) with audit columns
- **Deduplication**: Content hash-based storage efficiency
- **Expiration**: Indexed cleanup for burn-after-read and TTL
- **Transaction Safety**: ACID compliance with automatic rollback
- **Prepared Statements**: Compile-time SQL injection prevention via sqlx::query!

## Quick Start

### Build

```bash
cargo build --release
```

### Configuration

Create `config.toml`:

```toml
port = 3000
database_url = "sqlite://data.db"
max_upload_size = 524288000  # 500MB
base_url = "https://localhost:3000"
cert_path = "certs/cert.pem"
key_path = "certs/key.pem"
security_log_path = "logs/security.log"
```

### Run

```bash
./target/release/pastebin_cli
```

## API Usage

### Upload (Multipart)

```bash
curl -F 'file=@document.pdf' https://localhost:3000/
curl -F 'file=@script.sh' -F 'pass=secret' https://localhost:3000/  # Password-protected
curl -F 'file=@temp.txt' -F 'burn=true' https://localhost:3000/     # Burn after read
curl -F 'file=@data.json' -F 'expire=86400' https://localhost:3000/ # 24-hour TTL
```

### Upload (Raw POST)

```bash
curl -X POST -H 'X-Filename: note.txt' --data-binary @note.txt https://localhost:3000/raw
```

### Download

```bash
curl https://localhost:3000/abc123              # Raw for CLI
curl https://localhost:3000/abc123 -b cookie    # With auth cookie if protected
curl https://localhost:3000/raw/abc123          # Force raw endpoint
```

### Delete

```bash
curl -X DELETE -d 'pass=secret' https://localhost:3000/abc123
```

### Health & Metrics

```bash
curl https://localhost:3000/health   # Deep health check
curl https://localhost:3000/metrics   # Prometheus format
curl https://localhost:3000/status    # Real-time dashboard
```

## Deployment

The deployment configuration includes:
- Let's Encrypt certificate setup
- Network hardening (sysctl)
- SSH hardening
- Systemd service configuration
- Firewall rules
- Monitoring setup

## Hardening Details

The hardening implementation includes:
- Complete network obfuscation strategy
- Input validation and sanitization
- Database schema enhancements
- TLS management
- Rate limiting architecture
- Security headers
- Logging and audit trail

## Architecture

```
┌─────────────────┐
│   Internet      │
└────────┬────────┘
         │ HTTPS (Let's Encrypt)
         │ TLS 1.3+
┌────────▼────────────────────────────┐
│   Firewall (UFW)                    │
│   - Rate limiting                   │
│   - Connection tracking             │
└────────┬────────────────────────────┘
         │
┌────────▼────────────────────────────┐
│   Axum Web Server                   │
│   - Input validation                │
│   - Security headers                │
│   - Request ID correlation          │
└────────┬────────────────────────────┘
         │
         ├──→ /{id}              (Smart content negotiation)
         ├──→ /raw/{id}          (Force raw)
         ├──→ /health            (System health)
         ├──→ /metrics           (Prometheus)
         └──→ /status            (Real-time dashboard)
         │
         ├──────────────────────────────┐
         │                              │
┌────────▼──────────────┐   ┌──────────▼──────────┐
│   SQLite Database     │   │   File Storage      │
│   - Audit columns     │   │   - Deduplication   │
│   - Indexed queries   │   │   - Streaming       │
│   - ACID transactions │   │   - Content hash    │
└───────────────────────┘   └─────────────────────┘
```

## Security

### Threat Model Coverage

| Threat | Mitigation |
|--------|-----------|
| Brute-force auth | Exponential backoff, rate limiting |
| SQL injection | Prepared statements via sqlx::query! |
| Path traversal | Whitelist validation in handlers |
| Large file OOM | Streaming upload, size limits |
| OS fingerprinting | TCP/IP tuning, generic banners |
| TLS downgrade | HSTS preload, TLS 1.3 only |
| CSRF/XSS | CSP: default-src 'none', no inline scripts |
| Information leakage | Generic error messages, redacted logs |
| Unencrypted passwords | Bcrypt cost=14 (100ms per check) |

### Future Enhancements

- [ ] Client-side WASM encryption
- [ ] Advanced traffic shaping (packet timing jitter)
- [ ] TUI admin interface (ratatui)
- [ ] RocksDB for write-heavy workloads
- [ ] Comprehensive Grafana dashboards
- [ ] Distributed tracing (Jaeger)

## Observability

### Prometheus Metrics

```
# Requests
app_http_requests_total{status="200",endpoint="/"}
app_http_request_duration_seconds{status="200",endpoint="/"}

# Security
app_auth_failures_total{ip_hash="..."}
app_rate_limit_hits_total{limit_type="1s"}

# Storage
app_storage_operations_total{operation="write"}
app_storage_bytes_used

# System
node_cpu_seconds_total
node_memory_MemAvailable_bytes
node_disk_io_reads_bytes_total
```

### Structured Logging (JSON)

```json
{
  "timestamp": "2026-01-12T15:20:00.123Z",
  "level": "INFO",
  "message": "Paste created",
  "trace_id": "abc123def456",
  "paste_id": "xyz789",
  "size_bytes": 45678,
  "mime_type": "text/plain",
  "client_ip_hash": "sha256(ip)"
}
```

### Log Aggregation

Outputs JSON to stdout → systemd journald → optional shipping (vector/fluent-bit)

## Development

### Run Tests

```bash
cargo test
```

### Linting

```bash
cargo clippy -- -D warnings
```

### Build Checks

```bash
cargo check
cargo build --release
```

## License

0xfe Pastebin - Hardened Implementation
