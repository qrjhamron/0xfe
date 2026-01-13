FROM rust:1.85 as builder
WORKDIR /app
COPY . .
RUN cargo build --release

FROM debian:bookworm-slim
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y ca-certificates libsqlite3-0 && rm -rf /var/lib/apt/lists/*

# Create unprivileged user
RUN useradd -m -s /bin/bash pastebin

# Copy binary and config
COPY --from=builder /app/target/release/pastebin_cli .
COPY config.toml .

# Create data and log directories
RUN mkdir data logs && \
    chown -R pastebin:pastebin /app && \
    chmod 755 /app && \
    chmod 700 data logs

# Switch to unprivileged user
USER pastebin

# Expose port
EXPOSE 3000

# Run with read-only root filesystem (except volumes)
# This is usually enforced by docker run --read-only, but we prepare for it.
CMD ["./pastebin_cli"]