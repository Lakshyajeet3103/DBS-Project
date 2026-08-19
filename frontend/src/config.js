// Roles mirror the access tiers described in the RBAC design.
// clearance is a simple integer ceiling: a chunk tagged with a
// clearance requirement higher than the active role's clearance
// must never be returned by the retriever.
//
// IMPORTANT: this file only drives what the UI *asks for* and how it
// *labels* things. It is not a security boundary. The backend must
// enforce the same rule at the vector-store query layer (a metadata
// filter in the Chroma `where` clause), or a user can bypass this by
// calling the API directly. See README.md.
export const ROLES = [
  {
    id: 'analyst',
    name: 'Junior Analyst',
    clearance: 1,
    badge: 'L1',
    description: 'General policy and handbook access only. No compensation or executive contract data.',
  },
  {
    id: 'manager',
    name: 'HR Manager',
    clearance: 2,
    badge: 'L2',
    description: 'Adds vendor contracts and team-level compensation bands.',
  },
  {
    id: 'exec',
    name: 'C-Suite Executive',
    clearance: 3,
    badge: 'L3',
    description: 'Full access, including individual executive compensation contracts.',
  },
]

export const DOCUMENT_TYPES = ['Policy', 'Contract', 'Compensation']

export const EFFECTIVE_YEARS = ['Any year', 2024, 2023, 2022]

export const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'
