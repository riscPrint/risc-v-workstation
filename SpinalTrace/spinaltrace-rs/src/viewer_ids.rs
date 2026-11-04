//! Stable viewer IDs. Real vertices occupy 0..vertex_count; each edge owns one pseudo-node.
use anyhow::{bail, Result};

pub fn relation_id(vertex_count: usize, edge_index: usize) -> Result<u64> {
    let id = (vertex_count as u64).checked_add(edge_index as u64)
        .ok_or_else(|| anyhow::anyhow!("Viewer ID overflow"))?;
    // The web viewer represents IDs as JavaScript numbers.
    if id > (1u64 << 53) - 1 { bail!("Viewer ID exceeds JavaScript's exact integer range"); }
    Ok(id)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashSet;

    #[test]
    fn repeated_long_distance_relations_have_unique_ids() {
        // Equal endpoint sums collide with the old ungrouped formula. Repeated
        // endpoints also collide with the old grouped formula, even on 64-bit hosts.
        let relations = [(0usize, 7usize), (1, 6), (0, 7), (1, 6)];
        let mut ids: HashSet<u64> = (0..8).collect();
        for (index, (_, destination)) in relations.iter().enumerate() {
            let id = relation_id(8, index).unwrap();
            assert!(ids.insert(id));
            // Navigation decodes the edge index, retaining its destination source node.
            assert_eq!(relations[(id - 8) as usize].1, *destination);
        }
    }

    #[test]
    fn rejects_inexact_web_ids() {
        assert!(relation_id(1usize << 53, 0).is_err());
    }
}
