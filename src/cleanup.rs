use crate::db::DbPool;
use tracing::{info, error};
use std::time::Duration;
use tokio::time;
use chrono::Utc;

pub async fn run_cleanup_task(pool: DbPool) {
    info!("Starting cleanup task");
    let mut interval = time::interval(Duration::from_secs(3600)); // Every hour

    loop {
        interval.tick().await;
        info!("Running hourly cleanup");

        // 1. Delete expired pastes
        let res = sqlx::query("DELETE FROM pastes WHERE expiry < ?")
            .bind(Utc::now())
            .execute(&pool)
            .await;

        match res {
            Ok(r) => info!("Cleaned up {} expired pastes", r.rows_affected()),
            Err(e) => error!("Failed to clean expired pastes: {}", e),
        }

        // 2. Identify and delete orphaned files (ref_count <= 0)
        // First, ensure ref_counts are consistent? (Expensive)
        // Instead, we trust the logic: paste delete -> decrement.
        
        let rows = sqlx::query_as::<_, (String, String)>("SELECT hash, path FROM files WHERE ref_count <= 0")
            .fetch_all(&pool)
            .await;

        match rows {
            Ok(files) => {
                for (hash, path) in files {
                    if let Err(e) = tokio::fs::remove_file(&path).await {
                         error!("Failed to remove file {}: {}", path, e);
                         // Don't delete DB record if file delete failed? Or force?
                         // Force delete from DB to avoid loop
                    }
                    let _ = sqlx::query("DELETE FROM files WHERE hash = ?")
                        .bind(&hash)
                        .execute(&pool)
                        .await;
                    info!("Removed orphaned file: {}", hash);
                }
            },
            Err(e) => error!("Failed to fetch orphaned files: {}", e),
        }
    }
}
