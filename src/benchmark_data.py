"""Deterministic fictional workload; no organizational or disclosure text is used."""
import random

TOPICS = [
    ('account security', 'enable multifactor authentication and rotate compromised credentials'),
    ('incident response', 'isolate affected hosts and preserve event logs'),
    ('database recovery', 'restore a snapshot and replay the transaction log'),
    ('release approval', 'collect peer review and verify rollback readiness'),
    ('capacity planning', 'compare available staffing with committed work'),
    ('employee onboarding', 'assign a buddy and provision approved tools'),
    ('customer support', 'triage tickets by impact and record resolution steps'),
    ('data retention', 'apply expiration rules and document deletion evidence'),
    ('vendor assessment', 'review security controls and service commitments'),
    ('access review', 'remove obsolete grants and verify resource ownership'),
    ('performance testing', 'measure tail latency and inspect saturation'),
    ('budget planning', 'reconcile forecasts with approved expenditure'),
    ('design review', 'check accessibility and validate user journeys'),
    ('project handover', 'record dependencies and assign follow-up owners'),
    ('backup verification', 'run a restore drill and compare checksums'),
    ('network maintenance', 'stage routing changes and check connectivity'),
    ('document classification', 'identify sensitive content and assign a clearance level'),
    ('quality assurance', 'reproduce failures and track regression coverage'),
    ('training delivery', 'publish learning materials and assess understanding'),
    ('service monitoring', 'inspect error rates and test alert escalation'),
]
CONTEXTS = ['a regional office', 'a remote team', 'a customer portal', 'an internal platform',
            'a research lab', 'a distribution centre', 'a mobile application', 'a finance team',
            'a manufacturing site', 'a shared service desk']
TRIGGERS = ['a scheduled quarterly review', 'an unexpected service interruption',
            'a new supplier agreement', 'a change of project ownership',
            'a regulatory reporting deadline', 'a rapid increase in demand',
            'a failed audit check', 'a planned system migration',
            'a newly reported defect', 'a team reorganization']
ACTIONS = ['Collect written approval before proceeding.', 'Run a small pilot before expanding.',
           'Record evidence in the change register.', 'Assign a second reviewer to verify completion.',
           'Notify the responsible owner after verification.']


def make_workload(size=10000, query_count=120, seed=None):
    """10,000 distinct template combinations, not replicated/noised vectors.

    Queries are separately worded but share the template distribution. This is a
    synthetic stress workload, not an independently sampled relevance dataset.
    """
    if not 1 <= query_count <= len(TOPICS)*len(CONTEXTS)*len(TRIGGERS):
        raise ValueError('query_count exceeds the unique query template space')
    rows = [f'Guidance on {topic} for {context}. Following {trigger}, {action}. {closing}'
            for topic, action in TOPICS for context in CONTEXTS
            for trigger in TRIGGERS for closing in ACTIONS]
    if not 1 <= size <= len(rows):
        raise ValueError(f'size must be between 1 and {len(rows)}')
    rng = random.Random(seed)
    rng.shuffle(rows)
    queries = []
    while len(queries) < query_count:
        topic, _ = rng.choice(TOPICS)
        query = f'How should {rng.choice(CONTEXTS)} handle {topic} after {rng.choice(TRIGGERS)}?'
        if query not in queries:
            queries.append(query)
    return rows[:size], queries
