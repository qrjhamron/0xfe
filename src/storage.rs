use std::path::PathBuf;
use tokio::fs::{self, File};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use sha2::{Sha256, Digest};
use crate::db::{DbPool, FileRecord};
use chrono::Utc;
use anyhow::{Result, anyhow};
use tracing::info;
use bytes::Bytes;
use futures::StreamExt;

pub struct StorageManager {
    pool: DbPool,
    storage_dir: PathBuf,
}

impl StorageManager {
    pub fn new(pool: DbPool) -> Self {
        let storage_dir = PathBuf::from("storage");
        if !storage_dir.exists() {
            std::fs::create_dir_all(&storage_dir).expect("Failed to create storage dir");
        }
        Self { pool, storage_dir }
    }

    pub async fn store_stream<S, E>(&self, mut stream: S) -> Result<(String, i64, String)> 
    where
        S: futures::Stream<Item = Result<Bytes, E>> + Unpin,
        E: std::error::Error + Send + Sync + 'static,
    {
        let temp_id = uuid::Uuid::new_v4();
        let temp_path = self.storage_dir.join(format!("temp_{}", temp_id));
        let mut file = File::create(&temp_path).await?;
        let mut hasher = Sha256::new();
        let mut size: i64 = 0;

        while let Some(chunk_res) = stream.next().await {
            let chunk = chunk_res.map_err(|e| anyhow!("Stream error: {}", e))?;
            size += chunk.len() as i64;
            
            if size > 500 * 1024 * 1024 {
                drop(file); // Close handle
                let _ = fs::remove_file(&temp_path).await;
                return Err(anyhow!("File too large (>500MB)"));
            }

            hasher.update(&chunk);
            file.write_all(&chunk).await?;
        }
        
        file.flush().await?;
        let hash = hex::encode(hasher.finalize());

        let existing: Option<FileRecord> = sqlx::query_as("SELECT * FROM files WHERE hash = ?")
            .bind(&hash)
            .fetch_optional(&self.pool)
            .await?;

        if let Some(_) = existing {
            info!("Deduplicated file: {}", hash);
            sqlx::query("UPDATE files SET ref_count = ref_count + 1 WHERE hash = ?")
                .bind(&hash)
                .execute(&self.pool)
                .await?;
            fs::remove_file(temp_path).await?;
            let record: FileRecord = sqlx::query_as("SELECT * FROM files WHERE hash = ?")
                 .bind(&hash)
                 .fetch_one(&self.pool)
                 .await?;
            return Ok((hash, size, record.mime_type.unwrap_or_default())); 
        }

        let perm_path = self.storage_dir.join(&hash);
        fs::rename(&temp_path, &perm_path).await?;

        let mut f = File::open(&perm_path).await?;
        let mut header = [0u8; 8192];
        let n = f.read(&mut header).await?;
        let mime = infer::get(&header[..n]).map(|t| t.mime_type().to_string()).unwrap_or("application/octet-stream".to_string());

        sqlx::query(
            "INSERT INTO files (hash, path, size, ref_count, mime_type, created_at) VALUES (?, ?, ?, 1, ?, ?)"
        )
        .bind(&hash)
        .bind(perm_path.to_string_lossy().to_string())
        .bind(size)
        .bind(&mime)
        .bind(Utc::now())
        .execute(&self.pool)
        .await?;

        Ok((hash, size, mime))
    }

    pub async fn get_file_path(&self, hash: &str) -> Result<PathBuf> {
         let record: FileRecord = sqlx::query_as("SELECT * FROM files WHERE hash = ?")
            .bind(hash)
            .fetch_one(&self.pool)
            .await?;
        Ok(PathBuf::from(record.path))
    }
}
