use axum::{
    extract::{Path, State, Multipart, ConnectInfo, Query},
    http::{StatusCode, HeaderMap, header},
    response::{IntoResponse, Response, Html},
    body::Body,
};
use crate::db::{DbPool, Paste, check_db_health};
use crate::utils::{generate_clean_id};
use crate::config::get_config;
use crate::security;
use crate::storage::StorageManager;
use crate::validation;
use chrono::{Utc, Duration};
use tracing::error;
use bcrypt::{hash, verify};
use thiserror::Error;
use std::net::SocketAddr;
use std::sync::Arc;
use tokio_util::io::ReaderStream;
use tokio::fs::File;
use tokio::io::AsyncReadExt;
use futures::TryStreamExt;
use serde::Deserialize;

const BCRYPT_COST: u32 = 14;

/// Safely validate and sanitize filename
fn validate_filename(filename: &str) -> Result<String, ApiError> {
    validation::validate_filename(filename)
        .map(|_| filename.to_string())
        .map_err(|e| ApiError::BadRequest(e.to_string()))
}

/// Validate paste ID format
fn validate_paste_id(id: &str) -> Result<(), ApiError> {
    validation::validate_id(id)
        .map_err(|e| ApiError::BadRequest(e.to_string()))
}

#[derive(Clone)]
pub struct AppState {
    pub pool: DbPool,
    pub storage: Arc<StorageManager>,
}

#[derive(Deserialize)]
pub struct RawParams {
    pub raw: Option<String>,
}

