// Prevents additional console window on Windows in release.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Mutex;

#[cfg(not(dev))]
use std::net::TcpListener;
#[cfg(not(dev))]
use std::time::{Duration, Instant};
use tauri::{
    menu::{MenuBuilder, MenuItemBuilder, PredefinedMenuItem, SubmenuBuilder},
    AppHandle, Manager, RunEvent, WindowEvent,
};
#[cfg(not(dev))]
use tauri_plugin_shell::ShellExt;

/// Open a startup log file for diagnosing sidecar launch issues.
/// Writes to ``%LOCALAPPDATA%/Clarity/clarity-startup.log`` (Windows)
/// or ``~/.clarity/clarity-startup.log`` (other platforms).
#[cfg(not(dev))]
fn open_startup_log() -> Option<std::fs::File> {
    use std::fs::OpenOptions;
    let log_dir = if cfg!(target_os = "windows") {
        std::env::var("LOCALAPPDATA")
            .ok()
            .map(|d| std::path::PathBuf::from(d).join("Clarity"))
    } else {
        dirs::home_dir().map(|h| h.join(".clarity"))
    };
    let log_dir = log_dir?;
    std::fs::create_dir_all(&log_dir).ok()?;
    let path = log_dir.join("clarity-startup.log");
    OpenOptions::new().create(true).append(true).open(path).ok()
}

/// Maximum time to wait for the server to become ready.
#[cfg(not(dev))]
const SERVER_TIMEOUT: Duration = Duration::from_secs(30);

/// Interval between health-check polls.
#[cfg(not(dev))]
const POLL_INTERVAL: Duration = Duration::from_millis(250);

/// Maximum number of projects to show in Open Recent.
const MAX_RECENT: usize = 10;

/// Find an available TCP port by binding to port 0.
#[cfg(not(dev))]
fn find_free_port() -> u16 {
    let listener = TcpListener::bind("127.0.0.1:0").expect("failed to bind to a free port");
    listener.local_addr().unwrap().port()
}

/// State holding the sidecar child process so we can kill it on exit.
struct SidecarState(Mutex<Option<tauri_plugin_shell::process::CommandChild>>);

// ---------------------------------------------------------------------------
// Project registry reading (for Open Recent)
// ---------------------------------------------------------------------------

/// Wrapper for the projects.json file format.
///
/// The Python ``ProjectRegistry`` writes ``{"projects": [...], "active": "..."}``
/// (with a legacy fallback for bare arrays).
#[derive(serde::Deserialize)]
struct ProjectsFile {
    #[serde(default)]
    projects: Vec<ProjectEntry>,
}

/// Minimal project entry — we only need name, path, id, and last_opened.
#[derive(serde::Deserialize, Clone)]
#[allow(dead_code)]
struct ProjectEntry {
    name: String,
    path: String,
    id: String,
    #[serde(default)]
    last_opened: f64,
}

/// Locate the projects.json file.
///
/// Must match the Python resolution in ``clarity_agent.app_paths.clarity_data_dir()``:
/// 1. ``CLARITY_DATA_DIR`` env var
/// 2. macOS: ``~/Library/Application Support/Clarity/``
/// 3. Windows: ``%LOCALAPPDATA%\Clarity\data\``
/// 4. Fallback: ``~/.clarity/``
fn projects_json_path() -> Option<std::path::PathBuf> {
    // 1. CLARITY_DATA_DIR env var (set by desktop packaging or dev override).
    if let Ok(dir) = std::env::var("CLARITY_DATA_DIR") {
        return Some(std::path::PathBuf::from(dir).join("projects.json"));
    }

    // 2. macOS: ~/Library/Application Support/Clarity/
    #[cfg(target_os = "macos")]
    {
        if let Some(home) = dirs::home_dir() {
            return Some(
                home.join("Library")
                    .join("Application Support")
                    .join("Clarity")
                    .join("projects.json"),
            );
        }
    }

    // 3. Windows: %LOCALAPPDATA%\Clarity\data\
    #[cfg(target_os = "windows")]
    {
        if let Ok(local) = std::env::var("LOCALAPPDATA") {
            let candidate = std::path::PathBuf::from(local).join("Clarity").join("data");
            if candidate.parent().map_or(false, |p| p.is_dir()) {
                return Some(candidate.join("projects.json"));
            }
        }
    }

    // 4. Fallback: ~/.clarity/projects.json
    dirs::home_dir().map(|h| h.join(".clarity").join("projects.json"))
}

