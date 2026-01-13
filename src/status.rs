use axum::{
    extract::State,
    response::{Html, IntoResponse},
};
use sysinfo::{System, Networks, Disks};
use std::sync::{Arc, Mutex};
use crate::handlers::AppState;
use lazy_static::lazy_static;

// We need a persistent System object to calculate CPU usage correctly over time.
// Since axum handlers are async and stateless, we wrap it in a Mutex.
lazy_static! {
    static ref SYSTEM: Arc<Mutex<System>> = Arc::new(Mutex::new(System::new_all()));
    static ref NETWORKS: Arc<Mutex<Networks>> = Arc::new(Mutex::new(Networks::new_with_refreshed_list()));
}

pub async fn get_status_html(State(state): State<AppState>) -> impl IntoResponse {
    let mut sys = SYSTEM.lock().unwrap();
    let mut nets = NETWORKS.lock().unwrap();
    
    // Refresh components
    sys.refresh_cpu_all();
    sys.refresh_memory();
    nets.refresh(true);
    
    let cpu_count = sys.cpus().len();
    let cpu_usage: f32 = sys.global_cpu_usage();
    let load_avg = System::load_average();
    
    let total_mem = sys.total_memory();
    let used_mem = sys.used_memory();
    let total_swap = sys.total_swap();
    let used_swap = sys.used_swap();
    
    let uptime = System::uptime();
    
    // Simple Disk I/O (Snapshot)
    // sysinfo provides total read/write, not rate. We'd need to track diffs for rate.
    // For now, we show total stats or storage used.
    
    let disks = Disks::new_with_refreshed_list();
    let mut total_space = 0;
    let mut available_space = 0;
    for disk in &disks {
        total_space += disk.total_space();
        available_space += disk.available_space();
    }
    
    // Get DB Stats
    let db_conns = state.pool.size();
    let db_idle = state.pool.num_idle();
    
    let html = format!(r#"<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="2">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>System Status | 0xfe</title>
<style>
:root{{--bg:#101010;--fg:#c0c0c0;--accent:#00bc8c;--warn:#d08770;--crit:#bf616a}}
body{{background:var(--bg);color:var(--fg);font-family:monospace;margin:0;padding:1rem;max-width:800px;margin:auto}}
h1{{border-bottom:1px solid #333;padding-bottom:0.5rem}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem}}
.card{{background:#1a1a1a;padding:1rem;border:1px solid #333;border-radius:4px}}
.card h3{{margin-top:0;font-size:0.9rem;text-transform:uppercase;color:#888}}
.val{{font-size:1.5rem;font-weight:bold;color:var(--accent)}}
.unit{{font-size:0.8rem;color:#666}}
.bar{{background:#333;height:4px;margin-top:0.5rem;width:100%}}
.fill{{height:100%;background:var(--accent);transition:width 0.5s}}
table{{width:100%;border-collapse:collapse;margin-top:1rem}}
td,th{{text-align:left;padding:0.5rem;border-bottom:1px solid #333}}
</style>
</head>
<body>
<h1>SYSTEM STATUS</h1>

<div class="grid">
    <div class="card">
        <h3>CPU Load ({cpu_count} cores)</h3>
        <div class="val">{cpu_usage:.1}<span class="unit">%</span></div>
        <div class="bar"><div class="fill" style="width:{cpu_usage}%"></div></div>
        <div class="unit">Load: {l1:.2} / {l5:.2} / {l15:.2}</div>
    </div>
    
    <div class="card">
        <h3>Memory</h3>
        <div class="val">{mem_pct:.1}<span class="unit">%</span></div>
        <div class="bar"><div class="fill" style="width:{mem_pct}%"></div></div>
        <div class="unit">{used} / {total} GB (Swap: {swap_used}/{swap_total} GB)</div>
    </div>

    <div class="card">
        <h3>Storage</h3>
        <div class="val">{disk_pct:.1}<span class="unit">%</span></div>
        <div class="bar"><div class="fill" style="width:{disk_pct}%"></div></div>
        <div class="unit">{disk_avail} GB Free / {disk_total} GB Total</div>
    </div>

    <div class="card">
        <h3>Uptime</h3>
        <div class="val">{uptime_h}<span class="unit">h</span> {uptime_m}<span class="unit">m</span></div>
        <div class="unit">Since Boot</div>
    </div>
    
     <div class="card">
        <h3>Database</h3>
        <div class="val">{db_conns}<span class="unit">conns</span></div>
        <div class="unit">{db_idle} Idle</div>
    </div>
</div>

<h2>Active Processes (Top 5 CPU)</h2>
<table>
<thead><tr><th>PID</th><th>Name</th><th>CPU%</th><th>Mem</th></tr></thead>
<tbody>
{proc_rows}
</tbody>
</table>

<footer>
<p>Auto-refreshing every 2s. Server Time: {time}</p>
</footer>
</body>
</html>"#, 
    cpu_count=cpu_count,
    cpu_usage=cpu_usage,
    l1=load_avg.one, l5=load_avg.five, l15=load_avg.fifteen,
    mem_pct=(used_mem as f64 / total_mem as f64) * 100.0,
    used=bytes_to_gb(used_mem), total=bytes_to_gb(total_mem),
    swap_used=bytes_to_gb(used_swap), swap_total=bytes_to_gb(total_swap),
    disk_pct=(1.0 - (available_space as f64 / total_space as f64)) * 100.0,
    disk_avail=bytes_to_gb(available_space), disk_total=bytes_to_gb(total_space),
    uptime_h=uptime / 3600, uptime_m=(uptime % 3600) / 60,
    db_conns=db_conns, db_idle=db_idle,
    proc_rows=get_top_processes_html(&mut sys),
    time=chrono::Utc::now().to_rfc3339(),
    );

    Html(html)
}

fn bytes_to_gb(bytes: u64) -> String {
    format!("{:.1}", bytes as f64 / 1024.0 / 1024.0 / 1024.0)
}

fn get_top_processes_html(sys: &mut System) -> String {
    let mut procs: Vec<_> = sys.processes().values().collect();
    procs.sort_by(|a, b| b.cpu_usage().partial_cmp(&a.cpu_usage()).unwrap_or(std::cmp::Ordering::Equal));
    
    procs.iter().take(5).map(|p| {
        format!("<tr><td>{}</td><td>{}</td><td>{:.1}%</td><td>{:.1} MB</td></tr>", 
            p.pid(), 
            p.name().to_string_lossy(), 
            p.cpu_usage(), 
            p.memory() as f64 / 1024.0 / 1024.0
        )
    }).collect()
}
