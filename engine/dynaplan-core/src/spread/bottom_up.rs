use crate::calc::sum_slice;

use super::SummaryMethod;

pub fn aggregate_values(values: &[f64], method: SummaryMethod) -> f64 {
    if values.is_empty() {
        return 0.0;
    }

    match method {
        SummaryMethod::Sum | SummaryMethod::None | SummaryMethod::Formula => sum_slice(values),
        SummaryMethod::Average | SummaryMethod::WeightedAverage => {
            sum_slice(values) / values.len() as f64
        }
        SummaryMethod::Min => values
            .iter()
            .fold(values[0], |current, value| current.min(*value)),
        SummaryMethod::Max => values
            .iter()
            .fold(values[0], |current, value| current.max(*value)),
        SummaryMethod::Count => values.len() as f64,
        SummaryMethod::First | SummaryMethod::OpeningBalance => values[0],
        SummaryMethod::Last | SummaryMethod::ClosingBalance => values[values.len() - 1],
    }
}

#[cfg(test)]
mod tests {
    use super::aggregate_values;
    use crate::spread::SummaryMethod;

    #[test]
    fn supports_standard_summary_methods() {
        let values = vec![10.0, 20.0, 5.0];

        assert_eq!(aggregate_values(&values, SummaryMethod::Sum), 35.0);
        assert_eq!(
            aggregate_values(&values, SummaryMethod::Average),
            35.0 / 3.0
        );
        assert_eq!(aggregate_values(&values, SummaryMethod::Min), 5.0);
        assert_eq!(aggregate_values(&values, SummaryMethod::Max), 20.0);
        assert_eq!(aggregate_values(&values, SummaryMethod::Count), 3.0);
        assert_eq!(aggregate_values(&values, SummaryMethod::First), 10.0);
        assert_eq!(aggregate_values(&values, SummaryMethod::Last), 5.0);
        assert_eq!(aggregate_values(&values, SummaryMethod::OpeningBalance), 10.0);
        assert_eq!(aggregate_values(&values, SummaryMethod::ClosingBalance), 5.0);
        assert_eq!(
            aggregate_values(&values, SummaryMethod::WeightedAverage),
            35.0 / 3.0
        );
    }

    #[test]
    fn formula_and_none_fall_back_to_sum() {
        let values = vec![2.0, 4.0, 6.0];
        assert_eq!(aggregate_values(&values, SummaryMethod::Formula), 12.0);
        assert_eq!(aggregate_values(&values, SummaryMethod::None), 12.0);
    }

    #[test]
    fn empty_values_returns_zero() {
        assert_eq!(aggregate_values(&[], SummaryMethod::Sum), 0.0);
        assert_eq!(aggregate_values(&[], SummaryMethod::Count), 0.0);
    }
}
