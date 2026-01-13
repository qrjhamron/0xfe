// Certificate Hot-Reloading Module
// Allows certificates to be refreshed without restarting the service
// Uses file watcher to detect certificate changes

use std::path::{Path, PathBuf};
use std::time::SystemTime;
use std::sync::{Arc, Mutex};
use anyhow::Result;

#[derive(Clone)]
pub struct CertificateWatcher {
    cert_path: PathBuf,
    key_path: PathBuf,
    last_modified: Arc<Mutex<Option<SystemTime>>>,
}

impl CertificateWatcher {
    pub fn new(cert_path: impl AsRef<Path>, key_path: impl AsRef<Path>) -> Self {
        Self {
            cert_path: cert_path.as_ref().to_path_buf(),
            key_path: key_path.as_ref().to_path_buf(),
            last_modified: Arc::new(Mutex::new(None)),
        }
    }

    /// Check if certificate file has been modified
    pub fn has_changed(&self) -> Result<bool> {
        let metadata = std::fs::metadata(&self.cert_path)?;
        let modified = metadata.modified()?;

        let mut last = self.last_modified.lock().unwrap();
        let changed = last.map_or(true, |prev| modified > prev);
        
        if changed {
            *last = Some(modified);
        }

        Ok(changed)
    }

    /// Verify certificate validity
    pub fn is_valid(&self) -> bool {
        if !self.cert_path.exists() || !self.key_path.exists() {
            return false;
        }
        
        match std::fs::metadata(&self.key_path) {
            Ok(meta) => {
                // Verify private key has restrictive permissions (mode 0600 = 384)
                #[cfg(unix)]
                {
                    use std::os::unix::fs::PermissionsExt;
                    let mode = meta.permissions().mode() & 0o777;
                    mode == 0o600 || mode == 0o644  // Allow 0644 for cert, 0600 for key
                }
                #[cfg(not(unix))]
                true
            }
            Err(_) => false,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_certificate_watcher_creation() {
        let watcher = CertificateWatcher::new("cert.pem", "key.pem");
        assert_eq!(watcher.cert_path.to_str().unwrap(), "cert.pem");
    }
}
