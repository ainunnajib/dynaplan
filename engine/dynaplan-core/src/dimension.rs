use uuid::Uuid;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DimensionDef {
    pub id: Uuid,
    pub member_count: usize,
    pub members: Vec<Uuid>,
}

impl DimensionDef {
    pub fn new(id: Uuid, members: Vec<Uuid>) -> Self {
        Self {
            id,
            member_count: members.len(),
            members,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct DimensionKey {
    members: Vec<Uuid>,
}

impl DimensionKey {
    pub fn new(mut members: Vec<Uuid>) -> Self {
        members.sort_unstable_by_key(|member| member.as_u128());
        Self { members }
    }

    pub fn members(&self) -> &[Uuid] {
        &self.members
    }

    pub fn len(&self) -> usize {
        self.members.len()
    }

    pub fn is_empty(&self) -> bool {
        self.members.is_empty()
    }
}

impl From<Vec<Uuid>> for DimensionKey {
    fn from(members: Vec<Uuid>) -> Self {
        Self::new(members)
    }
}
