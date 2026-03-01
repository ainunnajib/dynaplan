pub mod block;
pub mod dimension;
pub mod model;
pub mod value;

pub use block::CalculationBlock;
pub use dimension::{DimensionDef, DimensionKey};
pub use model::ModelState;
pub use value::CellValue;

#[cfg(test)]
mod tests {
    use std::collections::HashSet;

    use uuid::Uuid;

    use crate::{DimensionDef, DimensionKey, ModelState};

    fn seeded_uuid(seed: u128) -> Uuid {
        Uuid::from_u128(seed + 1)
    }

    fn build_dimensions(
        model: &mut ModelState,
        dimension_count: usize,
        members_per_dimension: usize,
    ) -> Vec<Vec<Uuid>> {
        let mut dimension_members = Vec::with_capacity(dimension_count);

        for dim_idx in 0..dimension_count {
            let dimension_id = seeded_uuid(10_000 + dim_idx as u128);
            let members = (0..members_per_dimension)
                .map(|member_idx| {
                    seeded_uuid(((dim_idx as u128 + 1) << 32) + member_idx as u128)
                })
                .collect::<Vec<Uuid>>();

            model.upsert_dimension(DimensionDef::new(dimension_id, members.clone()));
            dimension_members.push(members);
        }

        dimension_members
    }

    fn key_for_index(mut index: usize, dimension_members: &[Vec<Uuid>]) -> DimensionKey {
        let mut members = Vec::with_capacity(dimension_members.len());

        for members_for_dimension in dimension_members {
            let member_index = index % members_for_dimension.len();
            members.push(members_for_dimension[member_index]);
            index /= members_for_dimension.len();
        }

        DimensionKey::new(members)
    }

    #[test]
    fn dimension_key_normalizes_member_order() {
        let a = seeded_uuid(1);
        let b = seeded_uuid(2);
        let c = seeded_uuid(3);

        let key_a = DimensionKey::new(vec![c, a, b]);
        let key_b = DimensionKey::new(vec![b, c, a]);

        assert_eq!(key_a, key_b);
    }

    #[test]
    fn model_state_handles_sparse_block_write_read_for_100k_cells() {
        let mut model = ModelState::new();
        let dimension_members = build_dimensions(&mut model, 5, 100);
        let line_item_id = seeded_uuid(1_000_000);

        let sample_indexes = [0usize, 1, 17, 999, 8_888, 42_424, 99_999];
        let sample_set: HashSet<usize> = sample_indexes.iter().copied().collect();

        for index in 0..100_000usize {
            let key = key_for_index(index, &dimension_members);
            let value = index as f64 * 1.25;
            model.write_numeric_cell(line_item_id, key.clone(), value);

            if sample_set.contains(&index) {
                assert_eq!(model.read_numeric_cell(&line_item_id, &key), Some(value));
            }
        }

        let block = model
            .block(&line_item_id)
            .expect("line item block should exist after writes");

        assert_eq!(block.len(), 100_000);
        assert_eq!(block.key_column().len(), 100_000);
        assert_eq!(block.value_column().len(), 100_000);
        assert_eq!(block.lookup_index_len(), 100_000);

        for index in sample_indexes {
            let key = key_for_index(index, &dimension_members);
            let expected = index as f64 * 1.25;

            assert_eq!(model.read_numeric_cell(&line_item_id, &key), Some(expected));

            let offset = block
                .offset_for_key(&key)
                .expect("dimension key should resolve to a column offset");
            let value_from_column = block
                .value_at_offset(offset)
                .expect("column offset should resolve to a value");

            assert_eq!(value_from_column, expected);
        }
    }
}
