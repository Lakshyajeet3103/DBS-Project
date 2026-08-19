import { ROLES, DOCUMENT_TYPES, EFFECTIVE_YEARS } from '../config'

export default function Sidebar({
  role,
  onRoleChange,
  activeTypes,
  onToggleType,
  year,
  onYearChange,
}) {
  const activeRole = ROLES.find((r) => r.id === role)

  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">Docket</span>
        <span className="brand-tag">RAG · RBAC</span>
      </div>
      <p className="brand-sub">
        Query employee handbooks and vendor contracts with clearance-aware
        retrieval. Nothing outside your role's scope ever reaches the model.
      </p>

      <div className="sidebar-section">
        <div className="sidebar-label">Acting as</div>
        <div className="role-list">
          {ROLES.map((r) => (
            <button
              key={r.id}
              type="button"
              className={`role-item${r.id === role ? ' active' : ''}`}
              onClick={() => onRoleChange(r.id)}
            >
              <span className="role-name">{r.name}</span>
              <span className={`clearance-badge clearance-${r.clearance}`}>
                {r.badge}
              </span>
            </button>
          ))}
        </div>
        {activeRole && <p className="role-desc">{activeRole.description}</p>}
      </div>

      <div className="sidebar-section">
        <div className="sidebar-label">Document type</div>
        <div className="chip-group">
          {DOCUMENT_TYPES.map((type) => (
            <button
              key={type}
              type="button"
              className={`chip${activeTypes.includes(type) ? ' active' : ''}`}
              onClick={() => onToggleType(type)}
            >
              {type}
            </button>
          ))}
        </div>
      </div>

      <div className="sidebar-section">
        <div className="sidebar-label">Effective year</div>
        <select
          className="year-select"
          value={year}
          onChange={(e) => onYearChange(e.target.value)}
        >
          {EFFECTIVE_YEARS.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </div>

      <div className="sidebar-footer">
        Filters apply as a hard WHERE clause before vector search, not a
        post-hoc UI filter. Denied results are enforced server-side.
      </div>
    </aside>
  )
}
