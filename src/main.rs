use axum::{
    routing::{get, post},
    Router,
    extract::DefaultBodyLimit,
    middleware,
};
use std::net::SocketAddr;
use tower_http::{
    trace::TraceLayer,
    limit::RequestBodyLimitLayer,
    cors::CorsLayer,
};
use tower::ServiceBuilder;
use axum_server::tls_rustls::RustlsConfig;
use std::path::PathBuf;
use std::future::ready;
use std::sync::Arc;

use pastebin_cli::{config, db, handlers, cleanup, security, app_metrics, observability, storage, status};

#[tokio::main]
async fn main() {
    println!("DEBUG: Starting...");
    if let Err(e) = rustls::crypto::ring::default_provider().install_default() {
         println!("DEBUG: Crypto install failed (might be already installed): {:?}", e);
    } else {
         println!("DEBUG: Crypto installed");
    }
    
    config::init_config();
    println!("DEBUG: Config initialized");
    let config = config::get_config();
    println!("DEBUG: Config loaded");

    let _guard = observability::init_observability();
    println!("DEBUG: Observability initialized");

    let prometheus_handle = app_metrics::init_metrics();
    println!("DEBUG: Metrics initialized");
    
    tokio::spawn(app_metrics::run_system_monitor());

    security::init_security_state();
    println!("DEBUG: Security initialized");

    let pool = db::init_db().await;
    println!("DEBUG: DB initialized");
    let storage = Arc::new(storage::StorageManager::new(pool.clone()));

    let cleanup_pool = pool.clone();
    tokio::spawn(async move {
        cleanup::run_cleanup_task(cleanup_pool).await;
    });

    let state = handlers::AppState {
        pool: pool.clone(),
        storage,
    };


    let app = Router::new()
        .route("/", get(handlers::index).post(handlers::upload_multipart))
        .route("/raw", post(handlers::upload_raw))
        .route("/health", get(handlers::health_check))
        .route("/metrics", get(move || ready(prometheus_handle.render())))
        .route("/status", get(status::get_status_html))
        .route("/{id}", get(handlers::get_paste).delete(handlers::delete_paste))
        // .route("/{id}/raw", get(handlers::get_raw_paste)) // Merged into get_paste
        .layer(
            ServiceBuilder::new()
                .layer(middleware::from_fn(security::rate_limit_middleware))
                .layer(middleware::from_fn(security::security_headers))
                .layer(middleware::from_fn(track_metrics))
                .layer(DefaultBodyLimit::disable())
                .layer(RequestBodyLimitLayer::new(config.max_upload_size))
                .layer(TraceLayer::new_for_http())
                .layer(CorsLayer::permissive())
        )
        .with_state(state);

    let tls_config = RustlsConfig::from_pem_file(
        PathBuf::from(&config.cert_path),
        PathBuf::from(&config.key_path),
    )
    .await;

    let addr = SocketAddr::from(([0, 0, 0, 0], config.port));
    println!("DEBUG: Listening on {}", addr);
    tracing::info!("listening on {}", addr);

    match tls_config {
        Ok(tls) => {
            println!("DEBUG: Starting TLS");
            tracing::info!("Starting with TLS enabled");
            axum_server::bind_rustls(addr, tls)
                .serve(app.into_make_service_with_connect_info::<SocketAddr>())
                .await
                .unwrap();
        },
        Err(e) => {
            println!("DEBUG: Starting HTTP (TLS Error: {})", e);
            tracing::warn!("TLS certificate not found or invalid ({}), falling back to HTTP.", e);
            axum_server::bind(addr)
                .serve(app.into_make_service_with_connect_info::<SocketAddr>())
                .await
                .unwrap();
        }
    }
}

async fn track_metrics(req: axum::extract::Request, next: axum::middleware::Next) -> axum::response::Response {
    let start = std::time::Instant::now();
    let response = next.run(req).await;
    let latency = start.elapsed().as_secs_f64();
    let status = response.status().as_u16().to_string();

    metrics::counter!(app_metrics::HTTP_REQUESTS_TOTAL, "status" => status.clone()).increment(1);
    metrics::histogram!(app_metrics::HTTP_REQUEST_DURATION_SECONDS, "status" => status).record(latency);

    response
}