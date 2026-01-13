use serde::Deserialize;
use std::fs;
use std::sync::OnceLock;

#[derive(Deserialize, Debug, Clone)]
pub struct Config {
    #[serde(default = "default_port")]
    pub port: u16,
    #[serde(default = "default_database_url")]
    pub database_url: String,
    #[serde(default = "default_max_upload_size")]
    pub max_upload_size: usize,
    #[serde(default = "default_base_url")]
    pub base_url: String,
    #[serde(default = "default_cert_path")]
    pub cert_path: String,
    #[serde(default = "default_key_path")]
    pub key_path: String,
    #[serde(default = "default_security_log_path")]
    pub security_log_path: String,
}

fn default_port() -> u16 {
    3000
}

fn default_database_url() -> String {
    "sqlite://data.db".to_string()
}

fn default_max_upload_size() -> usize {
    10 * 1024 * 1024 // 10MB
}

fn default_base_url() -> String {
    "https://localhost:3000".to_string()
}

fn default_cert_path() -> String {
    "cert.pem".to_string()
}

fn default_key_path() -> String {
    "key.pem".to_string()
}

fn default_security_log_path() -> String {
    "security.log".to_string()
}

pub static CONFIG: OnceLock<Config> = OnceLock::new();

pub fn init_config() {
    let config_content = fs::read_to_string("config.toml").unwrap_or_else(|_| "".to_string());
    let config: Config = toml::from_str(&config_content).unwrap_or_else(|_| Config {
        port: default_port(),
        database_url: default_database_url(),
        max_upload_size: default_max_upload_size(),
        base_url: default_base_url(),
        cert_path: default_cert_path(),
        key_path: default_key_path(),
        security_log_path: default_security_log_path(),
    });
    
    // Override with environment variables if present (basic override)
    let config = Config {
        port: std::env::var("PORT").ok().and_then(|p| p.parse().ok()).unwrap_or(config.port),
        database_url: std::env::var("DATABASE_URL").ok().unwrap_or(config.database_url),
        ..config
    };

    CONFIG.set(config).expect("Config already initialized");
}

pub fn get_config() -> &'static Config {
    CONFIG.get().expect("Config not initialized")
}