"""Database seeding utility for Folio."""
import sys
from core.auth import hash_password
from database.connection import Base, SessionLocal, engine
from database.models import Document, User

SEED_USERS = [
    {
        "id": "demo-junior",
        "email": "junior@folio.demo",
        "name": "Alex Morgan",
        "role": "junior",
        "raw_password": "Junior@123",
    },
    {
        "id": "demo-senior",
        "email": "senior@folio.demo",
        "name": "Taylor Reed",
        "role": "senior",
        "raw_password": "Senior@123",
    },
]

SEED_DOCUMENTS = [
    {
        "id": "getting-started",
        "title": "Your first week, made simple",
        "category": "Getting started",
        "type": "Guide",
        "year": "2026",
        "level": "junior",
        "date": "2026-10-06",
        "minutes": 4,
        "author": "People & Culture",
        "description": "A thoughtful introduction to our people, tools, and ways of working.",
        "content": (
            "Welcome to the team\n\n"
            "Start your first week by setting up your workspace and meeting your team lead. "
            "Your buddy is your first point of contact for everyday questions.\n\n"
            "Your first-week checklist\n\n"
            "Complete your profile, review the team handbook, and request access to the tools you need. "
            "Attend the team introduction on your first day and schedule a check-in with your buddy by Friday.\n\n"
            "Finding your footing\n\n"
            "Use the document library to find approved guides. Ask the assistant a question when you need a specific detail. "
            "Your workspace shows documents available to your access level."
        ),
    },
    {
        "id": "team-handbook",
        "title": "The team handbook",
        "category": "People & culture",
        "type": "Policy",
        "year": "2026",
        "level": "junior",
        "date": "2026-10-04",
        "minutes": 8,
        "author": "People & Culture",
        "description": "The everyday essentials: collaboration, communication, and working together.",
        "content": (
            "How we work together\n\n"
            "We keep decisions documented, share context early, and make room for focused work. "
            "Each team has a weekly planning session and a short Friday reflection.\n\n"
            "Communication\n\n"
            "Use team channels for shared questions. Record important decisions in a document with a clear owner and review date. "
            "Respect focus time and include context when requesting help.\n\n"
            "Working hours\n\n"
            "Coordinate availability with your team lead. Planned leave should be requested through your team lead at least five working days in advance."
        ),
    },
    {
        "id": "security-basics",
        "title": "Good habits. Safer work.",
        "category": "Security",
        "type": "Policy",
        "year": "2026",
        "level": "junior",
        "date": "2026-10-02",
        "minutes": 5,
        "author": "Security Team",
        "description": "A practical guide to keeping company information and your account secure.",
        "content": (
            "Protect your account\n\n"
            "Use a unique password and enable multi-factor authentication where available. "
            "Never share credentials or approve an unexpected sign-in request.\n\n"
            "Handling documents\n\n"
            "Only share documents with colleagues who have the required access. "
            "Do not copy restricted material into public tools. Report unexpected document access to the security team.\n\n"
            "Report an incident\n\n"
            "If you suspect a security incident, contact the security team immediately. "
            "Include what happened and when, but do not forward passwords or sensitive files."
        ),
    },
    {
        "id": "project-playbook",
        "title": "From idea to delivery",
        "category": "Engineering",
        "type": "Playbook",
        "year": "2026",
        "level": "junior",
        "date": "2026-09-28",
        "minutes": 6,
        "author": "Engineering",
        "description": "Our shared approach to planning, reviewing, and shipping useful work.",
        "content": (
            "Start with the problem\n\n"
            "Every project starts with a problem statement, an owner, and a measurable outcome. "
            "Break the work into small milestones that can be reviewed independently.\n\n"
            "Review and release\n\n"
            "Request a peer review before merging a change. Document testing and known limitations. "
            "The project owner coordinates release approval and verifies the result after delivery.\n\n"
            "Retrospectives\n\n"
            "At the end of a milestone, capture what worked, what did not, and one concrete improvement for the next cycle."
        ),
    },
    {
        "id": "brand-guide",
        "title": "A little guide to our voice",
        "category": "Design",
        "type": "Guide",
        "year": "2025",
        "level": "junior",
        "date": "2025-12-12",
        "minutes": 3,
        "author": "Design Studio",
        "description": "Write clearly, stay human, and make every interaction feel considered.",
        "content": (
            "Our voice\n\n"
            "Write like a helpful colleague. Use short sentences, familiar words, and specific examples. "
            "Start with the information the reader needs most.\n\n"
            "Design principles\n\n"
            "Create clear hierarchy and generous spacing. Use accessible contrast, visible keyboard focus, and meaningful labels. "
            "Help people recover when something goes wrong.\n\n"
            "Before publishing\n\n"
            "Read your work aloud, verify details, and ask someone unfamiliar with the topic to review it."
        ),
    },
    {
        "id": "review-template",
        "title": "A better project review",
        "category": "Engineering",
        "type": "Template",
        "year": "2025",
        "level": "junior",
        "date": "2025-11-20",
        "minutes": 3,
        "author": "Engineering",
        "description": "A reusable structure for sharing progress, decisions, and next steps.",
        "content": (
            "Project review template\n\n"
            "Summary: Describe the problem and the outcome in two sentences.\n\n"
            "Progress: List completed milestones and link to the supporting work.\n\n"
            "Decisions: Record the decision, its owner, and the reason behind it.\n\n"
            "Next steps: Assign an owner and a due date to each action. Highlight dependencies and unresolved questions."
        ),
    },
    {
        "id": "leadership-strategy",
        "title": "The road ahead: 2027 strategy",
        "category": "Leadership",
        "type": "Report",
        "year": "2026",
        "level": "senior",
        "date": "2026-10-07",
        "minutes": 10,
        "author": "Leadership Team",
        "description": "Priorities, investment themes, and the decisions shaping our next chapter.",
        "content": (
            "Leadership planning — fictional preview\n\n"
            "Our illustrative 2027 strategy focuses on a reliable product experience, clearer customer onboarding, and sustainable team growth.\n\n"
            "Investment priorities\n\n"
            "Prioritize platform reliability in the first quarter. Evaluate onboarding improvements through a limited pilot before wider rollout. "
            "Review staffing needs against confirmed project commitments.\n\n"
            "Decision cadence\n\n"
            "Leadership reviews progress monthly. Each initiative requires an accountable owner, a budget proposal, and a measurable outcome before approval."
        ),
    },
    {
        "id": "resource-planning",
        "title": "Resource planning framework",
        "category": "Leadership",
        "type": "Playbook",
        "year": "2026",
        "level": "senior",
        "date": "2026-09-30",
        "minutes": 7,
        "author": "Operations",
        "description": "Balance capacity, priorities, and investment across your teams.",
        "content": (
            "Capacity planning — fictional preview\n\n"
            "Review team capacity before accepting new commitments. Reserve capacity for maintenance, support, and planned leave.\n\n"
            "Quarterly planning\n\n"
            "Team leads submit resource requests with expected outcomes and dependencies. "
            "Senior reviewers compare requests against the agreed priorities and document allocation decisions.\n\n"
            "Escalation\n\n"
            "When demand exceeds capacity, reduce scope or adjust timelines before adding new commitments. "
            "Escalate unresolved conflicts to the leadership review."
        ),
    },
    {
        "id": "quarterly-review",
        "title": "Q3 business review",
        "category": "Leadership",
        "type": "Report",
        "year": "2026",
        "level": "senior",
        "date": "2026-09-25",
        "minutes": 9,
        "author": "Operations",
        "description": "An illustrative overview of quarterly performance and lessons learned.",
        "content": (
            "Quarterly review — fictional preview\n\n"
            "This sample report demonstrates Senior document access. It contains no real company performance data.\n\n"
            "Observations\n\n"
            "Teams reported that smaller milestones made reviews easier. Cross-team dependencies remained a planning challenge.\n\n"
            "Follow-up actions\n\n"
            "Introduce a shared dependency review during planning and assign an owner to each cross-team commitment. "
            "Revisit the process at the next quarterly review."
        ),
    },
]


def seed_database():
    """Create all tables and insert demo users and canonical documents."""
    print("Creating database tables if not exist...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 1. Seed Users
        for user_data in SEED_USERS:
            existing = db.query(User).filter(User.email == user_data["email"]).first()
            if not existing:
                print(f"Creating user: {user_data['email']} ({user_data['role']})")
                new_user = User(
                    id=user_data["id"],
                    email=user_data["email"],
                    name=user_data["name"],
                    role=user_data["role"],
                    password_hash=hash_password(user_data["raw_password"]),
                )
                db.add(new_user)
            else:
                # Update password hash and role to guarantee consistency
                existing.name = user_data["name"]
                existing.role = user_data["role"]
                existing.password_hash = hash_password(user_data["raw_password"])

        # 2. Seed Documents
        for doc_data in SEED_DOCUMENTS:
            existing = db.query(Document).filter(Document.id == doc_data["id"]).first()
            if not existing:
                print(f"Creating document: {doc_data['id']} [{doc_data['level']}]")
                new_doc = Document(**doc_data)
                db.add(new_doc)
            else:
                for k, v in doc_data.items():
                    setattr(existing, k, v)

        db.commit()
        print("Database seeding completed successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
