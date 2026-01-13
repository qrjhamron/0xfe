use metrics::{describe_counter, describe_histogram};
use metrics_exporter_prometheus::{PrometheusBuilder, PrometheusHandle};
use sysinfo::System; 
use std::time::Duration;
use tokio::time;
use std::sync::OnceLock;

pub const HTTP_REQUESTS_TOTAL: &str = "http_requests_total";
pub const HTTP_REQUEST_DURATION_SECONDS: &str = "http_request_duration_seconds";
pub const AUTH_FAILURES_TOTAL: &str = "auth_failures_total";
pub const RATE_LIMIT_HITS_TOTAL: &str = "rate_limit_hits_total";
pub const DB_QUERY_DURATION_SECONDS: &str = "db_query_duration_seconds";
pub const SYSTEM_MEMORY_USAGE_BYTES: &str = "system_memory_usage_bytes";
pub const SYSTEM_CPU_USAGE_PERCENT: &str = "system_cpu_usage_percent";
pub const ACTIVE_CONNECTIONS: &str = "active_connections";

static PROMETHEUS_HANDLE: OnceLock<PrometheusHandle> = OnceLock::new();

pub fn init_metrics() -> PrometheusHandle {
    let builder = PrometheusBuilder::new();
    let handle = builder
        .install_recorder()
        .expect("failed to install Prometheus recorder");

    // Register metrics
    describe_counter!(HTTP_REQUESTS_TOTAL, "Total number of HTTP requests");
    describe_histogram!(HTTP_REQUEST_DURATION_SECONDS, "HTTP request latency in seconds");
    describe_counter!(AUTH_FAILURES_TOTAL, "Total number of authentication failures");
    describe_counter!(RATE_LIMIT_HITS_TOTAL, "Total number of rate limit hits");
    describe_histogram!(DB_QUERY_DURATION_SECONDS, "Database query duration in seconds");
    
    PROMETHEUS_HANDLE.set(handle.clone()).expect("Metrics already initialized");
    handle
}

pub fn get_handle() -> PrometheusHandle {
    PROMETHEUS_HANDLE.get().expect("Metrics not initialized").clone()
}

pub async fn run_system_monitor() {
    let mut sys = System::new_all();
    let mut interval = time::interval(Duration::from_secs(15));

    loop {
        interval.tick().await;
        sys.refresh_memory();
        sys.refresh_cpu_all();

        let memory_used = sys.used_memory();
        // Fallback to absolute manual update if macro fails
        metrics::gauge!("system_memory_usage_bytes").set(memory_used as f64);

        let cpu_usage = sys.global_cpu_usage();
        metrics::gauge!("system_cpu_usage_percent").set(cpu_usage as f64);
    }
}
