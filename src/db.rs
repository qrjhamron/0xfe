use sqlx::{
    Pool, Sqlite,
};
use crate::config::get_config;
use chrono::{DateTime, Utc};

pub type DbPool = Pool<Sqlite>;

pub async fn init_db() -> DbPool {
    let config = get_config();
    println!("DEBUG: DB Connecting to {}", config.database_url);

    let pool = Pool::<Sqlite>::connect(&config.database_url)
        .await
        .expect("Failed to connect to database");
    
    println!("DEBUG: DB Connected");

    sqlx::migrate!()
        .run(&pool)
        .await
        .expect("Failed to run migrations");
    
    println!("DEBUG: DB Migrated");

    pool
}

pub async fn check_db_health(pool: &DbPool) -> Result<(), sqlx::Error> {
    sqlx::query("SELECT 1").execute(pool).await.map(|_| ())
}

#[derive(Debug, sqlx::FromRow)]
pub struct Paste {
    pub id: String,
    pub content: Option<Vec<u8>>, // Legacy/Small pastes
    pub file_hash: Option<String>, // Deduplicated storage
    pub password_hash: Option<String>,
    pub created_at: DateTime<Utc>,
    pub expiry: Option<DateTime<Utc>>,
    pub burn_after_read: bool,
    pub parent_id: Option<String>,
    pub mime_type: Option<String>,
    pub filename: Option<String>,
}

#[derive(Debug, sqlx::FromRow)]
pub struct FileRecord {
    pub hash: String,
    pub path: String,
    pub size: i64,
    pub ref_count: i64,
    pub mime_type: Option<String>,
    pub created_at: DateTime<Utc>,
}
