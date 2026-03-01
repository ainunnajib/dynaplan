pub mod aggregation;
pub mod context;
pub mod orchestrator;
pub mod parallel;

pub use aggregation::{average_slice, count_slice, sum_slice};
pub use context::{build_cell_context, collect_recalc_keys, ContextError, FormulaSpec};
pub use orchestrator::{CalcError, RecalcOrchestrator, RecalcResult};
pub use parallel::{build_topological_levels, execute_level_parallel};

#[cfg(test)]
mod tests;
