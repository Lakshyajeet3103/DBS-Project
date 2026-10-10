import { useEffect, useRef, useState } from 'react';
import Icon from './Icons';
import { api, DEMO } from './api';
import { filterDocuments } from './access';
const navigation = [{
  id: 'overview',
  label: 'Overview',
  icon: 'grid'
}, {
  id: 'documents',
  label: 'Document library',
  icon: 'book'
}, {
  id: 'assistant',
  label: 'AI assistant',
  icon: 'spark'
}, {
  id: 'saved',
  label: 'Saved documents',
  icon: 'bookmark'
}];
const go = path => {
  window.location.hash = `/${path}`;
};
const readRoute = () => window.location.hash.replace(/^#\/?/, '') || 'overview';
const roleName = role => role === 'senior' ? 'Senior' : 'Junior';
const initials = name => name.split(' ').map(part => part[0]).slice(0, 2).join('');
const prettyDate = date => new Date(`${date}T12:00:00`).toLocaleDateString('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric'
});
function Brand({
  light = false
}) {
  return <div className={`brand ${light ? 'brand-light' : ''}`}><span className="brand-symbol"><Icon name="book" size={23} /></span><span>folio<span className="brand-dot">.</span></span></div>;
}
function Badge({
  level
}) {
  return <span className={`badge ${level}`}><Icon name={level === 'senior' ? 'shield' : 'user'} size={12} />{roleName(level)}</span>;
}
function ErrorNote({
  children
}) {
  return children ? <div className="error-note" role="alert"><Icon name="help" size={18} /><span>{children}</span></div> : null;
}
function Empty({
  icon = 'search',
  title,
  children,
  action
}) {
  return <div className="empty"><span className="empty-icon"><Icon name={icon} size={30} /></span><h3>{title}</h3><p>{children}</p>{action}</div>;
}
function Login({
  onLogin,
  initialError
}) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(initialError || '');
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      onLogin(await api.login(email, password));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  function fillDemo(role) {
    setEmail(`${role}@folio.demo`);
    setPassword(role === 'junior' ? 'Junior@123' : 'Senior@123');
    setError('');
  }
  return <main className="login-page">
    <section className="login-story">
      <Brand light />
      <div className="story-content"><span className="eyebrow light">A LITTLE CLARITY GOES A LONG WAY</span><h1>Your knowledge.<br />All in <em>one place.</em></h1><p>Find the right document. Ask a better question.<br />Make room for your best work.</p>
        <div className="story-art" aria-hidden="true"><div className="art-orbit orbit-one" /><div className="art-orbit orbit-two" /><div className="art-paper paper-back"><span /><span /><span /></div><div className="art-paper paper-front"><span className="art-file"><Icon name="book" size={28} /></span><strong>A shared space<br />for bright ideas.</strong><span /><span /><span className="short" /><div className="art-paper-foot"><span className="mini-dot" /> YOUR TEAM’S KNOWLEDGE</div></div><div className="art-chip"><Icon name="spark" size={18} /> A little help, a lot of possibility.</div><div className="art-star">✳</div></div>
      </div>
      <div className="story-footer"><Icon name="shield" size={16} /> The right knowledge, for the right people.</div>
    </section>
    <section className="login-panel"><div className="login-top"><span>YOUR TEAM’S KNOWLEDGE WORKSPACE</span>{DEMO && <span className="preview-label">LOCAL PREVIEW</span>}</div><div className="login-form-wrap"><span className="login-greeting">A GOOD PLACE TO START</span><h2>Welcome back.</h2><p className="muted">Sign in to your own corner of the knowledge base.</p>
      <form onSubmit={submit} className="login-form"><label htmlFor="email">Work email</label><input id="email" name="email" type="email" autoComplete="username" placeholder="you@company.com" required value={email} onChange={e => setEmail(e.target.value)} disabled={busy} /><label htmlFor="password">Password</label><div className="password-input"><input id="password" name="password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" placeholder="Enter your password" required value={password} onChange={e => setPassword(e.target.value)} disabled={busy} /><button type="button" className="icon-button" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword}><Icon name="eye" size={18} /></button></div><ErrorNote>{error}</ErrorNote><button className="button primary login-submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in to your workspace'}<Icon name="arrow" size={18} /></button></form>
      <div className="login-security"><Icon name="lock" size={16} /><p>Your access is assigned to your account.<br />Need a change? Contact your team lead.</p></div>
      {DEMO && <div className="demo-accounts"><div className="demo-heading"><span>TAKE A LOOK AROUND</span><span>Demo accounts</span></div><div className="demo-buttons"><button onClick={() => fillDemo('junior')}><span className="demo-avatar">J</span><span><strong>Junior workspace</strong><small>Shared team knowledge</small></span><Icon name="arrow" size={16} /></button><button onClick={() => fillDemo('senior')}><span className="demo-avatar senior-avatar">S</span><span><strong>Senior workspace</strong><small>Shared + senior knowledge</small></span><Icon name="arrow" size={16} /></button></div><p>Choose a demo account to fill the form. This preview uses fictional documents and simulated sign-in.</p></div>}
    </div><footer className="login-footer"><span>Thoughtfully connected. Simply useful.</span><span>Folio workspace © 2026</span></footer></section>
  </main>;
}
function DocumentCard({
  doc,
  saved,
  toggleSave
}) {
  return <article className="doc-card"><div className="doc-card-top"><span className={`document-icon tone-${doc.type.toLowerCase()}`}><Icon name={doc.type === 'Guide' ? 'book' : 'file'} size={23} /></span><button className={`icon-button save-button ${saved ? 'is-saved' : ''}`} onClick={() => toggleSave(doc.id)} aria-label={`${saved ? 'Unsave' : 'Save'} ${doc.title}`} aria-pressed={saved}><Icon name="bookmark" size={18} /></button></div><span className="doc-category">{doc.category}</span><button className="doc-title" onClick={() => go(`documents/${doc.id}`)}>{doc.title}</button><p>{doc.description}</p><div className="doc-meta"><span>{doc.type} <b>·</b> {doc.minutes} min read</span><Badge level={doc.level} /></div></article>;
}
function Overview({
  user,
  docs,
  saved,
  toggleSave
}) {
  const recent = [...docs].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 3);
  return <><div className="page-heading"><div><span className="eyebrow">YOUR WORKSPACE, AT A GLANCE</span><h1>A little knowledge.<br className="mobile-break" /> A lot of possibility.</h1><p>Welcome back, {user.name.split(' ')[0]}. Let’s find what you need.</p></div><span className="heading-date"><Icon name="clock" size={16} />{new Date().toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
          year: 'numeric',
          timeZone: 'Asia/Kolkata'
        })}</span></div>
    <section className="welcome-banner"><div><span className="eyebrow light">{user.role === 'senior' ? 'A WIDER PERSPECTIVE' : 'BUILT FOR YOUR NEXT STEP'}</span><h2>{user.role === 'senior' ? <>The full picture.<br />At your fingertips.</> : <>Good work starts<br />with the right knowledge.</>}</h2><p>{user.role === 'senior' ? 'Explore shared team resources and senior insights, together in one thoughtful workspace.' : 'Your team’s guides, ideas, and answers. Organized, accessible, and ready when you are.'}</p><button className="button cream" onClick={() => go('documents')}>Explore the library<Icon name="arrow" size={17} /></button></div><div className="banner-art" aria-hidden="true"><div className="banner-circle" /><div className="book-spine spine-one">IDEAS</div><div className="book-spine spine-two">KNOWLEDGE</div><div className="book-spine spine-three">POSSIBILITY</div><span className="banner-spark">✳</span><span className="banner-tiny">A PLACE TO KEEP GROWING</span></div></section>
    <div className="stats-grid"><div className="stat-card"><span className="stat-icon"><Icon name="book" /></span><div><span>Documents available</span><strong>{docs.length.toString().padStart(2, '0')}</strong></div><small>Ready to explore</small></div><div className="stat-card"><span className="stat-icon peach"><Icon name="bookmark" /></span><div><span>Saved for later</span><strong>{docs.filter(doc => saved.includes(doc.id)).length.toString().padStart(2, '0')}</strong></div><button className="text-button" onClick={() => go('saved')}>Your reading list <Icon name="arrow" size={14} /></button></div><div className="stat-card"><span className="stat-icon lavender"><Icon name="shield" /></span><div><span>Your access level</span><strong className="stat-role">{roleName(user.role)}</strong></div><small>{user.role === 'senior' ? 'Junior + Senior documents' : 'Junior documents'}</small></div></div>
    <div className="section-heading"><div><h2>Fresh off the shelf</h2><p>The latest additions to your knowledge space.</p></div><button className="text-button" onClick={() => go('documents')}>View all documents <Icon name="arrow" size={16} /></button></div><div className="document-grid">{recent.map(doc => <DocumentCard key={doc.id} doc={doc} saved={saved.includes(doc.id)} toggleSave={toggleSave} />)}</div>
    <section className="assistant-callout"><span className="assistant-mark"><Icon name="spark" size={28} /></span><div><h3>A question on your mind?</h3><p>Your assistant helps you find answers in the documents you can access.</p></div><button className="button secondary" onClick={() => go('assistant')}>Ask the assistant<Icon name="arrow" size={17} /></button></section>
  </>;
}
function Library({
  user,
  docs,
  saved,
  toggleSave,
  savedOnly = false
}) {
  const [query, setQuery] = useState('');
  const [type, setType] = useState('All types');
  const [year, setYear] = useState('All years');
  const [level, setLevel] = useState('all');
  const [sort, setSort] = useState('recent');
  const base = savedOnly ? docs.filter(doc => saved.includes(doc.id)) : docs;
  const filtered = filterDocuments(base, user, {
    query,
    type,
    year,
    level
  }).sort((a, b) => sort === 'recent' ? b.date.localeCompare(a.date) : a.title.localeCompare(b.title));
  function clearFilters() {
    setQuery('');
    setType('All types');
    setYear('All years');
    setLevel('all');
  }
  return <><div className="page-heading"><div><span className="eyebrow">{savedOnly ? 'KEEP THE GOOD ONES CLOSE' : 'A SHARED SPACE FOR WHAT WE KNOW'}</span><h1>{savedOnly ? 'Your reading list.' : 'The document library.'}</h1><p>{savedOnly ? 'Useful today. Worth coming back to tomorrow.' : 'Find a fresh perspective, a practical guide, or just the answer you need.'}</p></div><span className="count-chip">{base.length} documents</span></div><div className="library-toolbar"><label className="search-box"><Icon name="search" size={19} /><input aria-label="Search documents" placeholder="Search documents, topics, or keywords…" value={query} onChange={e => setQuery(e.target.value)} />{query && <button className="icon-button" onClick={() => setQuery('')} aria-label="Clear search"><Icon name="close" size={15} /></button>}</label><select aria-label="Document type" value={type} onChange={e => setType(e.target.value)}><option>All types</option>{[...new Set(docs.map(doc => doc.type))].sort().map(item => <option key={item}>{item}</option>)}</select><select aria-label="Document year" value={year} onChange={e => setYear(e.target.value)}><option>All years</option>{[...new Set(docs.map(doc => String(doc.year)))].sort().reverse().map(item => <option key={item}>{item}</option>)}</select></div><div className="library-subbar"><div className="filter-tabs" aria-label="Access level filter">{(user.role === 'senior' ? ['all', 'junior', 'senior'] : ['all']).map(item => <button key={item} aria-pressed={level === item} className={level === item ? 'active' : ''} onClick={() => setLevel(item)}>{item === 'all' ? 'All documents' : `${roleName(item)} documents`}</button>)}</div><label className="sort-label">Sort by <select aria-label="Sort documents" value={sort} onChange={e => setSort(e.target.value)}><option value="recent">Recently updated</option><option value="name">Name A–Z</option></select></label></div><p className="results-count" aria-live="polite">{filtered.length} {filtered.length === 1 ? 'document' : 'documents'}{query ? ` matching “${query}”` : ' in your workspace'}</p>{filtered.length ? <div className="document-grid library-grid">{filtered.map(doc => <DocumentCard key={doc.id} doc={doc} saved={saved.includes(doc.id)} toggleSave={toggleSave} />)}</div> : <Empty icon={savedOnly && !base.length ? 'bookmark' : 'search'} title={savedOnly && !base.length ? 'Make room for your favorites.' : 'No documents found.'} action={<button className="button secondary" onClick={savedOnly && !base.length ? () => go('documents') : clearFilters}>{savedOnly && !base.length ? 'Explore the library' : 'Clear filters'}</button>}>{savedOnly && !base.length ? 'Save a document with the bookmark icon and it will be waiting here.' : 'Try a different keyword or clear your filters to explore more.'}</Empty>}<div className="access-footnote"><Icon name="shield" size={15} />{user.role === 'senior' ? 'Your Senior access includes Junior and Senior documents.' : 'You’re viewing documents available to your Junior account.'}</div></>;
}
function DocumentView({
  id,
  user,
  saved,
  toggleSave
}) {
  const [doc, setDoc] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setDoc(null);
    setError('');
    api.document(id, user).then(data => {
      if (active) setDoc(data);
    }).catch(err => {
      if (active) setError(err.message);
    });
    return () => {
      active = false;
    };
  }, [id, user]);
  function download() {
    const url = URL.createObjectURL(new Blob([`${doc.title}\n\n${doc.content}`], {
      type: 'text/plain;charset=utf-8'
    }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${doc.id}.txt`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  if (error) return <Empty icon="lock" title="This page isn’t available to you." action={<button className="button primary" onClick={() => go('documents')}>Back to your library</button>}>{error}</Empty>;
  if (!doc) return <div className="loading-state" role="status">Opening your document…</div>;
  return <><button className="text-button back-link" onClick={() => go('documents')}>← Back to document library</button><div className="document-reader"><div className="reader-heading"><span className="eyebrow">{doc.category} / {doc.type}</span><h1>{doc.title}</h1><p>{doc.description}</p><div className="reader-meta"><Badge level={doc.level} /><span>{doc.author}</span><span>Updated {prettyDate(doc.date)}</span><span>{doc.minutes} min read</span></div></div><div className="reader-actions"><button className={`button secondary ${saved.includes(id) ? 'selected-button' : ''}`} onClick={() => toggleSave(id)}><Icon name="bookmark" size={17} />{saved.includes(id) ? 'Saved to your list' : 'Save for later'}</button><button className="button secondary" onClick={download}><Icon name="download" size={17} />Download text</button><button className="button primary" onClick={() => go(`assistant?document=${encodeURIComponent(id)}`)}><Icon name="spark" size={17} />Ask about this</button></div>{DEMO && <div className="reader-demo-note">Sample document · Created for the local preview</div>}<div className="reader-content">{(doc.content || '').split('\n\n').map((paragraph, i) => paragraph.length < 65 && !paragraph.includes('.') ? <h2 key={i}>{paragraph}</h2> : <p key={i}>{paragraph}</p>)}</div></div></>;
}
function Assistant({
  user,
  docs,
  documentId,
  messages,
  setMessages
}) {
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const endRef = useRef(null);
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  useEffect(() => {
    if (messages.length) endRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'end'
    });
  }, [messages, busy]);
  const context = documentId ? docs.find(doc => doc.id === documentId) : null;
  if (documentId && !context) return <Empty icon="lock" title="That document isn’t available." action={<button className="button primary" onClick={() => go('assistant')}>Open the assistant</button>}>Choose a document from your library to ask questions about it.</Empty>;
  async function send(text) {
    const message = text.trim();
    if (!message || busy) return;
    setInput('');
    setError('');
    setBusy(true);
    setMessages(previous => [...previous, {
      role: 'user',
      text: message
    }]);
    try {
      const response = await api.chat(message, user, documentId);
      if (active.current) setMessages(previous => [...previous, {
        role: 'assistant',
        text: response.reply,
        sources: response.sources
      }]);
    } catch (err) {
      if (active.current) {
        setError(err.message);
        setInput(message);
      }
    } finally {
      if (active.current) setBusy(false);
    }
  }
  const suggestions = context ? [`What does ${context.title} say about ${context.category.toLowerCase()}?`, 'What are the key steps in this document?'] : ['How do I get started in my first week?', 'What are our security best practices?', 'How do we plan and review projects?'];
  return <div className="assistant-page"><div className="page-heading"><div><span className="eyebrow">LESS SEARCHING. MORE UNDERSTANDING.</span><h1>A little help, on demand.</h1><p>Answers start with the knowledge in your workspace.</p></div><button className="button secondary" disabled={busy || !messages.length} onClick={() => {
        setMessages([]);
        setError('');
      }}><Icon name="chat" size={17} />New conversation</button></div><div className="chat-panel"><div className="chat-panel-header"><span className="assistant-mark small"><Icon name="spark" size={20} /></span><div><strong>Folio assistant</strong><span>{context ? context.title : user.role === 'senior' ? 'Junior + Senior document collection' : 'Junior document collection'}</span></div><span className="chat-scope"><Icon name="shield" size={14} />{roleName(user.role)} access</span></div>{context && <div className="context-strip"><Icon name="file" size={15} />Asking about: {context.title}<button className="text-button" disabled={busy} onClick={() => go('assistant')}>Clear</button></div>}<div className="chat-messages" aria-live="polite" aria-relevant="additions text">{!messages.length ? <div className="chat-welcome"><span className="chat-welcome-symbol"><Icon name="spark" size={35} /></span><h2>What would you like to know?</h2><p>Find an answer, untangle an idea, or explore something new.<br />I’ll start with the documents available to you.</p><div className="prompt-suggestions">{suggestions.map(text => <button key={text} onClick={() => send(text)}>{text}<Icon name="arrow" size={16} /></button>)}</div></div> : messages.map((message, index) => <div className={`message message-${message.role}`} key={index}><span className={`message-avatar ${message.role === 'assistant' ? 'assistant-avatar' : ''}`}>{message.role === 'assistant' ? <Icon name="spark" size={18} /> : initials(user.name)}</span><div><span className="message-author">{message.role === 'assistant' ? 'Folio assistant' : 'You'}</span><p>{message.text}</p>{message.sources?.length > 0 && <div className="message-sources">{message.sources.filter(source => docs.some(doc => doc.id === source.id)).map(source => <button key={source.id} onClick={() => go(`documents/${source.id}`)}><Icon name="file" size={13} />{source.title}<Icon name="chevron" size={12} /></button>)}</div>}</div></div>)}{busy && <div className="thinking" role="status"><span /><span /><span />Finding the right words…</div>}<div ref={endRef} /></div><div className="chat-composer-wrap"><ErrorNote>{error}</ErrorNote><form className="chat-composer" onSubmit={e => {
          e.preventDefault();
          send(input);
        }}><textarea aria-label="Your question" placeholder={context ? 'Ask a question about this document…' : 'Ask something about your documents…'} value={input} maxLength={4000} rows={2} onChange={e => setInput(e.target.value)} onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              send(input);
            }
          }} /><button className="send-button" aria-label="Send question" disabled={busy || !input.trim()}><Icon name="arrow" size={20} /></button></form><p className="composer-note">{DEMO ? 'Preview assistant · Finds matching sample passages. No AI service is called.' : 'Answers use your accessible documents. Verify important details in the source.'}</p></div></div></div>;
}
function AccessPage({
  user
}) {
  return <><div className="page-heading"><div><span className="eyebrow">CLEAR BOUNDARIES. SHARED KNOWLEDGE.</span><h1>Your workspace access.</h1><p>The right information, available when you need it.</p></div></div><section className="access-profile"><span className="profile-avatar large">{initials(user.name)}</span><div><h2>{user.name}</h2><p>{user.email}</p></div><Badge level={user.role} /></section><div className="access-grid">{['junior', 'senior'].map(level => {
        const allowed = user.role === 'senior' || level === 'junior';
        return <section className={`access-card ${allowed ? 'allowed' : ''}`} key={level}><span className="stat-icon"><Icon name={allowed ? 'check' : 'lock'} size={23} /></span><h2>{roleName(level)} collection</h2><p>{level === 'junior' ? 'Shared guides, team policies, templates, and everyday resources.' : 'Leadership reports, strategic plans, and senior team resources.'}</p><span className={`access-status ${allowed ? 'granted' : ''}`}>{allowed ? 'Included in your access' : 'Not included in your access'}</span></section>;
      })}</div><section className="access-explanation"><Icon name="shield" size={25} /><div><h3>Your assistant follows the same access.</h3><p>Document search and assistant answers should only include information your account is allowed to access. Your role is assigned by your organization. Contact your team lead if your responsibilities change.</p>{DEMO && <p className="demo-caveat">You’re exploring a frontend preview. Demo roles simulate the experience; real access protection requires the authenticated backend described in the integration guide.</p>}</div></section></>;
}
export default function App() {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(true);
  const [sessionError, setSessionError] = useState('');
  const [route, setRoute] = useState(readRoute);
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState([]);
  const [messages, setMessages] = useState([]);
  const [mobileNav, setMobileNav] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [reload, setReload] = useState(0);
  const [toast, setToast] = useState('');
  const mainRef = useRef(null);
  useEffect(() => {
    let active = true;
    api.session().then(data => {
      if (active) setUser(data);
    }).catch(err => {
      if (active) setSessionError(err.message);
    }).finally(() => {
      if (active) setBooting(false);
    });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    const handleRoute = () => {
      setRoute(readRoute());
      setMobileNav(false);
    };
    const expire = () => {
      setUser(null);
      setDocs([]);
      setMessages([]);
      setSessionError('Your session has expired. Please sign in again.');
    };
    window.addEventListener('hashchange', handleRoute);
    window.addEventListener('folio:session-expired', expire);
    return () => {
      window.removeEventListener('hashchange', handleRoute);
      window.removeEventListener('folio:session-expired', expire);
    };
  }, []);
  useEffect(() => {
    mainRef.current?.scrollTo(0, 0);
    if (user) mainRef.current?.focus({
      preventScroll: true
    });
  }, [route, user]);
  useEffect(() => {
    if (!user) return;
    let active = true;
    setLoading(true);
    setError('');
    setDocs([]);
    try {
      const stored = JSON.parse(localStorage.getItem(`folio-saved-${user.id}`) || '[]');
      setSaved(Array.isArray(stored) ? stored.filter(id => typeof id === 'string') : []);
    } catch {
      setSaved([]);
    }
    api.documents(user).then(data => {
      if (active) setDocs(data);
    }).catch(err => {
      if (active) setError(err.message);
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [user, reload]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(''), 2500);
    return () => clearTimeout(timer);
  }, [toast]);
  const page = route.split(/[/?]/)[0];
  const documentId = new URLSearchParams(route.split('?')[1]).get('document');
  useEffect(() => {
    setMessages([]);
  }, [documentId, user?.id]);
  function toggleSave(id) {
    const next = saved.includes(id) ? saved.filter(item => item !== id) : [...saved, id];
    setSaved(next);
    setToast(next.includes(id) ? 'Document saved to your reading list' : 'Document removed from your reading list');
    try {
      localStorage.setItem(`folio-saved-${user.id}`, JSON.stringify(next));
    } catch {
      setToast('Saved for this session. Browser storage is unavailable.');
    }
  }
  async function logout() {
    setLoggingOut(true);
    try {
      await api.logout();
      setUser(null);
      setDocs([]);
      setSaved([]);
      setMessages([]);
      setSessionError('');
      go('overview');
    } catch (err) {
      setToast(err.message);
    } finally {
      setLoggingOut(false);
    }
  }
  if (booting) return <div className="boot-screen"><Brand /><p>Opening your workspace…</p></div>;
  if (!user) return <Login initialError={sessionError} onLogin={account => {
    setUser(account);
    setSessionError('');
  }} />;
  let content;
  if (page === 'access') content = <AccessPage user={user} />;else if (!['overview', 'documents', 'saved', 'assistant'].includes(page)) content = <Empty title="We couldn’t find that page." action={<button className="button primary" onClick={() => go('overview')}>Back to overview</button>}>Let’s get you back to your workspace.</Empty>;else if (loading) content = <div className="loading-state" role="status">Gathering your documents…</div>;else if (error) content = <Empty icon="help" title="Your library couldn’t load." action={<button className="button primary" onClick={() => setReload(reload + 1)}>Try again</button>}>{error}</Empty>;else if (page === 'documents' && route.includes('/')) content = <DocumentView key={route} id={route.split('/')[1]} user={user} saved={saved} toggleSave={toggleSave} />;else if (page === 'documents' || page === 'saved') content = <Library key={page} user={user} docs={docs} saved={saved} toggleSave={toggleSave} savedOnly={page === 'saved'} />;else if (page === 'assistant') content = <Assistant key={documentId || 'all'} user={user} docs={docs} documentId={documentId} messages={messages} setMessages={setMessages} />;else content = <Overview user={user} docs={docs} saved={saved} toggleSave={toggleSave} />;
  return <div className="workspace"><a className="skip-link" href="#main-content" onClick={e => {
      e.preventDefault();
      mainRef.current?.focus();
    }}>Skip to content</a>{mobileNav && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setMobileNav(false)} />}<aside className={`sidebar ${mobileNav ? 'sidebar-open' : ''}`}><div className="sidebar-brand"><Brand /><button className="icon-button mobile-only" aria-label="Close navigation" onClick={() => setMobileNav(false)}><Icon name="close" /></button></div><div className="workspace-switch"><span className="workspace-initial">F</span><div><strong>Team workspace</strong><span>Knowledge, connected.</span></div><span className="workspace-dot" /></div><span className="nav-label">WORKSPACE</span><nav aria-label="Main navigation">{navigation.map(item => <a key={item.id} href={`#/${item.id}`} className={`nav-item ${page === item.id ? 'active' : ''}`} aria-current={page === item.id ? 'page' : undefined}><Icon name={item.icon} size={19} /><span>{item.label}</span>{item.id === 'saved' && saved.filter(id => docs.some(doc => doc.id === id)).length > 0 && <span className="nav-count">{saved.filter(id => docs.some(doc => doc.id === id)).length}</span>}{item.id === 'assistant' && <span className="new-label">ASK</span>}</a>)}</nav><div className="sidebar-bottom"><div className="access-note"><span className="access-note-heading"><Icon name="shield" size={17} />{roleName(user.role)} workspace</span><p>{user.role === 'senior' ? 'A full view of shared knowledge and senior insights.' : 'Your space for shared knowledge and everyday growth.'}</p><a href="#/access">About your access <Icon name="arrow" size={14} /></a></div><a className={`nav-item ${page === 'access' ? 'active' : ''}`} href="#/access" aria-current={page === 'access' ? 'page' : undefined}><Icon name="help" size={19} />My access</a><div className="sidebar-user"><span className="profile-avatar">{initials(user.name)}</span><div><strong>{user.name}</strong><span>{roleName(user.role)} member</span></div><button className="icon-button" aria-label="Sign out" title="Sign out" disabled={loggingOut} onClick={logout}><Icon name="logout" size={18} /></button></div></div></aside><div className="workspace-body"><header className="topbar"><div className="breadcrumbs"><button className="icon-button mobile-only" aria-label="Open navigation" aria-expanded={mobileNav} onClick={() => setMobileNav(true)}><Icon name="menu" /></button><span>Workspace</span><Icon name="chevron" size={13} /><strong>{navigation.find(item => item.id === page)?.label || (page === 'access' ? 'My access' : 'Page')}</strong></div><div className="topbar-right">{DEMO && <span className="preview-label"><span />Demo workspace</span>}<Badge level={user.role} /><span className="profile-avatar mini">{initials(user.name)}</span></div></header><main id="main-content" tabIndex={-1} ref={mainRef} className="main-content">{content}<footer className="workspace-footer"><span>A little more clarity. Every day.</span><span>Folio · Your knowledge, connected.</span></footer></main></div>{toast && <div className="toast" role="status"><Icon name="check" size={17} />{toast}</div>}</div>;
}
