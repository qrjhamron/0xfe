use axum::{
    response::Response,
    middleware::Next,
    extract::Request,
    http::{StatusCode, HeaderValue},
};
use governor::{Quota, RateLimiter, state::keyed::DashMapStateStore, clock::DefaultClock};
use std::num::NonZeroU32;
use std::sync::Arc;
use dashmap::DashMap;
use std::time::{Duration, Instant};
use tracing::warn;
use std::net::SocketAddr;
use std::sync::OnceLock;
use axum::extract::ConnectInfo;
use crate::app_metrics::{AUTH_FAILURES_TOTAL, RATE_LIMIT_HITS_TOTAL};

type RateLimiterType = RateLimiter<SocketAddr, DashMapStateStore<SocketAddr>, DefaultClock>;

pub struct SecurityState {
    pub limit_1s: RateLimiterType,
    pub limit_1m: RateLimiterType,
    pub limit_1h: RateLimiterType,
    pub failed_auths: DashMap<SocketAddr, AuthFailure>,
    pub concurrent_conns: DashMap<SocketAddr, usize>,
}

#[derive(Clone)]
pub struct AuthFailure {
    pub count: u32,
    pub last_attempt: Instant,
    pub blocked_until: Option<Instant>,
}

pub static SECURITY_STATE: OnceLock<Arc<SecurityState>> = OnceLock::new();

pub fn init_security_state() {
    let state = Arc::new(SecurityState {
        limit_1s: RateLimiter::dashmap(Quota::per_second(NonZeroU32::new(5).unwrap())),
        limit_1m: RateLimiter::dashmap(Quota::per_minute(NonZeroU32::new(60).unwrap())),
        limit_1h: RateLimiter::dashmap(Quota::per_hour(NonZeroU32::new(100).unwrap())),
        failed_auths: DashMap::new(),
        concurrent_conns: DashMap::new(),
    });
    SECURITY_STATE.set(state).ok();
}

pub fn get_security_state() -> &'static Arc<SecurityState> {
    SECURITY_STATE.get().expect("Security state not initialized")
}

pub async fn security_headers(req: Request, next: Next) -> Response {
    let mut response = next.run(req).await;
    let headers = response.headers_mut();
    
    // NSA-Level Hardening Headers
    headers.insert("X-Content-Type-Options", HeaderValue::from_static("nosniff"));
    headers.insert("X-Frame-Options", HeaderValue::from_static("DENY"));
    headers.insert("Strict-Transport-Security", HeaderValue::from_static("max-age=63072000; includeSubDomains; preload"));
    
    // Strict CSP: Only self-hosted images and inline styles for the brutalist UI. No scripts.
    headers.insert("Content-Security-Policy", HeaderValue::from_static(
        "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; font-src 'none'; \
        frame-ancestors 'none'; base-uri 'none'; form-action 'self'; block-all-mixed-content;"
    ));
    
    headers.insert("Referrer-Policy", HeaderValue::from_static("no-referrer"));
    headers.insert("Permissions-Policy", HeaderValue::from_static(
        "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), \
        microphone=(), payment=(), usb=(), interest-cohort=(), sync-xhr=()"
    ));
    
    // Extra Hardening
    headers.insert("X-XSS-Protection", HeaderValue::from_static("1; mode=block"));
    headers.insert("X-Download-Options", HeaderValue::from_static("noopen"));
    headers.insert("X-Permitted-Cross-Domain-Policies", HeaderValue::from_static("none"));

    // OS Fingerprint Spoofing (OpenBSD/BSD Mimicry)
    headers.insert("Server", HeaderValue::from_static("OpenBSD httpd"));
    headers.insert("X-Powered-By", HeaderValue::from_static("PHP/5.6.40")); // Deception
    
    response
}

