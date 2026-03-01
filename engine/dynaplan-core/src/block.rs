use std::collections::HashMap;

use uuid::Uuid;

use crate::dimension::DimensionKey;

#[derive(Clone, Debug)]
pub struct CalculationBlock {
    pub line_item_id: Uuid,
    sparse_values: HashMap<DimensionKey, f64>,
    key_column: Vec<DimensionKey>,
    value_column: Vec<f64>,
    key_index: HashMap<DimensionKey, usize>,
}

impl CalculationBlock {
    pub fn new(line_item_id: Uuid) -> Self {
        Self {
            line_item_id,
            sparse_values: HashMap::new(),
            key_column: Vec::new(),
            value_column: Vec::new(),
            key_index: HashMap::new(),
        }
    }

    pub fn write_numeric(&mut self, key: DimensionKey, value: f64) {
        if let Some(offset) = self.key_index.get(&key).copied() {
            self.value_column[offset] = value;
        } else {
            let offset = self.value_column.len();
            self.key_column.push(key.clone());
            self.value_column.push(value);
            self.key_index.insert(key.clone(), offset);
        }

        self.sparse_values.insert(key, value);
    }

    pub fn read_numeric(&self, key: &DimensionKey) -> Option<f64> {
        self.sparse_values.get(key).copied()
    }

    pub fn offset_for_key(&self, key: &DimensionKey) -> Option<usize> {
        self.key_index.get(key).copied()
    }

    pub fn value_at_offset(&self, offset: usize) -> Option<f64> {
        self.value_column.get(offset).copied()
    }

    pub fn len(&self) -> usize {
        self.sparse_values.len()
    }

    pub fn is_empty(&self) -> bool {
        self.sparse_values.is_empty()
    }

    pub fn key_column(&self) -> &[DimensionKey] {
        &self.key_column
    }

    pub fn value_column(&self) -> &[f64] {
        &self.value_column
    }

    pub fn lookup_index_len(&self) -> usize {
        self.key_index.len()
    }

    pub fn iter_columnar(&self) -> impl Iterator<Item = (&DimensionKey, &f64)> {
        self.key_column.iter().zip(self.value_column.iter())
    }
}
