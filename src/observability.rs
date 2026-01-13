use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt, Registry, EnvFilter};
use tracing_appender::non_blocking::WorkerGuard;

pub fn init_observability() -> Option<WorkerGuard> {
    // Zero Local Logs Mandate: No file appender.
    // We stream JSON to stdout. Systemd Journal handles rotation/storage.

    // Stdout Layer - JSON Structured Logging
    let stdout_layer = tracing_subscriber::fmt::layer()
        .json()
        .flatten_event(true)
        .with_span_list(false) // Reduce noise
        .with_target(false)
        .with_current_span(false)
        .with_writer(std::io::stdout);

    // Filter - Allow info by default for app, restrict others
    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| "pastebin_cli=info,security=info,tower_http=info,axum=warn,sqlx=warn,hyper=warn".into());

    Registry::default()
        .with(filter)
        .with(stdout_layer)
        .init();

    // In a full OTLP setup, we would return the OTLP guard here.
    // For now, we return None as stdout doesn't need a guard.
    None
}