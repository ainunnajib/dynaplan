use std::collections::{HashMap, HashSet};

use uuid::Uuid;

use crate::{block::CalculationBlock, dimension::DimensionDef, dimension::DimensionKey};

#[derive(Clone, Debug, Default)]
pub struct ModelState {
    blocks: HashMap<Uuid, CalculationBlock>,
    dimension_defs: HashMap<Uuid, DimensionDef>,
    dependency_edges: HashMap<Uuid, HashSet<Uuid>>,
}

impl ModelState {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn upsert_dimension(&mut self, dimension: DimensionDef) {
        self.dimension_defs.insert(dimension.id, dimension);
    }

    pub fn dimension(&self, dimension_id: &Uuid) -> Option<&DimensionDef> {
        self.dimension_defs.get(dimension_id)
    }

    pub fn dimensions(&self) -> &HashMap<Uuid, DimensionDef> {
        &self.dimension_defs
    }

    pub fn ensure_block(&mut self, line_item_id: Uuid) -> &mut CalculationBlock {
        self.blocks
            .entry(line_item_id)
            .or_insert_with(|| CalculationBlock::new(line_item_id))
    }

    pub fn block(&self, line_item_id: &Uuid) -> Option<&CalculationBlock> {
        self.blocks.get(line_item_id)
    }

    pub fn block_mut(&mut self, line_item_id: &Uuid) -> Option<&mut CalculationBlock> {
        self.blocks.get_mut(line_item_id)
    }

    pub fn write_numeric_cell(&mut self, line_item_id: Uuid, key: DimensionKey, value: f64) {
        self.ensure_block(line_item_id).write_numeric(key, value);
    }

    pub fn read_numeric_cell(&self, line_item_id: &Uuid, key: &DimensionKey) -> Option<f64> {
        self.blocks
            .get(line_item_id)
            .and_then(|block| block.read_numeric(key))
    }

    pub fn add_dependency(&mut self, line_item_id: Uuid, depends_on: Uuid) {
        self.dependency_edges
            .entry(line_item_id)
            .or_insert_with(HashSet::new)
            .insert(depends_on);
    }

    pub fn dependencies_of(&self, line_item_id: &Uuid) -> Option<&HashSet<Uuid>> {
        self.dependency_edges.get(line_item_id)
    }

    pub fn blocks(&self) -> &HashMap<Uuid, CalculationBlock> {
        &self.blocks
    }

    pub fn block_count(&self) -> usize {
        self.blocks.len()
    }

    pub fn dimension_count(&self) -> usize {
        self.dimension_defs.len()
    }
}
