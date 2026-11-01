//! The tool broker.
//!
//! Agents never touch the system directly for brokered operations. They
//! send a tool request to the daemon; the broker checks the request
//! against the capability grants in the agent manifest, executes it if
//! allowed, and writes the decision to the audit log either way.
//!
//! Tools:
//! - `fs.read`  {path}                 read a file inside an fs_read root
//! - `fs.write` {path, content}        write a file inside an fs_write root
//! - `exec`     {program, args}        run an allowlisted program
//! - `net.http_get` {url}              plain HTTP GET, only when the
//!                                     manifest grants network egress

use std::io::{Read, Write};
use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::Duration;

use serde_json::{json, Value};

use crate::audit::AuditLog;
use crate::manifest::Permissions;

pub const MAX_READ_BYTES: usize = 1 << 20;
pub const EXEC_TIMEOUT_SECS: u64 = 15;

#[derive(Debug)]
pub struct ToolOutcome {
    pub allowed: bool,
    pub result: Value,
    pub reason: String,
}

/// Check whether `path` (canonicalized) is inside any granted root.
/// Roots are canonicalized too, so symlinked prefixes cannot escape.
fn path_in_roots(path: &Path, roots: &[PathBuf]) -> Result<PathBuf, String> {
    let canon = path
        .canonicalize()
        .map_err(|e| format!("cannot resolve {}: {e}", path.display()))?;
    for root in roots {
        if let Ok(root_canon) = root.canonicalize() {
            if canon == root_canon || canon.starts_with(&root_canon) {
                return Ok(canon);
            }
        }
    }
    Err(format!("{} is outside every granted root", path.display()))
}

/// For writes, the file may not exist yet: canonicalize the parent and
/// reattach the file name, then run the same root check.
fn write_path_in_roots(path: &Path, roots: &[PathBuf]) -> Result<PathBuf, String> {
    let parent = path.parent().unwrap_or_else(|| Path::new("/"));
    let name = path
        .file_name()
        .ok_or_else(|| "write path has no file name".to_string())?;
    let canon_parent = parent
        .canonicalize()
        .map_err(|e| format!("cannot resolve parent {}: {e}", parent.display()))?;
    let candidate = canon_parent.join(name);
    for root in roots {
        if let Ok(root_canon) = root.canonicalize() {
            if candidate == root_canon || candidate.starts_with(&root_canon) {
                return Ok(candidate);
            }
        }
    }
    Err(format!("{} is outside every granted root", path.display()))
}

fn program_allowed(perms: &Permissions, program: &str) -> bool {
    let program_name = Path::new(program).file_name().and_then(|s| s.to_str());
    perms.exec_allow.iter().any(|allowed| {
        allowed == program
            || (!allowed.contains('/') && Some(allowed.as_str()) == program_name)
    })
}

pub struct Broker<'a> {
    audit: &'a AuditLog,
}