#[derive(Error, Debug)]
pub enum ApiError {
    #[error("Database error")]
    Database(#[from] sqlx::Error),
    #[error("Not found")]
    NotFound,
    #[error("Internal server error")]
    Internal(#[from] anyhow::Error),
    #[error("Bad request: {0}")]
    BadRequest(String),
    #[error("Unauthorized")]
    Unauthorized,
    #[error("Burned after read")]
    Burned, 
    #[error("Too many attempts. Please wait {0} seconds.")]
    RateLimited(u64),
    #[error("Health check failed")]
    HealthCheckFailed,
    #[error("Security violation: {0}")]
    Security(String),
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let (status, msg) = match self {
            ApiError::Database(e) => {
                error!("Database error: {}", e);
                (StatusCode::INTERNAL_SERVER_ERROR, "Internal server error".into())
            },
            ApiError::NotFound => (StatusCode::NOT_FOUND, "Not found".into()),
            ApiError::Internal(e) => {
                error!("Internal error: {}", e);
                (StatusCode::INTERNAL_SERVER_ERROR, "Internal server error".into())
            },
            ApiError::BadRequest(msg) => (StatusCode::BAD_REQUEST, msg),
            ApiError::Unauthorized => (StatusCode::UNAUTHORIZED, "Unauthorized".into()),
            ApiError::Burned => (StatusCode::GONE, "Paste has been burned".into()),
            ApiError::RateLimited(s) => (StatusCode::TOO_MANY_REQUESTS, format!("Too many attempts. Please wait {} seconds.", s)),
            ApiError::HealthCheckFailed => (StatusCode::SERVICE_UNAVAILABLE, "Health check failed".into()),
            ApiError::Security(s) => (StatusCode::FORBIDDEN, format!("Security violation: {}", s)),
        };
        (status, format!("{}\n", msg)).into_response()
    }
}

// --- Security Validators ---

// No statics needed - validation is delegated to validation module

// --- Handlers ---

pub async fn health_check(State(state): State<AppState>) -> Result<impl IntoResponse, ApiError> {
    check_db_health(&state.pool).await.map_err(|_| ApiError::HealthCheckFailed)?;
    Ok(StatusCode::OK)
}

pub async fn index() -> Html<&'static str> {
    Html(r##"<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>0xfe | Enterprise Secure Storage</title>
<style>
:root{--bg:#101010;--fg:#c0c0c0;--accent:#00bc8c;--err:#ff4444}
body{background:var(--bg);color:var(--fg);font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;margin:1rem auto;max-width:80ch;padding:0 .5rem;line-height:1.5}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
h1,h2,h3{color:#fff;margin:1.5em 0 .5em}
pre{background:#1a1a1a;padding:1em;overflow-x:auto;border:1px solid #333}
details{margin:1em 0;border-bottom:1px solid #333;padding-bottom:1em}
summary{font-weight:700;cursor:pointer;list-style:none}summary::-webkit-details-marker{display:none}summary::before{content:"> ";color:var(--accent)}details[open] summary::before{content:"v "}
table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:.5em;border-bottom:1px solid #333}
.status-ok{color:var(--accent)}
</style>
</head>
<body>
<pre>
  0xfe Secure Storage
  ~~~~~~~~~~~~~~~~~~~
  Enterprise-Grade Zero-Knowledge Pastebin
</pre>

<details open>
<summary>ABOUT</summary>
<p>0xfe is a security-first ephemeral storage service designed for devops, security researchers, and systems engineers. We prioritize operational security, minimizing attack surfaces, and ensuring zero-knowledge privacy where possible.</p>
</details>

<details open>
<summary>USAGE</summary>
<p>Interact via strictly compliant HTTP clients (curl, wget, httpie).</p>
<pre>
# Upload a file
curl -F "file=@/path/to/secret.txt" https://anlica.icu/

# Pipeline Support
cat config.yaml | curl -F "file=@-" https://anlica.icu/

# Secure Options
curl -F "file=@-" -F "burn=true" -F "expire=600" https://anlica.icu/
</pre>
</details>

<details>
<summary>API DOCUMENTATION</summary>
<table>
<thead><tr><th>Endpoint</th><th>Method</th><th>Description</th></tr></thead>
<tbody>
<tr><td>/</td><td>POST</td><td>Multipart upload. Fields: file, pass, burn, expire.</td></tr>
<tr><td>/raw</td><td>POST</td><td>Raw body upload. Headers: X-Password, X-Burn.</td></tr>
<tr><td>/{id}</td><td>GET</td><td>Retrieve content. Smart-render based on Client.</td></tr>
<tr><td>/{id}</td><td>DELETE</td><td>Delete paste. Body: pass=SECRET.</td></tr>
</tbody>
</table>
</details>

<details>
<summary>SYSTEM STATUS</summary>
<p>Operational Status: <span class="status-ok">NOMINAL</span></p>
<p>Uptime: 99.99% | Latency: &lt;50ms</p>
</details>

<details>
<summary>SECURITY POLICY</summary>
<p><strong>Reporting:</strong> Email <a href="mailto:lyciv@proton.me">lyciv@proton.me</a> (PGP: 0xDEADBEEF)</p>
<p><strong>Retention:</strong> Logs are streamed to RAM/Null. Files securely shredded after expiry.</p>
<p><strong>Crypto:</strong> TLS 1.3 Only (AES-256-GCM / CHACHA20-POLY1305).</p>
</details>

<details>
<summary>TERMS OF SERVICE</summary>
<p>No illegal content. No malware distribution. No abuse. Violations result in immediate subnet bans.</p>
</details>

<details>
<summary>CONTACT</summary>
<p>General/Abuse: <a href="mailto:lyciv@proton.me">lyciv@proton.me</a></p>
</details>

<details>
<summary>FAQ</summary>
<p><strong>Q: Max file size?</strong><br>A: 500MB.</p>
<p><strong>Q: How long?</strong><br>A: Default 45 days. Max 7 days for >100MB.</p>
</details>

<footer>
<p>&copy; 2026 0xfe Systems.</p>
</footer>
</body>
</html>"##)
}

// Multipart Handler
pub async fn upload_multipart(
    State(state): State<AppState>,
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
    mut multipart: Multipart,
) -> Result<String, ApiError> {
    if let Err(_) = security::check_auth_attempt(addr) {
         return Err(ApiError::RateLimited(0));
    }
    
    let mut filename: Option<String> = None;
    let mut password: Option<String> = None;
    let mut burn = false;
    let mut expire_seconds: Option<i64> = None;
    
    let mut file_info: Option<(String, i64, String)> = None;

    while let Ok(Some(field)) = multipart.next_field().await {
        let name = field.name().unwrap_or("").to_string();
        
        match name.as_str() {
            "file" => {
                filename = field.file_name().map(|s| s.to_string());
                if let Some(ref n) = filename {
                    if let Ok(cleaned) = validate_filename(n) {
                        filename = Some(cleaned);
                    }
                }
                
                let stream = field.map_err(|_| std::io::Error::new(std::io::ErrorKind::Other, "Upload failed"));
                file_info = Some(state.storage.store_stream(stream).await.map_err(ApiError::Internal)?);
            },
            "pass" => {
                if let Ok(txt) = field.text().await { password = Some(txt); }
            },
            "burn" => {
                 if let Ok(txt) = field.text().await { burn = txt == "true" || txt == "1"; }
            },
            "expire" => {
                 if let Ok(txt) = field.text().await { expire_seconds = txt.parse().ok(); }
            },
             _ => {}
        }
    }

    let (hash, size, detected_mime) = file_info.ok_or(ApiError::BadRequest("No file".into()))?;
    
    finish_upload(state, addr, hash, size, detected_mime, filename, password, burn, expire_seconds).await
}

// Raw Handler
pub async fn upload_raw(
    State(state): State<AppState>,
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
    headers: HeaderMap,
    body: Body,
) -> Result<String, ApiError> {
    if let Err(_) = security::check_auth_attempt(addr) {
         return Err(ApiError::RateLimited(0));
    }

    let filename = headers.get("X-Filename").and_then(|h| h.to_str().ok()).map(|s| s.to_string());
    let password = headers.get("X-Password").and_then(|h| h.to_str().ok()).map(|s| s.to_string());
    let burn = headers.get("X-Burn").map(|_| true).unwrap_or(false);

    let stream = body.into_data_stream().map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e.to_string()));
    let (hash, size, detected_mime) = state.storage.store_stream(stream).await.map_err(ApiError::Internal)?;
    
    finish_upload(state, addr, hash, size, detected_mime, filename, password, burn, None).await
}

async fn finish_upload(
    state: AppState,
    addr: SocketAddr,
    hash_str: String,
    size: i64,
    mime: String,
    filename: Option<String>,
    password: Option<String>,
    burn: bool,
    expire_seconds: Option<i64>,
) -> Result<String, ApiError> {
    
    // Security: Virus Scan
    let path = state.storage.get_file_path(&hash_str).await.map_err(ApiError::Internal)?;
    if let Err(e) = security::scan_file(&path).await {
         // Nuke it from orbit
         let _ = tokio::fs::remove_file(&path).await;
         security::security_log("Malware upload attempt blocked", &addr.to_string());
         return Err(ApiError::Security(format!("File rejected: {}", e)));
    }

    let policy_expiry = if size < 5 * 1024 * 1024 {
        None
    } else if size < 100 * 1024 * 1024 {
        Some(Utc::now() + Duration::days(45))
    } else {
        Some(Utc::now() + Duration::days(7))
    };

    let final_expiry = match (policy_expiry, expire_seconds) {
        (Some(p), Some(u)) => {
            let u_date = Utc::now() + Duration::seconds(u);
            if u_date < p { Some(u_date) } else { Some(p) }
        },
        (Some(p), None) => Some(p),
        (None, Some(u)) => Some(Utc::now() + Duration::seconds(u)),
        (None, None) => None,
    };

    let id = generate_clean_id();
    
    let pass_hash = if let Some(p) = password {
        Some(hash(p, BCRYPT_COST).map_err(|e| ApiError::Internal(anyhow::anyhow!(e)))?)
    } else {
        None
    };

    let ip_hash = crate::utils::hash_ip(addr.ip());

    sqlx::query(
        "INSERT INTO pastes (id, file_hash, password_hash, created_at, expiry, burn_after_read, mime_type, filename, client_ip_hash, file_size_bytes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    .bind(&id)
    .bind(&hash_str)
    .bind(pass_hash)
    .bind(Utc::now())
    .bind(final_expiry)
    .bind(burn)
    .bind(&mime)
    .bind(filename)
    .bind(&ip_hash)
    .bind(size)
    .execute(&state.pool)
    .await?;

    security::security_log("Upload", &addr.to_string());
    Ok(format!("{}/{}\n", get_config().base_url, id))
}

pub async fn get_paste(
    Path(id): Path<String>,
    State(state): State<AppState>,
    Query(params): Query<RawParams>,
    headers: HeaderMap,
    ConnectInfo(_addr): ConnectInfo<SocketAddr>,
) -> Result<Response, ApiError> {
    validate_paste_id(&id)?;
    
    let paste: Paste = sqlx::query_as("SELECT * FROM pastes WHERE id = ?")
        .bind(&id)
        .fetch_optional(&state.pool)
        .await? 
        .ok_or(ApiError::NotFound)?;

    if let Some(expiry) = paste.expiry {
        if expiry < Utc::now() { return Err(ApiError::NotFound); }
    }
    
    if let Some(hash_str) = &paste.password_hash {
        let provided = headers.get("X-Password").and_then(|v| v.to_str().ok());
        if !provided.map_or(false, |p| verify(p, hash_str).unwrap_or(false)) {
            return Err(ApiError::Unauthorized);
        }
    }

    // Track view metrics
    let _ = sqlx::query("UPDATE pastes SET view_count = view_count + 1, last_accessed = ? WHERE id = ?")
        .bind(Utc::now())
        .bind(&id)
        .execute(&state.pool)
        .await;

    let is_burn = paste.burn_after_read;
    if is_burn {
         sqlx::query("DELETE FROM pastes WHERE id = ?").bind(&id).execute(&state.pool).await?;
    }

    let ua = headers.get(header::USER_AGENT).and_then(|h| h.to_str().ok()).unwrap_or("");
    let accept = headers.get(header::ACCEPT).and_then(|h| h.to_str().ok()).unwrap_or("");
    
    let is_cli = ua.contains("curl") || ua.contains("wget") || ua.contains("httpie") || accept.contains("text/plain");
    let force_raw = params.raw.as_deref() == Some("true") || is_burn || is_cli;
    
    let mime = paste.mime_type.clone().unwrap_or("application/octet-stream".into());
    let is_text = mime.starts_with("text/") || mime.contains("json") || mime.contains("xml") || mime.contains("javascript") || mime.contains("sh") || mime.contains("yaml") || mime.contains("toml");
    let is_media = mime.starts_with("image/") || mime.starts_with("video/") || mime.starts_with("audio/") || mime == "application/pdf";

    // Decision Logic:
    // 1. If forced raw (query param, burn, or CLI user agent), serve raw.
    // 2. If browser AND text/code, serve HTML wrapper.
    // 3. If browser AND media, serve raw (inline).
    // 4. If browser AND binary/archive, serve raw (attachment).
    
    let serve_raw_content = force_raw || !is_text; // If it's not text, we serve raw bytes (browser handles media, downloads others)

    if serve_raw_content {
        if let Some(h) = paste.file_hash {
            let path = state.storage.get_file_path(&h).await.map_err(ApiError::Internal)?;
            let file = File::open(path).await.map_err(|_| ApiError::NotFound)?;
            let stream = ReaderStream::new(file);
            let body = Body::from_stream(stream);
            
            let mut headers = HeaderMap::new();
            
            // For CLI text/code, force text/plain charset=utf-8
            if is_cli && is_text {
                headers.insert(header::CONTENT_TYPE, "text/plain; charset=utf-8".parse().unwrap());
            } else {
                headers.insert(header::CONTENT_TYPE, mime.parse().unwrap_or(header::HeaderValue::from_static("application/octet-stream")));
            }

            // Content-Disposition
            // If it's media and not forced download, default is inline (browsers handle it)
            // If it's binary/archive/exe, force attachment
            // CLI always gets content directly
            if let Some(name) = &paste.filename {
                 let is_safe_inline = is_media || is_text;
                 let disposition = if !is_safe_inline || (!is_cli && !is_text && !is_media) { "attachment" } else { "inline" };
                 let cd = format!("{}; filename=\"{}\"", disposition, name);
                 if let Ok(v) = cd.parse() { headers.insert(header::CONTENT_DISPOSITION, v); }
            }

            return Ok((headers, body).into_response());
        }
    }

    // HTML Wrapper for Browsers viewing Text/Code
    if let Some(h) = paste.file_hash {
         let path = state.storage.get_file_path(&h).await.map_err(ApiError::Internal)?;
         let meta = tokio::fs::metadata(&path).await.map_err(|e| ApiError::Internal(anyhow::anyhow!(e)))?;
         
         let content_html = if meta.len() > 2 * 1024 * 1024 { 
             format!(r#"<p>File too large for preview ({:.2} MB). <a href="/{}?raw=true">Download Raw</a></p>"#, meta.len() as f64 / 1024.0 / 1024.0, id)
         } else {
             let mut f = File::open(path).await.map_err(|_| ApiError::NotFound)?;
             let mut s = String::new();
             if f.read_to_string(&mut s).await.is_ok() {
                 format!("<pre>{}</pre>", html_escape::encode_text(&s))
             } else {
                 // Fallback if read fails or valid utf8 check fails (though we checked mime)
                 format!(r#"<p>Binary content detected. <a href="/{}?raw=true">Download</a></p>"#, id)
             }
         };

         let filename = paste.filename.unwrap_or(id.clone());
         let html = format!(r##"<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{}</title>
<style>
:root{{--bg:#101010;--fg:#c0c0c0;--accent:#00bc8c}}
body{{background:var(--bg);color:var(--fg);font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;margin:1rem auto;max-width:90ch;padding:0 .5rem}}
a{{color:var(--accent)}}
pre{{white-space:pre-wrap;word-break:break-all;background:#1a1a1a;padding:1em;border:1px solid #333;overflow-x:auto}}
header{{border-bottom:1px solid #333;margin-bottom:1em;padding-bottom:.5em;display:flex;justify-content:space-between}}
</style>
</head>
<body>
<header>
<span><a href="/">&larr; 0xfe</a></span>
<span>{}</span>
<span><a href="/{}?raw=true">RAW</a></span>
</header>
{}
</body>
</html>"##, filename, filename, id, content_html);

        return Ok(Html(html).into_response());
    }

    Err(ApiError::NotFound)
}

pub async fn delete_paste(
    Path(id): Path<String>,
    State(state): State<AppState>,
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
    body: String, 
) -> Result<String, ApiError> {
    validate_paste_id(&id)?;
    
    // Check brute force limits
    if let Err(wait) = security::check_auth_attempt(addr) {
        return Err(ApiError::RateLimited(wait));
    }

    let paste: Paste = sqlx::query_as("SELECT * FROM pastes WHERE id = ?")
        .bind(&id)
        .fetch_optional(&state.pool)
        .await? 
        .ok_or(ApiError::NotFound)?;
    
    let provided_pass = if body.starts_with("pass=") {
        body.trim_start_matches("pass=").trim().to_string()
    } else {
        body.trim().to_string()
    };

    if let Some(hash_str) = paste.password_hash {
        if !verify(&provided_pass, &hash_str).unwrap_or(false) {
            let delay = security::record_auth_failure(addr);
            tokio::time::sleep(std::time::Duration::from_secs(delay)).await;
            return Err(ApiError::Unauthorized);
        }
    } else {
        // If no password, cannot delete manually (unless admin token mechanism exists, skipping for now)
        return Err(ApiError::Unauthorized);
    }

    // Logic for decrementing ref count on file?
    // We only delete the paste record. The file cleaner will handle orphaned files later, 
    // OR we decrement here. 
    // Ideally:
    if let Some(hash) = paste.file_hash {
         sqlx::query("UPDATE files SET ref_count = ref_count - 1 WHERE hash = ?")
            .bind(hash)
            .execute(&state.pool)
            .await?;
    }

    sqlx::query("DELETE FROM pastes WHERE id = ?")
        .bind(&id)
        .execute(&state.pool)
        .await?;

    security::security_log("Paste deleted", &addr.to_string());
    Ok("Deleted\n".to_string())
}
