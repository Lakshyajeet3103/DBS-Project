import { useEffect, useRef, useState } from 'react'
import Sidebar from './components/Sidebar'
import MessageEntry from './components/MessageEntry'
import { askDocket } from './api'
import { ROLES } from './config'

let idCounter = 0
const nextId = () => `e${++idCounter}`

export default function App() {
  const [role, setRole] = useState('analyst')
  const [activeTypes, setActiveTypes] = useState([])
  const [year, setYear] = useState('Any year')
  const [input, setInput] = useState('')
  const [entries, setEntries] = useState([])
  const [isBusy, setIsBusy] = useState(false)
  const threadRef = useRef(null)

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: 'smooth' })
  }, [entries])

  function toggleType(type) {
    setActiveTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    )
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const message = input.trim()
    if (!message || isBusy) return

    const userEntry = { id: nextId(), role: 'user', text: message }
    const pendingEntry = { id: nextId(), role: 'assistant', status: 'pending' }
    setEntries((prev) => [...prev, userEntry, pendingEntry])
    setInput('')
    setIsBusy(true)

    const filters = {
      document_type: activeTypes.length ? activeTypes : undefined,
      effective_year: year === 'Any year' ? undefined : Number(year),
    }

    try {
      const result = await askDocket({ message, role, filters })
      setEntries((prev) =>
        prev.map((entry) =>
          entry.id === pendingEntry.id
            ? {
                ...entry,
                status: 'done',
                text: result.reply,
                citations: result.citations,
                denied: result.denied,
              }
            : entry
        )
      )
    } catch (err) {
      setEntries((prev) =>
        prev.map((entry) =>
          entry.id === pendingEntry.id
            ? {
                ...entry,
                status: 'error',
                text: `Couldn't reach the backend — ${err.message}`,
              }
            : entry
        )
      )
    } finally {
      setIsBusy(false)
    }
  }

  const activeRole = ROLES.find((r) => r.id === role)

  return (
    <div className="app">
      <Sidebar
        role={role}
        onRoleChange={setRole}
        activeTypes={activeTypes}
        onToggleType={toggleType}
        year={year}
        onYearChange={setYear}
      />

      <div className="main">
        <header className="main-header">
          <h1>Compliance Query</h1>
          <span className="session-meta">
            role: {activeRole?.name} · clearance {activeRole?.badge}
          </span>
        </header>

        <div className="thread" ref={threadRef}>
          {entries.length === 0 && (
            <div className="empty-state">
              <h2>No entries yet</h2>
              <p>
                Ask about a policy, clause, or vendor contract. Answers cite the
                exact section they came from — or say plainly when a policy
                doesn't cover it.
              </p>
            </div>
          )}
          {entries.map((entry) => (
            <MessageEntry key={entry.id} entry={entry} />
          ))}
        </div>

        <div className="composer">
          <form className="composer-form" onSubmit={handleSubmit}>
            <input
              className="composer-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about PTO, a vendor SLA, a comp clause…"
              disabled={isBusy}
            />
            <button className="send-btn" type="submit" disabled={isBusy || !input.trim()}>
              {isBusy ? 'Retrieving…' : 'Ask'}
            </button>
          </form>
          <div className="composer-hint">
            Grounded strictly in retrieved chunks — no answer without a citation.
          </div>
        </div>
      </div>
    </div>
  )
}
