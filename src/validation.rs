// Input Validation and Sanitization Module
// Strict validation at the boundary to prevent injection attacks

use regex::Regex;
use lazy_static::lazy_static;

lazy_static! {
    static ref SAFE_FILENAME: Regex = Regex::new(r"^[a-zA-Z0-9._\-]{1,255}$").unwrap();
    static ref SAFE_ID: Regex = Regex::new(r"^[a-zA-Z0-9_\-]{1,32}$").unwrap();
    static ref SAFE_MIME: Regex = Regex::new(r"^[a-z0-9]+/[a-z0-9\.\+\-]+$").unwrap();
}

pub enum ValidationError {
    InvalidFilename(String),
    FilenameTooLong,
    InvalidId(String),
    FileSizeExceeded,
    InvalidMimeType(String),
}

impl std::fmt::Display for ValidationError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::InvalidFilename(name) => write!(f, "Invalid filename: {}", name),
            Self::FilenameTooLong => write!(f, "Filename exceeds 255 bytes"),
            Self::InvalidId(id) => write!(f, "Invalid paste ID: {}", id),
            Self::FileSizeExceeded => write!(f, "File size exceeds limit"),
            Self::InvalidMimeType(m) => write!(f, "Invalid MIME type: {}", m),
        }
    }
}

/// Validate filename: alphanumeric, dash, underscore, dot only
pub fn validate_filename(filename: &str) -> Result<(), ValidationError> {
    if filename.is_empty() {
        return Err(ValidationError::InvalidFilename("empty".to_string()));
    }
    
    if filename.len() > 255 {
        return Err(ValidationError::FilenameTooLong);
    }
    
    if !SAFE_FILENAME.is_match(filename) {
        return Err(ValidationError::InvalidFilename(filename.to_string()));
    }
    
    // Prevent path traversal
    if filename.contains("..") || filename.contains("/") || filename.contains("\\") {
        return Err(ValidationError::InvalidFilename(filename.to_string()));
    }
    
    Ok(())
}

/// Validate paste ID format
pub fn validate_id(id: &str) -> Result<(), ValidationError> {
    if !SAFE_ID.is_match(id) {
        return Err(ValidationError::InvalidId(id.to_string()));
    }
    Ok(())
}

/// Validate MIME type format
pub fn validate_mime_type(mime: &str) -> Result<(), ValidationError> {
    if !SAFE_MIME.is_match(mime) {
        return Err(ValidationError::InvalidMimeType(mime.to_string()));
    }
    
    // Prevent overly long MIME types
    if mime.len() > 100 {
        return Err(ValidationError::InvalidMimeType(mime.to_string()));
    }
    
    Ok(())
}

/// Validate file size against limit
pub fn validate_file_size(size: i64, max_bytes: usize) -> Result<(), ValidationError> {
    if size as usize > max_bytes {
        return Err(ValidationError::FileSizeExceeded);
    }
    Ok(())
}

/// Sanitize text for HTML display (context-aware escaping)
pub fn sanitize_html(text: &str) -> String {
    html_escape::encode_text(text).to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_valid_filename() {
        assert!(validate_filename("my-file.txt").is_ok());
        assert!(validate_filename("test_file_2024.zip").is_ok());
    }

    #[test]
    fn test_invalid_filename() {
        assert!(validate_filename("../etc/passwd").is_err());
        assert!(validate_filename("file..name.txt").is_err());
        assert!(validate_filename("file\nname").is_err());
        assert!(validate_filename("").is_err());
    }

    #[test]
    fn test_valid_id() {
        assert!(validate_id("abc123").is_ok());
        assert!(validate_id("test_id_9").is_ok());
    }

    #[test]
    fn test_invalid_id() {
        assert!(validate_id("../admin").is_err());
        assert!(validate_id("test id").is_err());
    }

    #[test]
    fn test_mime_validation() {
        assert!(validate_mime_type("text/plain").is_ok());
        assert!(validate_mime_type("application/json").is_ok());
        assert!(validate_mime_type("image/jpeg").is_ok());
    }

    #[test]
    fn test_mime_injection() {
        assert!(validate_mime_type("text/plain\nX-Injection: bad").is_err());
    }

    #[test]
    fn test_file_size_validation() {
        let limit = 10 * 1024 * 1024; // 10MB
        assert!(validate_file_size(5 * 1024 * 1024 as i64, limit).is_ok());
        assert!(validate_file_size(15 * 1024 * 1024 as i64, limit).is_err());
    }
}
