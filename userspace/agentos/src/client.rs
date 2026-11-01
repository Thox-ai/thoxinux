//! Minimal client for the daemon control socket.
//!
//! Protocol: one JSON object per line in each direction. A request is
//! `{"cmd": "...", ...}` and a response is `{"ok": bool, ...}`.

use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::UnixStream;
use std::path::Path;

use serde_json::Value;

pub fn request(socket: &Path, req: Value) -> Result<Value, String> {
    let mut stream = UnixStream::connect(socket)
        .map_err(|e| format!("cannot connect to daemon at {}: {e}", socket.display()))?;
    let mut line = serde_json::to_string(&req).map_err(|e| e.to_string())?;
    line.push('\n');
    stream
        .write_all(line.as_bytes())
        .map_err(|e| format!("cannot write request: {e}"))?;
    let mut reader = BufReader::new(stream);
    let mut response = String::new();
    reader
        .read_line(&mut response)
        .map_err(|e| format!("cannot read response: {e}"))?;
    if response.trim().is_empty() {
        return Err("daemon closed the connection without a response".to_string());
    }
    serde_json::from_str(&response).map_err(|e| format!("bad daemon response: {e}"))
}
