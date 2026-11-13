import { invoke, isTauri } from "@tauri-apps/api/core";
type Connection = { port: number; token: string };
let connection: Connection;
export async function connect(): Promise<void> {
  if (!isTauri()) {
    const token = import.meta.env.VITE_BACKEND_TOKEN;
    if (!token)
      throw new Error(
        "Start the Tauri app, or set VITE_BACKEND_TOKEN for browser development.",
      );
    connection = {
      port: Number(import.meta.env.VITE_BACKEND_PORT || 8765),
      token,
    };
    await api("/health");
    return;
  }
  for (let attempt = 0; attempt < 240; attempt++) {
    const config = await invoke<Connection | null>("backend_config");
    if (config) {
      connection = config;
      try {
        await api("/health");
        return;
      } catch {
        /* Wait for the HTTP listener. */
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("The local audio engine did not start. Restart the app.");
}
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`http://127.0.0.1:${connection.port}${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      Authorization: `Bearer ${connection.token}`,
      ...(body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
    },
    body:
      body === undefined
        ? undefined
        : body instanceof FormData
          ? body
          : JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok)
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Check your values and try again.",
    );
  return result;
}
