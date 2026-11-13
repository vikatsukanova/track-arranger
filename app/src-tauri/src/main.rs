#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use std::sync::Mutex;
use tauri::{Manager, RunEvent};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

#[derive(Clone, serde::Serialize)]
struct Connection {
    port: u16,
    token: String,
}
struct Backend {
    connection: Mutex<Option<Connection>>,
    child: Mutex<Option<CommandChild>>,
}
#[tauri::command]
fn backend_config(state: tauri::State<Backend>) -> Option<Connection> {
    state.connection.lock().unwrap().clone()
}
fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(Backend {
            connection: Mutex::new(None),
            child: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![backend_config])
        .setup(|app| {
            let token = uuid::Uuid::new_v4().to_string();
            let cache = app.path().app_cache_dir()?;
            std::fs::create_dir_all(&cache)?;
            let command = app
                .shell()
                .sidecar("track-arranger-api")?
                .set_process_group(true)
                .kill_on_drop(true)
                .env("TRACK_ARRANGER_TOKEN", &token)
                .env("TRACK_ARRANGER_CACHE", cache.to_string_lossy().to_string());
            let (mut receiver, child) = command.spawn()?;
            *app.state::<Backend>().child.lock().unwrap() = Some(child);
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                while let Some(event) = receiver.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            if let Ok(value) = serde_json::from_slice::<serde_json::Value>(&line) {
                                if let Some(port) =
                                    value["port"].as_u64().filter(|p| *p > 0 && *p <= 65535)
                                {
                                    *handle.state::<Backend>().connection.lock().unwrap() =
                                        Some(Connection {
                                            port: port as u16,
                                            token: token.clone(),
                                        });
                                }
                            }
                        }
                        CommandEvent::Terminated(_) => {
                            *handle.state::<Backend>().connection.lock().unwrap() = None;
                            break;
                        }
                        CommandEvent::Stderr(line) => {
                            eprintln!("{}", String::from_utf8_lossy(&line))
                        }
                        _ => {}
                    }
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("Unable to start Track Arranger");
    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            if let Some(child) = handle.state::<Backend>().child.lock().unwrap().take() {
                let _ = child.kill();
            }
        }
    });
}
