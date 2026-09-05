//! Ledger I/O: read/write JSONL entries.

use serde::{Deserialize, Serialize};
use std::fs::{self, OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::path::Path;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct HypothesisEntry {
    pub id: String,
    pub layer: u32,
    pub status: String,
    pub claim: String,
    pub primitives_used: Vec<String>,
    pub input_closures: Vec<String>,
    pub falsification_criterion: String,
    pub proposed_experiment: String,
    pub timestamp: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ExperimentEntry {
    pub id: String,
    pub hypothesis_id: String,
    pub status: String,
    pub description: String,
    pub parameters: serde_json::Value,
    pub metrics: Vec<String>,
    pub artifacts_dir: String,
    pub timestamp: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ResultEntry {
    pub id: String,
    pub experiment_id: String,
    pub seed: u64,
    pub scale: usize,
    pub params: serde_json::Value,
    pub metrics: serde_json::Value,
    pub artifacts: Vec<String>,
    pub outcome: String,
    pub timestamp: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ClosureEntry {
    pub id: String,
    pub layer: u32,
    pub status: String,
    pub description: String,
    pub detection_method: String,
    pub stability_score: f64,
    pub robustness_rate: f64,
    pub epsilon: f64,
    pub persistence_threshold: f64,
    pub supporting_experiments: Vec<String>,
    pub supporting_runs: Vec<String>,
    pub primitives_involved: Vec<String>,
    pub timestamp: String,
}

/// Append a JSON line to a JSONL file.
pub fn append_jsonl<T: Serialize>(path: &Path, entry: &T) -> std::io::Result<()> {
    let mut file = OpenOptions::new().create(true).append(true).open(path)?;
    let json = serde_json::to_string(entry)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;
    writeln!(file, "{}", json)?;
    Ok(())
}

/// Read all entries from a JSONL file.
pub fn read_jsonl<T: for<'de> Deserialize<'de>>(path: &Path) -> std::io::Result<Vec<T>> {
    let content = fs::read_to_string(path)?;
    let mut entries = Vec::new();
    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        let entry: T = serde_json::from_str(trimmed)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
        entries.push(entry);
    }
    Ok(entries)
}

/// Count entries in a JSONL file.
pub fn count_jsonl(path: &Path) -> std::io::Result<usize> {
    let file = fs::File::open(path)?;
    let reader = BufReader::new(file);
    Ok(reader
        .lines()
        .filter_map(|l| l.ok())
        .filter(|l| !l.trim().is_empty())
        .count())
}

/// Generate a timestamp string.
pub fn now_iso8601() -> String {
    // Simple implementation without chrono dependency
    use std::time::{SystemTime, UNIX_EPOCH};
    let dur = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default();
    let secs = dur.as_secs();
    // Rough conversion (not accounting for leap seconds, etc.)
    let days = secs / 86400;
    let years = 1970 + days / 365; // approximate
    let remaining_secs = secs % 86400;
    let hours = remaining_secs / 3600;
    let minutes = (remaining_secs % 3600) / 60;
    let seconds = remaining_secs % 60;
    format!(
        "{:04}-01-01T{:02}:{:02}:{:02}Z",
        years, hours, minutes, seconds
    )
}

/// Generate a run ID from experiment, seed, scale, and a hash.
pub fn make_run_id(exp_id: &str, seed: u64, scale: usize, params: &serde_json::Value) -> String {
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    hasher.update(format!("{}-{}-{}-{}", exp_id, seed, scale, params));
    let hash = format!("{:x}", hasher.finalize());
    format!("RUN-{}-s{}-n{}-{}", exp_id, seed, scale, &hash[..6])
}
