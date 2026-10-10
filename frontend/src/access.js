export function validRole(role) {
  return role === 'junior' || role === 'senior';
}
export function canAccess(user, document) {
  return validRole(user?.role) && ['junior', 'senior'].includes(document?.level) && (user.role === 'senior' || document.level === 'junior');
}
export function filterDocuments(documents, user, {
  query = '',
  type = 'All types',
  year = 'All years',
  level = 'all'
} = {}) {
  const needle = query.trim().toLowerCase();
  return documents.filter(doc => canAccess(user, doc) && (!needle || `${doc.title} ${doc.description} ${doc.category}`.toLowerCase().includes(needle)) && (type === 'All types' || doc.type === type) && (year === 'All years' || String(doc.year) === year) && (level === 'all' || doc.level === level));
}
export function findExcerpts(documents, question) {
  const stopwords = new Set(['what', 'when', 'where', 'which', 'should', 'would', 'could', 'does', 'have', 'about', 'this', 'that', 'with', 'from', 'your', 'they', 'them', 'please']);
  const terms = question.toLowerCase().match(/[a-z0-9]+/g)?.filter(word => word.length > 3 && !stopwords.has(word)) || [];
  return documents.flatMap(doc => doc.content.split('\n\n').slice(1).map(text => ({
    id: doc.id,
    title: doc.title,
    text,
    score: terms.filter(term => text.toLowerCase().includes(term)).length
  }))).filter(hit => hit.score > 0).sort((a, b) => b.score - a.score).slice(0, 3);
}
