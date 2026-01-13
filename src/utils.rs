use rand::{Rng, rng};
use rand::distr::Alphanumeric;
use sha2::{Sha256, Digest};
use std::net::IpAddr;

pub fn generate_id() -> String {
    let mut rng = rng();
    (0..6)
        .map(|_| rng.sample(Alphanumeric))
        .map(char::from)
        .collect()
}

const CHARSET: &[u8] = b"23456789abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ";

pub fn generate_clean_id() -> String {
    let mut rng = rng();
    (0..6)
        .map(|_| {
            let idx = rng.random_range(0..CHARSET.len());
            CHARSET[idx] as char
        })
        .collect()
}

pub fn detect_mime(content: &[u8], filename: Option<&str>) -> String {
    if let Some(name) = filename {
        let guess = mime_guess::from_path(name);
        if let Some(mime) = guess.first() {
            return mime.to_string();
        }
    }
    
    if let Some(kind) = infer::get(content) {
        return kind.mime_type().to_string();
    }

    if std::str::from_utf8(content).is_ok() {
        "text/plain".to_string()
    } else {
        "application/octet-stream".to_string()
    }
}

/// Hash IP address for rate limiting without storing actual IPs
/// Consistent hashing ensures same IP always produces same hash
pub fn hash_ip(ip: IpAddr) -> String {
    let mut hasher = Sha256::new();
    hasher.update(ip.to_string().as_bytes());
    format!("{:x}", hasher.finalize())
}

/// Compute BLAKE3 hash of content for integrity verification
pub fn compute_content_hash(data: &[u8]) -> String {
    use sha2::Sha256;
    let mut hasher = Sha256::new();
    hasher.update(data);
    hex::encode(hasher.finalize())
}