//! AeroCloud Preview WASM — Browser-side Archimedean spiral + Quadtree
//!
//! This crate is a skeleton in Phase 1. Implementation begins in Phase 3.

#![allow(dead_code)]

/// Placeholder to keep cargo check happy.
pub fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn smoke_version() {
        assert_eq!(version(), "0.1.0");
    }
}
