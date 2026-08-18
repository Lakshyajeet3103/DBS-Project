import { useEffect, useRef, useState } from 'react'

// Change this if your FastAPI backend runs somewhere other than localhost:8000
const API_BASE = 'http://127.0.0.1:8000'

function formatTime(date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isThinking, setIsThinking] = useState(false)
  const [connectionError, setConnectionError] = useState(false)
  const scrollRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, isThinking])

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`
    }
  }, [input])

  async function sendMessage(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || isThinking) return

    const userMessage = { role: 'user', text, time: new Date() }
    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setIsThinking(true)
    setConnectionError(false)

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })

      if (!res.ok) throw new Error(`Server responded ${res.status}`)

      const data = await res.json()
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: data.reply, time: new Date() },
      ])
    } catch (err) {
      setConnectionError(true)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: "Couldn't reach the backend. Make sure it's running — uvicorn main:app --reload — at " + API_BASE + '.',
          time: new Date(),
          isError: true,
        },
      ])
    } finally {
      setIsThinking(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(e)
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="wordmark">
          <span className="wordmark-glyph">§</span>
          <span className="wordmark-text">Marginalia</span>
        </div>
        <span className="header-sub">study assistant · grounded in your documents</span>
        <span className={`status ${connectionError ? 'status-error' : ''}`}>
          <span className="status-dot" />
          {connectionError ? 'backend unreachable' : 'ready'}
        </span>
      </header>

      <main className="thread" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="empty-state">
            <p className="empty-title">Ask something about your documents.</p>
            <p className="empty-body">
              Answers are drawn only from what's been indexed — nothing is guessed.
              If it isn't in your documents, you'll be told so plainly.
            </p>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`row row-${m.role}`}>
            {m.role === 'assistant' ? (
              <div className={`note note-assistant ${m.isError ? 'note-error' : ''}`}>
                <span className="note-rule" />
                <div className="note-body">
                  <p>{m.text}</p>
                  <span className="note-time">{formatTime(m.time)}</span>
                </div>
              </div>
            ) : (
              <div className="note note-user">
                <p>{m.text}</p>
                <span className="note-time">{formatTime(m.time)}</span>
              </div>
            )}
          </div>
        ))}

        {isThinking && (
          <div className="row row-assistant">
            <div className="note note-assistant note-thinking">
              <span className="note-rule" />
              <div className="note-body">
                <span className="thinking-dots">
                  <span />
                  <span />
                  <span />
                </span>
              </div>
            </div>
          </div>
        )}
      </main>

      <form className="composer" onSubmit={sendMessage}>
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about your documents…"
          rows={1}
        />
        <button type="submit" disabled={!input.trim() || isThinking}>
          Ask
        </button>
      </form>
    </div>
  )
}
