//! Six Dynamics: self-modifying dynamical system for emergent coarse-graining.
//!
//! Replaces the static algebraic cascade with an iterated dynamical loop:
//! - P6 as active drive (budget ledger constrains modifications)
//! - Fast-slow separation (trajectory = fast, kernel modifications = slow)
//! - Mixture kernel (stochastic P1-P6 choice per step)
//! - Active P3 (protocol phase biases primitive selection)
//! - Viability constraints (prevent degenerate kernels)

pub mod audit;
pub mod drive;
pub mod lagrange;
pub mod mixture;
pub mod observe;
pub mod pica;
pub mod protocol;
pub mod spectral;
pub mod state;
pub mod viability;

pub use audit::AuditRecord;
pub use mixture::{run_dynamics, run_dynamics_from_kernel, Action, DynamicsTrace};
pub use observe::Snapshot;
pub use pica::PicaConfig;
pub use state::{AugmentedState, DynamicsConfig};