/// Read and parse the project registry, sorted by last_opened descending.
///
/// Handles both the current wrapper format ``{"projects": [...]}`` and
/// the legacy bare-array format ``[...]``.
fn read_recent_projects() -> Vec<ProjectEntry> {
    let path = match projects_json_path() {
        Some(p) if p.exists() => p,
        _ => return Vec::new(),
    };
    let contents = match std::fs::read_to_string(&path) {
        Ok(c) => c,
        Err(_) => return Vec::new(),
    };
    // Try wrapper format first, then legacy bare array.
    let mut entries: Vec<ProjectEntry> =
        if let Ok(file) = serde_json::from_str::<ProjectsFile>(&contents) {
            file.projects
        } else if let Ok(arr) = serde_json::from_str::<Vec<ProjectEntry>>(&contents) {
            arr
        } else {
            return Vec::new();
        };
    entries.sort_by(|a, b| b.last_opened.partial_cmp(&a.last_opened).unwrap_or(std::cmp::Ordering::Equal));
    entries.truncate(MAX_RECENT);
    entries
}

// ---------------------------------------------------------------------------
// Menu construction
// ---------------------------------------------------------------------------

/// Menu item IDs (must be stable strings for event matching).
const ID_NEW_PROJECT: &str = "new-project";
const ID_OPEN_PROJECT: &str = "open-project";
const ID_PRINT: &str = "print";
const ID_EXPORT_PRINT: &str = "export-print";
const ID_CLEAR_RECENT: &str = "clear-recent";

/// Build (or rebuild) the full application menu.
fn build_menu(app: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    let h = app;

    // -- File menu --
    let new_project = MenuItemBuilder::with_id(ID_NEW_PROJECT, "New Project...")
        .accelerator("CmdOrCtrl+N")
        .build(h)?;
    let open_project = MenuItemBuilder::with_id(ID_OPEN_PROJECT, "Open Project...")
        .accelerator("CmdOrCtrl+O")
        .build(h)?;

    // Open Recent submenu
    let mut recent_sub = SubmenuBuilder::new(h, "Open Recent");
    let projects = read_recent_projects();
    for project in &projects {
        let item = MenuItemBuilder::with_id(
            format!("recent:{}", project.id),
            &project.name,
        )
        .build(h)?;
        recent_sub = recent_sub.item(&item);
    }
    if !projects.is_empty() {
        recent_sub = recent_sub.separator();
    }
    let clear_recent = MenuItemBuilder::with_id(ID_CLEAR_RECENT, "Clear Recent")
        .enabled(!projects.is_empty())
        .build(h)?;
    recent_sub = recent_sub.item(&clear_recent);
    let recent_menu = recent_sub.build()?;

    let print_item = MenuItemBuilder::with_id(ID_PRINT, "Print...")
        .accelerator("CmdOrCtrl+P")
        .build(h)?;
    let export_print = MenuItemBuilder::with_id(ID_EXPORT_PRINT, "Export & Print...")
        .accelerator("CmdOrCtrl+Shift+P")
        .enabled(false)
        .build(h)?;

    let close_window = PredefinedMenuItem::close_window(h, None)?;

    let file_menu = SubmenuBuilder::new(h, "File")
        .item(&new_project)
        .item(&open_project)
        .item(&recent_menu)
        .separator()
        .item(&print_item)
        .item(&export_print)
        .separator()
        .item(&close_window)
        .build()?;

    // -- Edit menu --
    let edit_menu = SubmenuBuilder::new(h, "Edit")
        .item(&PredefinedMenuItem::undo(h, None)?)
        .item(&PredefinedMenuItem::redo(h, None)?)
        .separator()
        .item(&PredefinedMenuItem::cut(h, None)?)
        .item(&PredefinedMenuItem::copy(h, None)?)
        .item(&PredefinedMenuItem::paste(h, None)?)
        .item(&PredefinedMenuItem::select_all(h, None)?)
        .build()?;

    // -- Assemble --
    #[cfg(target_os = "macos")]
    let app_menu = SubmenuBuilder::new(h, "Clarity")
        .item(&PredefinedMenuItem::about(h, None, None)?)
        .separator()
        .item(&PredefinedMenuItem::hide(h, None)?)
        .item(&PredefinedMenuItem::hide_others(h, None)?)
        .item(&PredefinedMenuItem::show_all(h, None)?)
        .separator()
        .item(&PredefinedMenuItem::quit(h, None)?)
        .build()?;

    #[cfg(target_os = "macos")]
    let menu = MenuBuilder::new(h)
        .item(&app_menu)
        .item(&file_menu)
        .item(&edit_menu)
        .build()?;

    #[cfg(not(target_os = "macos"))]
    let menu = MenuBuilder::new(h)
        .item(&file_menu)
        .item(&edit_menu)
        .build()?;

    app.set_menu(menu)?;
    Ok(())
}