impl<'a> Broker<'a> {
    pub fn new(audit: &'a AuditLog) -> Broker<'a> {
        Broker { audit }
    }

    fn deny(&self, agent: &str, tool: &str, target: &str, reason: &str) -> ToolOutcome {
        let _ = self
            .audit
            .append(agent, &format!("tool.{tool}"), target, "deny", reason);
        ToolOutcome {
            allowed: false,
            result: json!({"error": reason}),
            reason: reason.to_string(),
        }
    }

    fn allow(
        &self,
        agent: &str,
        tool: &str,
        target: &str,
        result: Value,
        detail: &str,
    ) -> ToolOutcome {
        let _ = self
            .audit
            .append(agent, &format!("tool.{tool}"), target, "allow", detail);
        ToolOutcome {
            allowed: true,
            result,
            reason: detail.to_string(),
        }
    }

    /// Execute one tool request for `agent` under `perms`.
    pub fn execute(&self, agent: &str, perms: &Permissions, tool: &str, params: &Value) -> ToolOutcome {
        match tool {
            "fs.read" => self.fs_read(agent, perms, params),
            "fs.write" => self.fs_write(agent, perms, params),
            "exec" => self.exec(agent, perms, params),
            "net.http_get" => self.net_http_get(agent, perms, params),
            other => self.deny(agent, other, "", &format!("unknown tool: {other}")),
        }
    }

    fn fs_read(&self, agent: &str, perms: &Permissions, params: &Value) -> ToolOutcome {
        let path_str = params.get("path").and_then(|v| v.as_str()).unwrap_or("");
        let path = Path::new(path_str);
        let canon = match path_in_roots(path, &perms.fs_read) {
            Ok(c) => c,
            Err(reason) => return self.deny(agent, "fs.read", path_str, &reason),
        };
        match std::fs::read(&canon) {
            Ok(data) => {
                let cut = data.len().min(MAX_READ_BYTES);
                let content = String::from_utf8_lossy(&data[..cut]).into_owned();
                self.allow(
                    agent,
                    "fs.read",
                    path_str,
                    json!({"content": content, "bytes": data.len(), "truncated": data.len() > MAX_READ_BYTES}),
                    &format!("read {} bytes", data.len()),
                )
            }
            Err(e) => self.deny(agent, "fs.read", path_str, &format!("read failed: {e}")),
        }
    }

    fn fs_write(&self, agent: &str, perms: &Permissions, params: &Value) -> ToolOutcome {
        let path_str = params.get("path").and_then(|v| v.as_str()).unwrap_or("");
        let content = params.get("content").and_then(|v| v.as_str()).unwrap_or("");
        let path = Path::new(path_str);
        let target = match write_path_in_roots(path, &perms.fs_write) {
            Ok(t) => t,
            Err(reason) => return self.deny(agent, "fs.write", path_str, &reason),
        };
        match std::fs::write(&target, content) {
            Ok(()) => self.allow(
                agent,
                "fs.write",
                path_str,
                json!({"written": content.len()}),
                &format!("wrote {} bytes", content.len()),
            ),
            Err(e) => self.deny(agent, "fs.write", path_str, &format!("write failed: {e}")),
        }
    }

    fn exec(&self, agent: &str, perms: &Permissions, params: &Value) -> ToolOutcome {
        let program = params.get("program").and_then(|v| v.as_str()).unwrap_or("");
        let args: Vec<String> = params
            .get("args")
            .and_then(|v| v.as_array())
            .map(|a| {
                a.iter()
                    .filter_map(|x| x.as_str().map(|s| s.to_string()))
                    .collect()
            })
            .unwrap_or_default();
        if !program_allowed(perms, program) {
            return self.deny(
                agent,
                "exec",
                program,
                &format!("program {program:?} is not in the exec allowlist"),
            );
        }
        let spawned = Command::new(program)
            .args(&args)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn();
        match spawned {
            Ok(mut child) => {
                let deadline = std::time::Instant::now() + Duration::from_secs(EXEC_TIMEOUT_SECS);
                loop {
                    match child.try_wait() {
                        Ok(Some(_status)) => {
                            let out = child.wait_with_output();
                            return match out {
                                Ok(o) => self.allow(
                                    agent,
                                    "exec",
                                    program,
                                    json!({
                                        "exit_code": o.status.code(),
                                        "stdout": String::from_utf8_lossy(&o.stdout).into_owned(),
                                        "stderr": String::from_utf8_lossy(&o.stderr).into_owned(),
                                    }),
                                    &format!("exit code {:?}", o.status.code()),
                                ),
                                Err(e) => self.deny(agent, "exec", program, &format!("collect output: {e}")),
                            };
                        }
                        Ok(None) => {
                            if std::time::Instant::now() > deadline {
                                let _ = child.kill();
                                return self.deny(agent, "exec", program, "exec timed out");
                            }
                            std::thread::sleep(Duration::from_millis(25));
                        }
                        Err(e) => {
                            return self.deny(agent, "exec", program, &format!("wait failed: {e}"))
                        }
                    }
                }
            }
            Err(e) => self.deny(agent, "exec", program, &format!("spawn failed: {e}")),
        }
    }

    fn net_http_get(&self, agent: &str, perms: &Permissions, params: &Value) -> ToolOutcome {
        let url = params.get("url").and_then(|v| v.as_str()).unwrap_or("");
        if !perms.network_egress {
            return self.deny(
                agent,
                "net.http_get",
                url,
                "network egress is not granted to this agent",
            );
        }
        let rest = match url.strip_prefix("http://") {
            Some(r) => r,
            None => {
                return self.deny(
                    agent,
                    "net.http_get",
                    url,
                    "only http:// URLs are supported by the broker fetch",
                )
            }
        };
        let (hostport, path) = match rest.find('/') {
            Some(i) => (&rest[..i], &rest[i..]),
            None => (rest, "/"),
        };
        let hostport = if hostport.contains(':') {
            hostport.to_string()
        } else {
            format!("{hostport}:80")
        };
        let result = (|| -> std::io::Result<String> {
            let mut stream = TcpStream::connect(&hostport)?;
            stream.set_read_timeout(Some(Duration::from_secs(10)))?;
            let host = hostport.split(':').next().unwrap_or("");
            write!(
                stream,
                "GET {path} HTTP/1.0\r\nHost: {host}\r\nUser-Agent: thox-agentos-broker\r\n\r\n"
            )?;
            let mut buf = Vec::new();
            stream.take((MAX_READ_BYTES + 4096) as u64).read_to_end(&mut buf)?;
            Ok(String::from_utf8_lossy(&buf).into_owned())
        })();
        match result {
            Ok(body) => self.allow(
                agent,
                "net.http_get",
                url,
                json!({"body": body}),
                "fetch completed",
            ),
            Err(e) => self.deny(agent, "net.http_get", url, &format!("fetch failed: {e}")),
        }
    }
}
