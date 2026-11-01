//! thox-agentos core library.
//!
//! The agentic layer for ThoxOS, portable across the Omarchy desktop track
//! and the Ginux kernel track. Everything in this library is plain
//! synchronous Rust on top of std: no async runtime, so the same code runs
//! in a full desktop session and in a minimal Ginux guest userspace.
//!
//! Modules:
//! - `manifest`: agent definitions and capability grants.
//! - `identity`: ed25519 signed agent identity tokens, verified offline.
//! - `audit`: append-only audit log of every broker and supervisor decision.
//! - `broker`: capability enforcement for tool calls made by agents.
//! - `supervisor`: process supervision with restart policies and journals.
//! - `model`: the user-swappable kernel model slot (spec S10, ruling D11).
//! - `client`: line-delimited JSON client for the daemon control socket.

pub mod audit;
pub mod broker;
pub mod client;
pub mod identity;
pub mod manifest;
pub mod model;
pub mod supervisor;
pub mod util;
