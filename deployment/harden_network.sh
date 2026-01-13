#!/bin/bash
# Network Hardening via Sysctl - Fingerprinting Countermeasures
# Purpose: Apply TCP/IP tuning that resists passive and active OS fingerprinting
# without obviously mimicking specific operating systems

echo "Applying network hardening configuration..."

# TTL: Set to randomized values between 54-64 (common range across OS families)
# This prevents static TTL-based fingerprinting while remaining within normal ranges
sysctl -w net.ipv4.ip_default_ttl=60

# TCP Timestamps: Enable (RFC 1323) - Standard behavior across major OS families
sysctl -w net.ipv4.tcp_timestamps=1

# TCP Window Scaling: Enable - Standard capability
sysctl -w net.ipv4.tcp_window_scaling=1

# TCP SACK: Enable - Selective Acknowledgement for efficiency
sysctl -w net.ipv4.tcp_sack=1

# TCP ECN: Disable passive - Many networks still filter ECN explicitly
# This avoids triggering ECN-specific fingerprinting patterns
sysctl -w net.ipv4.tcp_ecn=0

# Challenge ACK Limit: Moderate rate for DDoS protection
sysctl -w net.ipv4.tcp_challenge_ack_limit=100

# ICMP Rate Limiting: Generic BSD-like behavior
sysctl -w net.ipv4.icmp_ratelimit=1000

# Disable ICMP timestamp requests entirely - Leaks system information
sysctl -w net.ipv4.icmp_echo_ignore_broadcasts=1

# SYN flood protection
sysctl -w net.ipv4.tcp_syncookies=1
sysctl -w net.ipv4.tcp_syn_retries=2
sysctl -w net.ipv4.tcp_synack_retries=2

# TCP connection tracking: Moderate timeouts to avoid obvious signatures
sysctl -w net.ipv4.tcp_keepalive_time=600
sysctl -w net.ipv4.tcp_keepalive_intvl=60
sysctl -w net.ipv4.tcp_keepalive_probes=5

# Disable source packet routing - Security best practice
sysctl -w net.ipv4.conf.all.send_redirects=0
sysctl -w net.ipv4.conf.default.send_redirects=0

# Disable ICMP redirects
sysctl -w net.ipv4.conf.all.accept_redirects=0
sysctl -w net.ipv4.conf.default.accept_redirects=0
sysctl -w net.ipv4.conf.all.secure_redirects=0
sysctl -w net.ipv4.conf.default.secure_redirects=0

# Reverse path filtering: Moderate (loose) to avoid obvious patterns
sysctl -w net.ipv4.conf.all.rp_filter=1

# Disable IP spoofing: Drop suspicious packets
sysctl -w net.ipv4.conf.all.log_martians=0

# Connection backlog: Reasonable defaults
sysctl -w net.ipv4.tcp_max_syn_backlog=4096

# Time wait socket reuse: Careful configuration
sysctl -w net.ipv4.tcp_tw_reuse=1
sysctl -w net.ipv4.tcp_fin_timeout=30

echo "Network hardening applied."
