import test from 'node:test'
import assert from 'node:assert/strict'
import { canAccess, filterDocuments, findExcerpts } from '../src/access.js'
import { documents } from '../src/data.js'
test('Junior cannot list or search Senior documents', () => {
  const user = { role: 'junior' }
  assert.equal(filterDocuments(documents, user).length, 6)
  for (const doc of documents.filter(doc => doc.level === 'senior')) assert.equal(canAccess(user, doc), false)
  assert.deepEqual(filterDocuments(documents, user, { query: 'strategy' }), [])
  assert.deepEqual(filterDocuments(documents, user, { level: 'senior' }), [])
})
test('Senior inherits Junior access and can filter either collection', () => {
  const user = { role: 'senior' }
  assert.equal(filterDocuments(documents, user).length, 9)
  assert.equal(filterDocuments(documents, user, { level: 'junior' }).length, 6)
  assert.equal(filterDocuments(documents, user, { level: 'senior' }).length, 3)
})
test('Unknown roles and document levels are denied by default', () => {
  for (const user of [null, {}, { role: 'admin' }, { role: 'Senior' }]) assert.equal(canAccess(user, documents[0]), false)
  assert.equal(canAccess({ role: 'senior' }, { level: 'secret' }), false)
  assert.equal(canAccess({ role: 'senior' }, null), false)
})
test('Combined filters find only matching documents', () => {
  assert.deepEqual(filterDocuments(documents, { role: 'junior' }, { query: '  VOICE ', year: '2025', type: 'Guide' }).map(doc => doc.id), ['brand-guide'])
  assert.deepEqual(filterDocuments(documents, { role: 'senior' }, { query: 'no-such-document' }), [])
})
test('Preview excerpts come only from the accessible collection', () => {
  const allowed = filterDocuments(documents, { role: 'junior' })
  const hits = findExcerpts(allowed, 'What security habits should I follow?')
  assert.ok(hits.length > 0)
  for (const hit of hits) assert.ok(allowed.some(doc => doc.id === hit.id && doc.content.includes(hit.text)))
  assert.deepEqual(findExcerpts(allowed, 'illustrative 2027 investment priorities'), [])
})
