mod bottom_up;
mod hierarchy;
mod top_down;

use std::error::Error;
use std::fmt;

pub use bottom_up::aggregate_values;
pub use hierarchy::aggregate_hierarchy;
pub use top_down::{compute_proportions, spread_value};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SpreadMethod {
    Even,
    Proportional,
    Manual,
    Weighted,
}

impl SpreadMethod {
    pub fn parse(value: &str) -> Result<Self, SpreadError> {
        match value.trim().to_ascii_lowercase().as_str() {
            "even" => Ok(Self::Even),
            "proportional" => Ok(Self::Proportional),
            "manual" => Ok(Self::Manual),
            "weighted" => Ok(Self::Weighted),
            other => Err(SpreadError::UnknownSpreadMethod(other.to_string())),
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SummaryMethod {
    Sum,
    Average,
    WeightedAverage,
    Min,
    Max,
    Count,
    First,
    Last,
    OpeningBalance,
    ClosingBalance,
    None,
    Formula,
}

impl SummaryMethod {
    pub fn parse(value: &str) -> Result<Self, SpreadError> {
        match value.trim().to_ascii_lowercase().as_str() {
            "sum" => Ok(Self::Sum),
            "average" => Ok(Self::Average),
            "weighted_average" => Ok(Self::WeightedAverage),
            "min" => Ok(Self::Min),
            "max" => Ok(Self::Max),
            "count" => Ok(Self::Count),
            "first" => Ok(Self::First),
            "last" => Ok(Self::Last),
            "opening_balance" => Ok(Self::OpeningBalance),
            "closing_balance" => Ok(Self::ClosingBalance),
            "none" => Ok(Self::None),
            "formula" => Ok(Self::Formula),
            other => Err(SpreadError::UnknownSummaryMethod(other.to_string())),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum SpreadError {
    UnknownSpreadMethod(String),
    UnknownSummaryMethod(String),
    InvalidWeightsLength { expected: usize, actual: usize },
    InvalidExistingValuesLength { expected: usize, actual: usize },
}

impl fmt::Display for SpreadError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            SpreadError::UnknownSpreadMethod(method) => {
                write!(f, "Unknown spread method: {}", method)
            }
            SpreadError::UnknownSummaryMethod(method) => {
                write!(f, "Unknown summary method: {}", method)
            }
            SpreadError::InvalidWeightsLength { expected, actual } => {
                write!(
                    f,
                    "weights length {} does not match member_count {}",
                    actual, expected
                )
            }
            SpreadError::InvalidExistingValuesLength { expected, actual } => {
                write!(
                    f,
                    "existing_values length {} does not match member_count {}",
                    actual, expected
                )
            }
        }
    }
}

impl Error for SpreadError {}

#[cfg(test)]
mod tests {
    use super::SummaryMethod;

    #[test]
    fn summary_method_parse_supports_f055_methods() {
        assert_eq!(
            SummaryMethod::parse("opening_balance").unwrap(),
            SummaryMethod::OpeningBalance
        );
        assert_eq!(
            SummaryMethod::parse("closing_balance").unwrap(),
            SummaryMethod::ClosingBalance
        );
        assert_eq!(
            SummaryMethod::parse("weighted_average").unwrap(),
            SummaryMethod::WeightedAverage
        );
    }
}
