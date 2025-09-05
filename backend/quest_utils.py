# backend/quest_utils.py
import time
import random
from datetime import datetime

# ---------- CONFIG ----------
REGEN = {
    "daily": 24 * 60 * 60,
    "weekly": 7 * 24 * 60 * 60,
    "monthly": 28 * 24 * 60 * 60
}

COUNTS = {"daily": 3, "weekly": 2, "monthly": 1}
REWARDS = {"daily": 10, "weekly": 30, "monthly": 100}

# ---------- QUEST POOLS ----------
DEFAULT_POOLS = {
    "daily": [
        {"title": "Do 30 pushups", "category": "physical", "type": "daily", "difficulty": "Normal", "xp": 10},
        {"title": "Meditate 10 minutes", "category": "mental", "type": "daily", "difficulty": "Normal", "xp": 10},
        {"title": "Track today’s expenses", "category": "financial", "type": "daily", "difficulty": "Normal", "xp": 10}
    ],
    "weekly": [
        {"title": "Run total 5 km this week", "category": "physical", "type": "weekly", "difficulty": "Normal", "xp": 30},
        {"title": "Write a weekly journal", "category": "mental", "type": "weekly", "difficulty": "Normal", "xp": 30},
    ],
    "monthly": [
        {"title": "Complete 1000 pushups total", "category": "physical", "type": "monthly", "difficulty": "Hard", "xp": 100},
        {"title": "Save 10% of income this month", "category": "financial", "type": "monthly", "difficulty": "Normal", "xp": 100}
    ]
}

# ---------- HELPERS ----------
def rand_sample(lst, n):
    return random.sample(lst, min(n, len(lst)))

# ---------- QUEST FUNCTIONS ----------
def generate_quests_for_user(user_id, db, User, Quest):
    """
    Generate quests for a specific user and save them in DB.
    Only regenerate if the appropriate period has passed.
    """
    user = db.session.get(User, user_id)
    if not user:
        return

    now = datetime.utcnow()

    periods = {
        "daily": (user.last_daily_quest, REGEN["daily"]),
        "weekly": (user.last_weekly_quest, REGEN["weekly"]),
        "monthly": (user.last_monthly_quest, REGEN["monthly"])
    }

    for period, (last_time, regen_seconds) in periods.items():
        if not last_time or (now - last_time).total_seconds() >= regen_seconds:
            # Delete old quests of this period
            old_quests = Quest.query.filter_by(user_id=user.id, type=period).all()
            for q in old_quests:
                db.session.delete(q)

            # Add new quests
            chosen = rand_sample(DEFAULT_POOLS.get(period, []), COUNTS.get(period, 1))
            for q in chosen:
                quest = Quest(
                    user_id=user.id,
                    title=q["title"],
                    category=q["category"],
                    type=q["type"],
                    difficulty=q["difficulty"],
                    xp=q["xp"],
                    completed=False
                )
                db.session.add(quest)

            # Update last quest time
            if period == "daily":
                user.last_daily_quest = now
            elif period == "weekly":
                user.last_weekly_quest = now
            elif period == "monthly":
                user.last_monthly_quest = now

    # Personalized physical quest based on BMI (daily only)
    if user.weight_kg and user.height_cm:
        bmi = user.weight_kg / ((user.height_cm / 100) ** 2)
        title, xp = "Standard Exercise", 10
        if bmi < 18.5:
            title, xp = "Light Workout", 15
        elif bmi > 25:
            title, xp = "Moderate Cardio", 20

        # Only create if daily BMI quest doesn't exist
        exists = Quest.query.filter_by(user_id=user.id, title=title, type="daily").first()
        if not exists:
            quest = Quest(
                user_id=user.id,
                title=title,
                category="Physical",
                type="daily",
                difficulty="Medium",
                xp=xp,
                completed=False
            )
            db.session.add(quest)

    db.session.commit()



def get_user_quests(user_id, db, Quest, period=None):
    query = Quest.query.filter_by(user_id=user_id)
    if period:
        query = query.filter_by(type=period)
    return query.order_by(Quest.created_at.asc()).all()


def complete_user_quest(user_id, quest_id, db, User, Quest):
    quest = Quest.query.filter_by(id=quest_id, user_id=user_id).first()
    if not quest or quest.completed:
        return 0

    quest.completed = True
    db.session.commit()

    # Add XP to user
    user = db.session.get(User, user_id)
    if user:
        user.points += quest.xp
        db.session.commit()

    return quest.xp
