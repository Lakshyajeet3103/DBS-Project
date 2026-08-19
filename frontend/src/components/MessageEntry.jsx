export default function MessageEntry({ entry }) {
  if (entry.role === 'user') {
    return (
      <div className="entry user">
        <div className="bubble-user">{entry.text}</div>
      </div>
    )
  }

  if (entry.status === 'pending') {
    return (
      <div className="entry assistant">
        <div className="record">
          <div className="record-header">
            <span className="record-dot" />
            Docket
          </div>
          <div className="thinking">Searching retrieved chunks</div>
        </div>
      </div>
    )
  }

  if (entry.status === 'error') {
    return (
      <div className="entry assistant">
        <div className="status-banner">{entry.text}</div>
      </div>
    )
  }

  if (entry.denied) {
    return (
      <div className="entry assistant">
        <div className="record">
          <div className="record-header">
            <span className="record-dot denied" />
            Docket — Access Restricted
          </div>
          <div className="redaction-block">
            <div className="redaction-note">🔒 Retrieval blocked at the database layer</div>
            <div className="redaction-line w-full" />
            <div className="redaction-line w-80" />
            <div className="redaction-line w-60" />
            <div className="redaction-caption">
              {entry.text || 'This is not covered in the provided policy.'}
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="entry assistant">
      <div className="record">
        <div className="record-header">
          <span className="record-dot" />
          Docket
        </div>
        <div className="record-body">{entry.text}</div>
        {entry.citations?.length > 0 && (
          <div className="citations">
            {entry.citations.map((c) => (
              <span className="citation-chip" key={c}>
                § {c}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
