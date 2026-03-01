pub fn sum_slice(values: &[f64]) -> f64 {
    const CHUNK_SIZE: usize = 8;

    let mut total = 0.0;
    let mut idx = 0usize;

    while idx + CHUNK_SIZE <= values.len() {
        total += values[idx]
            + values[idx + 1]
            + values[idx + 2]
            + values[idx + 3]
            + values[idx + 4]
            + values[idx + 5]
            + values[idx + 6]
            + values[idx + 7];
        idx += CHUNK_SIZE;
    }

    for value in &values[idx..] {
        total += *value;
    }

    total
}

pub fn average_slice(values: &[f64]) -> Option<f64> {
    if values.is_empty() {
        return None;
    }

    Some(sum_slice(values) / values.len() as f64)
}

pub fn count_slice(values: &[f64]) -> usize {
    values.len()
}
