use super::{SpreadError, SpreadMethod};

pub fn spread_value(
    total: f64,
    member_count: usize,
    method: SpreadMethod,
    weights: Option<&[f64]>,
    existing_values: Option<&[f64]>,
) -> Result<Vec<f64>, SpreadError> {
    if member_count == 0 {
        return Ok(Vec::new());
    }

    match method {
        SpreadMethod::Even => Ok(even_split(total, member_count)),
        SpreadMethod::Proportional => {
            let Some(existing_values) = existing_values else {
                return Ok(even_split(total, member_count));
            };

            if existing_values.is_empty() {
                return Ok(even_split(total, member_count));
            }

            if existing_values.len() != member_count {
                return Err(SpreadError::InvalidExistingValuesLength {
                    expected: member_count,
                    actual: existing_values.len(),
                });
            }

            let proportions = compute_proportions(existing_values);
            Ok(proportions.into_iter().map(|v| total * v).collect())
        }
        SpreadMethod::Manual => {
            let Some(existing_values) = existing_values else {
                return Ok(vec![0.0; member_count]);
            };

            if existing_values.len() != member_count {
                return Err(SpreadError::InvalidExistingValuesLength {
                    expected: member_count,
                    actual: existing_values.len(),
                });
            }

            Ok(existing_values.to_vec())
        }
        SpreadMethod::Weighted => {
            let Some(weights) = weights else {
                return Ok(even_split(total, member_count));
            };

            if weights.is_empty() {
                return Ok(even_split(total, member_count));
            }

            if weights.len() != member_count {
                return Err(SpreadError::InvalidWeightsLength {
                    expected: member_count,
                    actual: weights.len(),
                });
            }

            let weight_total: f64 = weights.iter().sum();
            if weight_total == 0.0 {
                return Ok(even_split(total, member_count));
            }

            Ok(weights.iter().map(|weight| total * (weight / weight_total)).collect())
        }
    }
}

pub fn compute_proportions(values: &[f64]) -> Vec<f64> {
    if values.is_empty() {
        return Vec::new();
    }

    let total: f64 = values.iter().map(|value| value.abs()).sum();
    if total == 0.0 {
        let share = 1.0 / values.len() as f64;
        return vec![share; values.len()];
    }

    values.iter().map(|value| value.abs() / total).collect()
}

fn even_split(total: f64, member_count: usize) -> Vec<f64> {
    let share = total / member_count as f64;
    vec![share; member_count]
}

#[cfg(test)]
mod tests {
    use super::{compute_proportions, spread_value};
    use crate::spread::{SpreadError, SpreadMethod};

    #[test]
    fn even_spread_splits_equally() {
        let values = spread_value(120.0, 3, SpreadMethod::Even, None, None).unwrap();
        assert_eq!(values, vec![40.0, 40.0, 40.0]);
    }

    #[test]
    fn proportional_spread_uses_absolute_shares() {
        let values = spread_value(
            200.0,
            3,
            SpreadMethod::Proportional,
            None,
            Some(&[10.0, -30.0, 60.0]),
        )
        .unwrap();
        assert!((values[0] - 20.0).abs() < 1e-9);
        assert!((values[1] - 60.0).abs() < 1e-9);
        assert!((values[2] - 120.0).abs() < 1e-9);
    }

    #[test]
    fn weighted_spread_zero_total_falls_back_to_even() {
        let values = spread_value(30.0, 3, SpreadMethod::Weighted, Some(&[0.0, 0.0, 0.0]), None)
            .unwrap();
        assert_eq!(values, vec![10.0, 10.0, 10.0]);
    }

    #[test]
    fn manual_spread_without_existing_values_returns_zeroes() {
        let values = spread_value(100.0, 4, SpreadMethod::Manual, None, None).unwrap();
        assert_eq!(values, vec![0.0, 0.0, 0.0, 0.0]);
    }

    #[test]
    fn spread_rejects_invalid_weight_length() {
        let err = spread_value(100.0, 3, SpreadMethod::Weighted, Some(&[1.0, 2.0]), None)
            .expect_err("weights length should be validated");
        assert_eq!(
            err,
            SpreadError::InvalidWeightsLength {
                expected: 3,
                actual: 2
            }
        );
    }

    #[test]
    fn compute_proportions_even_when_all_zero() {
        let proportions = compute_proportions(&[0.0, 0.0, 0.0]);
        assert_eq!(proportions, vec![1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0]);
    }
}