// ---------------------------------------------------------------------------
// Tauri commands (callable from frontend JS)
// ---------------------------------------------------------------------------

/// Rebuild the Open Recent submenu. Called from the frontend after
/// projects are created, activated, or deleted.
#[tauri::command]
fn refresh_recent_menu(app: AppHandle) -> Result<(), String> {
    build_menu(&app).map_err(|e| e.to_string())
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;

    // Env var tests must run serially to avoid interference.
    static ENV_LOCK: Mutex<()> = Mutex::new(());

    #[test]
    fn projects_json_path_respects_clarity_data_dir() {
        let _guard = ENV_LOCK.lock().unwrap();
        let old = std::env::var("CLARITY_DATA_DIR").ok();
        std::env::set_var("CLARITY_DATA_DIR", "/tmp/test-clarity-data");
        let result = projects_json_path();
        // Restore.
        match old {
            Some(v) => std::env::set_var("CLARITY_DATA_DIR", v),
            None => std::env::remove_var("CLARITY_DATA_DIR"),
        }
        assert_eq!(
            result,
            Some(std::path::PathBuf::from("/tmp/test-clarity-data/projects.json")),
        );
    }

    #[test]
    fn projects_json_path_uses_platform_default() {
        let _guard = ENV_LOCK.lock().unwrap();
        let old = std::env::var("CLARITY_DATA_DIR").ok();
        std::env::remove_var("CLARITY_DATA_DIR");
        let result = projects_json_path();
        // Restore.
        if let Some(v) = old {
            std::env::set_var("CLARITY_DATA_DIR", v);
        }
        let home = dirs::home_dir().unwrap();
        #[cfg(target_os = "macos")]
        let expected = home
            .join("Library")
            .join("Application Support")
            .join("Clarity")
            .join("projects.json");
        #[cfg(not(target_os = "macos"))]
        let expected = home.join(".clarity").join("projects.json");
        assert_eq!(result, Some(expected));
    }

    #[test]
    fn read_recent_projects_parses_wrapper_format() {
        let _guard = ENV_LOCK.lock().unwrap();
        let dir = std::env::temp_dir().join("clarity-test-wrapper");
        std::fs::create_dir_all(&dir).unwrap();
        let file = dir.join("projects.json");
        std::fs::write(
            &file,
            r#"{
                "projects": [
                    {"name": "alpha", "path": "/a", "id": "aaa", "last_opened": 200.0},
                    {"name": "beta", "path": "/b", "id": "bbb", "last_opened": 100.0}
                ],
                "active": "alpha"
            }"#,
        )
        .unwrap();

        let old = std::env::var("CLARITY_DATA_DIR").ok();
        std::env::set_var("CLARITY_DATA_DIR", dir.to_str().unwrap());
        let entries = read_recent_projects();
        match old {
            Some(v) => std::env::set_var("CLARITY_DATA_DIR", v),
            None => std::env::remove_var("CLARITY_DATA_DIR"),
        }
        std::fs::remove_dir_all(&dir).ok();

        assert_eq!(entries.len(), 2);
        // Should be sorted by last_opened descending.
        assert_eq!(entries[0].name, "alpha");
        assert_eq!(entries[1].name, "beta");
    }

    #[test]
    fn read_recent_projects_parses_legacy_array_format() {
        let _guard = ENV_LOCK.lock().unwrap();
        let dir = std::env::temp_dir().join("clarity-test-legacy");
        std::fs::create_dir_all(&dir).unwrap();
        let file = dir.join("projects.json");
        std::fs::write(
            &file,
            r#"[
                {"name": "gamma", "path": "/g", "id": "ggg", "last_opened": 50.0}
            ]"#,
        )
        .unwrap();

        let old = std::env::var("CLARITY_DATA_DIR").ok();
        std::env::set_var("CLARITY_DATA_DIR", dir.to_str().unwrap());
        let entries = read_recent_projects();
        match old {
            Some(v) => std::env::set_var("CLARITY_DATA_DIR", v),
            None => std::env::remove_var("CLARITY_DATA_DIR"),
        }
        std::fs::remove_dir_all(&dir).ok();

        assert_eq!(entries.len(), 1);
        assert_eq!(entries[0].name, "gamma");
    }
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .invoke_handler(tauri::generate_handler![refresh_recent_menu])
        .manage(SidecarState(Mutex::new(None)))
        .setup(|app| {
            build_menu(app.handle())?;

            // Register menu event handler.
            //
            // Because the webview loads from a remote URL (http://localhost:PORT),
            // the Tauri IPC bridge / event system is not available in the page.
            // Instead, we dispatch CustomEvents via webview.eval() — standard
            // DOM events that the frontend listens for with addEventListener.
            let handle = app.handle().clone();
            app.on_menu_event(move |_app, event| {
                let id = event.id().0.as_str();

                // Helper: dispatch a CustomEvent in the webview.
                let dispatch = |event_name: &str, detail: &str| {
                    let js = format!(
                        "window.dispatchEvent(new CustomEvent('{}', {{ detail: {} }}))",
                        event_name,
                        serde_json::json!(detail),
                    );
                    if let Some(w) = handle.get_webview_window("main") {
                        let _ = w.eval(&js);
                    }
                };

                match id {
                    ID_NEW_PROJECT => {
                        let h = handle.clone();
                        tauri::async_runtime::spawn(async move {
                            use tauri_plugin_dialog::DialogExt;
                            let path = h.dialog()
                                .file()
                                .set_title("Create a new project")
                                .set_file_name("my-project")
                                .blocking_save_file();
                            if let Some(p) = path {
                                let dir = p.as_path().unwrap();
                                let _ = std::fs::create_dir_all(dir);
                                let path_str = dir.to_string_lossy();
                                let js = format!(
                                    "window.dispatchEvent(new CustomEvent('clarity-new-project', {{ detail: {} }}))",
                                    serde_json::json!(path_str.as_ref()),
                                );
                                if let Some(w) = h.get_webview_window("main") {
                                    let _ = w.eval(&js);
                                }
                            }
                        });
                    }
                    ID_OPEN_PROJECT => {
                        let h = handle.clone();
                        tauri::async_runtime::spawn(async move {
                            use tauri_plugin_dialog::DialogExt;
                            let path = h.dialog()
                                .file()
                                .set_title("Open an existing project folder")
                                .blocking_pick_folder();
                            if let Some(p) = path {
                                let path_str = p.to_string();
                                let js = format!(
                                    "window.dispatchEvent(new CustomEvent('clarity-open-project', {{ detail: {} }}))",
                                    serde_json::json!(path_str),
                                );
                                if let Some(w) = h.get_webview_window("main") {
                                    let _ = w.eval(&js);
                                }
                            }
                        });
                    }
                    ID_PRINT => {
                        // Use Tauri's native print — window.print() is a
                        // no-op in WKWebView.
                        if let Some(w) = handle.get_webview_window("main") {
                            let _ = w.print();
                        }
                    }
                    ID_CLEAR_RECENT => {
                        dispatch("clarity-clear-recent", "");
                    }
                    other if other.starts_with("recent:") => {
                        let project_id = other.strip_prefix("recent:").unwrap_or("");
                        dispatch("clarity-activate-project", project_id);
                    }
                    _ => {}
                }
            });

            // In dev mode, the Python server and Vite dev server are started
            // externally (via beforeDevCommand and a manual `clarity web`).
            // The Tauri window loads devUrl directly — no sidecar needed.
            #[cfg(not(dev))]
            {
                use std::io::Write;

                let mut log = open_startup_log();
                macro_rules! log {
                    ($($arg:tt)*) => {
                        let msg = format!($($arg)*);
                        eprintln!("{}", msg);
                        if let Some(ref mut f) = log {
                            let _ = writeln!(f, "{}", msg);
                            let _ = f.flush();
                        }
                    };
                }

                // ---- Launch sidecar ----
                let port = find_free_port();
                log!("[startup] Launching clarity-server on port {}", port);

                let sidecar_command = app
                    .shell()
                    .sidecar("clarity-server")
                    .expect("failed to locate clarity-server sidecar binary")
                    .args(["web", "--port", &port.to_string()]);

                log!("[startup] Spawning sidecar process...");
                let (mut rx, child) =
                    sidecar_command.spawn().expect("failed to spawn sidecar");
                log!("[startup] Sidecar spawned (pid {:?})", child.pid());

                // Store the child handle for cleanup.
                let state = app.state::<SidecarState>();
                *state.0.lock().unwrap() = Some(child);

                // Log sidecar output in a background thread.
                let mut log_bg = open_startup_log();
                tauri::async_runtime::spawn(async move {
                    use tauri_plugin_shell::process::CommandEvent;
                    while let Some(event) = rx.recv().await {
                        match event {
                            CommandEvent::Stdout(line) => {
                                let text = String::from_utf8_lossy(&line);
                                eprint!("[clarity-server] {}", text);
                                if let Some(ref mut f) = log_bg {
                                    let _ = write!(f, "[clarity-server] {}", text);
                                    let _ = f.flush();
                                }
                            }
                            CommandEvent::Stderr(line) => {
                                let text = String::from_utf8_lossy(&line);
                                eprint!("[clarity-server:err] {}", text);
                                if let Some(ref mut f) = log_bg {
                                    let _ = write!(f, "[clarity-server:err] {}", text);
                                    let _ = f.flush();
                                }
                            }
                            CommandEvent::Terminated(status) => {
                                let msg = format!(
                                    "[clarity-server] process exited with code {:?}\n",
                                    status.code
                                );
                                eprint!("{}", msg);
                                if let Some(ref mut f) = log_bg {
                                    let _ = write!(f, "{}", msg);
                                    let _ = f.flush();
                                }
                                break;
                            }
                            _ => {}
                        }
                    }
                });

                // ---- Wait for server, then navigate ----
                let window = app.get_webview_window("main").expect("no main window");
                let server_url = format!("http://localhost:{}", port);

                std::thread::spawn(move || {
                    let mut log_poll = open_startup_log();
                    let start = Instant::now();
                    let client = reqwest::blocking::Client::builder()
                        .timeout(Duration::from_secs(2))
                        .build()
                        .expect("failed to build HTTP client");

                    let health_url = format!("{}/api/session", server_url);
                    let mut attempt = 0u32;

                    loop {
                        attempt += 1;
                        if start.elapsed() > SERVER_TIMEOUT {
                            let msg = format!(
                                "[startup] Timed out after {:.1}s ({} attempts) waiting for {}",
                                start.elapsed().as_secs_f64(), attempt, health_url,
                            );
                            eprintln!("{}", msg);
                            if let Some(ref mut f) = log_poll {
                                let _ = writeln!(f, "{}", msg);
                            }
                            break;
                        }

                        match client.get(&health_url).send() {
                            Ok(resp) if resp.status().is_success() => {
                                let msg = format!(
                                    "[startup] Server ready in {:.1}s, navigating to {}",
                                    start.elapsed().as_secs_f64(), server_url,
                                );
                                eprintln!("{}", msg);
                                if let Some(ref mut f) = log_poll {
                                    let _ = writeln!(f, "{}", msg);
                                }
                                let url: tauri::Url =
                                    server_url.parse().expect("invalid URL");
                                let _ = window.navigate(url);
                                break;
                            }
                            Ok(resp) => {
                                if attempt <= 3 || attempt % 20 == 0 {
                                    let msg = format!(
                                        "[startup] attempt {}: {} returned {}",
                                        attempt, health_url, resp.status(),
                                    );
                                    eprintln!("{}", msg);
                                    if let Some(ref mut f) = log_poll {
                                        let _ = writeln!(f, "{}", msg);
                                    }
                                }
                                std::thread::sleep(POLL_INTERVAL);
                            }
                            Err(e) => {
                                if attempt <= 3 || attempt % 20 == 0 {
                                    let msg = format!(
                                        "[startup] attempt {}: {} error: {}",
                                        attempt, health_url, e,
                                    );
                                    eprintln!("{}", msg);
                                    if let Some(ref mut f) = log_poll {
                                        let _ = writeln!(f, "{}", msg);
                                    }
                                }
                                std::thread::sleep(POLL_INTERVAL);
                            }
                        }
                    }
                });
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            let should_kill = matches!(
                &event,
                RunEvent::ExitRequested { .. }
                    | RunEvent::WindowEvent {
                        event: WindowEvent::Destroyed,
                        ..
                    }
            );
            if should_kill {
                let child = app.state::<SidecarState>().0.lock().unwrap().take();
                if let Some(child) = child {
                    let _ = child.kill();
                }
            }
        });
}