pub async fn rate_limit_middleware(
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
    req: Request,
    next: Next,
) -> Result<Response, StatusCode> {
    let state = get_security_state();
    let ip = addr; 

    if state.limit_1s.check_key(&addr).is_err() {
        security_log("Rate limit exceeded (1s)", &ip.to_string());
        metrics::counter!(RATE_LIMIT_HITS_TOTAL).increment(1);
        return Err(StatusCode::TOO_MANY_REQUESTS);
    }
    if state.limit_1m.check_key(&addr).is_err() {
        security_log("Rate limit exceeded (1m)", &ip.to_string());
        metrics::counter!(RATE_LIMIT_HITS_TOTAL).increment(1);
        return Err(StatusCode::TOO_MANY_REQUESTS);
    }
    if state.limit_1h.check_key(&addr).is_err() {
         security_log("Rate limit exceeded (1h)", &ip.to_string());
         metrics::counter!(RATE_LIMIT_HITS_TOTAL).increment(1);
         return Err(StatusCode::TOO_MANY_REQUESTS);
    }

    {
        let mut count = state.concurrent_conns.entry(addr).or_insert(0);
        if *count >= 10 {
             security_log("Concurrency limit exceeded", &ip.to_string());
             return Err(StatusCode::SERVICE_UNAVAILABLE);
        }
        *count += 1;
    }

    let response = next.run(req).await;

    if let Some(mut count) = state.concurrent_conns.get_mut(&addr) {
        if *count > 0 {
            *count -= 1;
        }
    }

    Ok(response)
}

pub fn check_auth_attempt(ip: SocketAddr) -> Result<(), u64> {
    let state = get_security_state();
    if let Some(mut entry) = state.failed_auths.get_mut(&ip) {
        if let Some(blocked_until) = entry.blocked_until {
            if Instant::now() < blocked_until {
                security_log("Blocked auth attempt", &ip.to_string());
                return Err(blocked_until.duration_since(Instant::now()).as_secs());
            } else {
                entry.blocked_until = None;
                entry.count = 0; 
            }
        }
    }
    Ok(())
}

pub fn record_auth_failure(ip: SocketAddr) -> u64 {
    metrics::counter!(AUTH_FAILURES_TOTAL).increment(1);
    let state = get_security_state();
    let mut entry = state.failed_auths.entry(ip).or_insert(AuthFailure {
        count: 0,
        last_attempt: Instant::now(),
        blocked_until: None,
    });

    entry.count += 1;
    entry.last_attempt = Instant::now();

    let delay = match entry.count {
        1 => 1,
        2 => 2,
        3 => 4,
        4 => 8,
        5 => 16,
        _ => 60,
    };

    if entry.count >= 5 {
        entry.blocked_until = Some(Instant::now() + Duration::from_secs(300));
        security_log("IP Locked out due to excessive auth failures", &ip.to_string());
        return 300;
    }

    security_log(&format!("Auth failed (Attempt {})", entry.count), &ip.to_string());
    delay
}

pub fn security_log(event: &str, ip: &str) {
    warn!(target: "security_events", ip = %ip, event = %event, "[SECURITY] {} from {}", event, ip);
}

pub async fn scan_file(path: &std::path::Path) -> Result<(), String> {
    use tokio::process::Command;
    
    // Attempt to use clamdscan (daemon) first for speed
    // This requires clamd to be running and accessible
    // If command not found, we log warning and pass (Fail Open for dev/demo, Fail Closed for High Security)
    
    match Command::new("clamdscan").arg("--fdpass").arg("--no-summary").arg(path).status().await {
        Ok(status) => {
            if status.success() {
                Ok(())
            } else {
                // Exit code 1 usually means virus found
                security_log("Malware detected by clamdscan", "SYSTEM");
                Err("Malware detected".into())
            }
        },
        Err(_e) => {
            // If clamdscan is missing, try clamscan
            match Command::new("clamscan").arg(path).status().await {
                Ok(status) => {
                    if status.success() {
                         Ok(())
                    } else {
                        security_log("Malware detected by clamscan", "SYSTEM");
                        Err("Malware detected".into())
                    }
                },
                Err(_) => {
                    // Both missing. Log warning.
                    warn!("Virus scanner (clamdscan/clamscan) not found. Skipping scan.");
                    Ok(()) // Fail Open
                }
            }
        }
    }
}
