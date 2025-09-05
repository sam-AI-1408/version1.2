# app.py
import os
from datetime import datetime, timedelta
from random import sample as rand_sample

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    session,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)

# ----------------- APP & DB SETUP -----------------
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-not-for-prod")

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///Sam.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = "static/uploads"
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"

# Upload settings
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ----------------- MODELS -----------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(200), nullable=False)
    profile_pic = db.Column(db.String(200), nullable=True)
    quote = db.Column(db.String(300), nullable=False, default="Stay focused. Keep leveling up.")
    rank = db.Column(db.String(50), default="Bronze")
    level = db.Column(db.Integer, default=1)
    points = db.Column(db.Integer, default=0)
    strength = db.Column(db.Integer, default=50)
    health = db.Column(db.Integer, default=50)
    growth = db.Column(db.Integer, default=50)
    wisdom = db.Column(db.Integer, default=50)
    finance = db.Column(db.Integer, default=50)

    # Personal
    age = db.Column(db.Integer, nullable=True)
    height_cm = db.Column(db.Float, nullable=True)
    weight_kg = db.Column(db.Float, nullable=True)
    fitness_level = db.Column(db.String(50), default="Beginner")

    # Quest timestamps
    last_daily_quest = db.Column(db.DateTime, default=None)
    last_weekly_quest = db.Column(db.DateTime, default=None)
    last_monthly_quest = db.Column(db.DateTime, default=None)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    alarm_time = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", backref=db.backref("tasks", lazy=True))


class StudyLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    started_at = db.Column(db.String(50))
    ended_at = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<StudyLog {self.subject} - {self.duration} min>"


class Quest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # daily/weekly/monthly
    difficulty = db.Column(db.String(50), nullable=False)
    xp = db.Column(db.Integer, default=10)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ----------------- RANK/LEVEL/STATS UTIL -----------------
def get_rank(points: int) -> str:
    ranks = [
        ("E", 0, 99),
        ("E+", 100, 199),
        ("E++", 200, 299),
        ("D", 300, 499),
        ("D+", 500, 699),
        ("D++", 700, 899),
        ("C", 900, 1199),
        ("C+", 1200, 1499),
        ("C++", 1500, 1799),
        ("B", 1800, 2199),
        ("B+", 2200, 2599),
        ("B++", 2600, 2999),
        ("A", 3000, 3499),
        ("A+", 3500, 3999),
        ("A++", 4000, 4499),
        ("S", 4500, 4999),
        ("S+", 5000, 5999),
        ("SS", 6000, 6999),
        ("SS+", 7000, 7999),
        ("SSS", 8000, 8999),
        ("National Rank", 9000, 9999999),
    ]
    for rank, low, high in ranks:
        if low <= points <= high:
            return rank
    return "Unranked"


def get_level(points: int) -> int:
    level = 1
    thresholds = [50, 150, 300, 500, 750, 1050, 1400, 1800, 2250, 2750]
    for i, threshold in enumerate(thresholds, start=1):
        if points >= threshold:
            level = i + 1
    return level


def calculate_stats(user):
    base = user.points or 0
    # Simple derived stats — extend as you like
    completed_tasks = Task.query.filter_by(user_id=user.id, completed=True).count()
    completed_quests = Quest.query.filter_by(user_id=user.id, completed=True).count()
    completed_academics = StudyLog.query.filter_by(user_id=user.id).count()
    return {
        "strength": base // 10 + completed_tasks * 5,
        "finance": base // 20 + completed_academics * 3,
        "wisdom": base // 15 + completed_quests * 4,
        "growth": (completed_tasks + completed_academics + completed_quests) * 7,
        "mental": 50 + (base // 30),
    }


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ----------------- QUEST POOLS & REGEN CONFIG -----------------
# You can expand these pools with your preferred quests.
DEFAULT_POOLS = {
    "daily": [
        {"title": "Read 20 pages of a book", "category": "Academics", "type": "daily", "difficulty": "Easy", "xp": 15},
        {"title": "Practice coding for 30 minutes", "category": "Academics", "type": "daily", "difficulty": "Medium", "xp": 20},
        {"title": "Meditate for 10 minutes", "category": "Mental", "type": "daily", "difficulty": "Easy", "xp": 10},
    ],
    "weekly": [
        {"title": "Finish one small project", "category": "Project", "type": "weekly", "difficulty": "Hard", "xp": 80},
        {"title": "Workout 4 times this week", "category": "Physical", "type": "weekly", "difficulty": "Hard", "xp": 70},
    ],
    "monthly": [
        {"title": "Complete a mini-course", "category": "Academics", "type": "monthly", "difficulty": "Hard", "xp": 200},
        {"title": "Read a full book", "category": "Academics", "type": "monthly", "difficulty": "Medium", "xp": 150},
    ],
}

# How many to create per period
COUNTS = {"daily": 3, "weekly": 2, "monthly": 1}

# Seconds to wait before regenerating quests (approx)
REGEN = {
    "daily": 24 * 3600,  # 24 hours
    "weekly": 7 * 24 * 3600,  # 7 days
    "monthly": 30 * 24 * 3600,  # 30 days
}


def _choose_sample(pool, count):
    if not pool:
        return []
    if len(pool) <= count:
        return pool.copy()
    try:
        return rand_sample(pool, count)
    except ValueError:
        # fallback
        return pool[:count]


# ----------------- QUEST UTILITIES -----------------
def generate_quests_for_user(user_id, db_session=db, UserModel=User, QuestModel=Quest):
    """Generate quests for a user only when the regen period has passed."""
    user = db_session.session.get(UserModel, user_id) if hasattr(db_session, "session") else UserModel.query.get(user_id)
    if not user:
        return

    now = datetime.utcnow()
    periods = {
        "daily": (user.last_daily_quest, REGEN["daily"]),
        "weekly": (user.last_weekly_quest, REGEN["weekly"]),
        "monthly": (user.last_monthly_quest, REGEN["monthly"]),
    }

    for period, (last_time, regen_seconds) in periods.items():
        needs = False
        if not last_time:
            needs = True
        else:
            elapsed = (now - last_time).total_seconds()
            if elapsed >= regen_seconds:
                needs = True

        if not needs:
            continue

        # Delete old quests of this period
        old_quests = QuestModel.query.filter_by(user_id=user.id, type=period).all()
        for q in old_quests:
            db.session.delete(q)

        # Choose and add new quests from pool
        pool = DEFAULT_POOLS.get(period, [])
        chosen = _choose_sample(pool, COUNTS.get(period, 1))
        for q in chosen:
            quest = QuestModel(
                user_id=user.id,
                title=q["title"],
                category=q.get("category", "General"),
                type=q.get("type", period),
                difficulty=q.get("difficulty", "Medium"),
                xp=q.get("xp", 10),
                completed=False,
            )
            db.session.add(quest)

        # Personalized physical quest based on BMI (only daily)
        if period == "daily" and user.weight_kg and user.height_cm:
            try:
                bmi = user.weight_kg / ((user.height_cm / 100) ** 2)
                title, xp = "Standard Exercise", 10
                if bmi < 18.5:
                    title, xp = "Light Workout", 15
                elif bmi > 25:
                    title, xp = "Moderate Cardio", 20
                # don't duplicate same title for same day
                exists = QuestModel.query.filter_by(user_id=user.id, title=title, type="daily").first()
                if not exists:
                    q = QuestModel(
                        user_id=user.id,
                        title=title,
                        category="Physical",
                        type="daily",
                        difficulty="Medium",
                        xp=xp,
                        completed=False,
                    )
                    db.session.add(q)
            except Exception:
                pass

        # Update last time
        if period == "daily":
            user.last_daily_quest = now
        elif period == "weekly":
            user.last_weekly_quest = now
        elif period == "monthly":
            user.last_monthly_quest = now

    db.session.commit()


def get_user_quests(user_id, period=None, QuestModel=Quest):
    """Return all quests for user; if period provided filter by type."""
    q = QuestModel.query.filter_by(user_id=user_id)
    if period:
        q = q.filter_by(type=period)
    return q.order_by(QuestModel.created_at.desc()).all()


def complete_user_quest(user_id, quest_id, QuestModel=Quest, UserModel=User):
    quest = QuestModel.query.get(quest_id)
    if not quest or quest.user_id != user_id:
        return False, "Quest not found or not owned by user"
    if quest.completed:
        return False, "Quest already completed"
    quest.completed = True
    user = UserModel.query.get(user_id)
    user.points = (user.points or 0) + (quest.xp or 0)
    # Optionally update user level/rank fields
    user.level = get_level(user.points)
    user.rank = get_rank(user.points)
    db.session.commit()
    return True, {"points": user.points, "quest_id": quest.id}


# ----------------- ROUTES -----------------
@app.route("/")
def home():
    return render_template("index.html")


# ----- AUTH -----
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password_raw = request.form.get("password", "")
        quote = request.form.get("quote", "").strip() or "Stay focused. Keep leveling up."

        if not username or not password_raw:
            flash("Username and password required.", "danger")
            return render_template("register.html")

        if User.query.filter_by(username=username).first():
            flash("Username already exists. Please choose another one.", "danger")
            return render_template("register.html")

        password = generate_password_hash(password_raw)

        filename = None
        file = request.files.get("profile_pic")
        if file and file.filename:
            if not allowed_file(file.filename):
                flash("Invalid image type.", "danger")
                return render_template("register.html")
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        new_user = User(username=username, password=password, profile_pic=filename, quote=quote)
        db.session.add(new_user)
        db.session.commit()
        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for("profile"))
        else:
            flash("Invalid username or password", "danger")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Logged out successfully", "success")
    return redirect(url_for("login"))


# ----- PROFILE -----
@app.route("/profile")
@login_required
def profile():
    user_rank = get_rank(current_user.points or 0)
    user_level = get_level(current_user.points or 0)
    stats = calculate_stats(current_user)
    return render_template("dashboard/profile.html", user=current_user, rank=user_rank, level=user_level, stats=stats)


@app.route("/edit-profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        new_username = request.form.get("username", "").strip()
        if new_username and new_username != current_user.username:
            if User.query.filter_by(username=new_username).first():
                flash("Username already taken.", "danger")
                return redirect(url_for("edit_profile"))
            current_user.username = new_username

        new_quote = request.form.get("quote")
        if new_quote:
            current_user.quote = new_quote

        file = request.files.get("profile_pic")
        if file and file.filename:
            if not allowed_file(file.filename):
                flash("Invalid image type.", "danger")
                return redirect(url_for("edit_profile"))
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            current_user.profile_pic = filename

        current_user.age = request.form.get("age", type=int)
        current_user.height_cm = request.form.get("height_cm", type=float)
        current_user.weight_kg = request.form.get("weight_kg", type=float)
        current_user.fitness_level = request.form.get("fitness_level")

        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for("profile"))
    return render_template("dashboard/edit_profile.html", user=current_user)


# ----- TASKS -----
@app.route("/tasks")
@login_required
def tasks_page():
    tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.created_at.desc()).all()
    return render_template("dashboard/tasks.html", tasks=tasks, user=current_user)


@app.route("/add_task", methods=["POST"])
@login_required
def add_task():
    title = request.form.get("title", "").strip()
    time_str = request.form.get("time", "")
    alarm_time = None
    if time_str:
        try:
            alarm_time = datetime.strptime(time_str, "%Y-%m-%dT%H:%M")
        except ValueError:
            alarm_time = None
    if title:
        new_task = Task(title=title, alarm_time=alarm_time, user_id=current_user.id)
        db.session.add(new_task)
        db.session.commit()
    return redirect(url_for("tasks_page"))


@app.route("/complete_task/<int:task_id>", methods=["POST"])
@login_required
def complete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        return jsonify({"success": False, "error": "Forbidden"}), 403
    if not task.completed:
        task.completed = True
        current_user.points = (current_user.points or 0) + 10
        current_user.strength = (current_user.strength or 0) + 2
        db.session.commit()
    return jsonify(success=True, points=current_user.points)


@app.route("/delete_task/<int:task_id>", methods=["POST"])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        flash("You cannot delete someone else's task.", "danger")
        return redirect(url_for("tasks_page"))
    db.session.delete(task)
    db.session.commit()
    flash("Task deleted.", "success")
    return redirect(url_for("tasks_page"))


@app.route("/tasks_list")
@login_required
def tasks_list():
    tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.created_at.desc()).all()
    return jsonify([{"id": t.id, "title": t.title, "completed": t.completed} for t in tasks])


@app.route("/latest_task")
@login_required
def latest_task():
    task = Task.query.filter_by(user_id=current_user.id, completed=False).order_by(Task.created_at.desc()).first()
    return jsonify({"id": task.id, "title": task.title} if task else None)


# ----- ACADEMICS / STUDY LOGS -----
@app.route("/academics")
@login_required
def academics():
    return render_template("dashboard/academics.html", user=current_user)


@app.route("/add_study_log", methods=["POST"])
@login_required
def add_study_log():
    subject = request.form.get("subject", "Study")
    try:
        duration = int(request.form.get("duration", 0))
    except ValueError:
        duration = 0
    notes = request.form.get("notes", "")
    started_at = request.form.get("started_at", "")
    ended_at = request.form.get("ended_at", "")

    log = StudyLog(user_id=current_user.id, subject=subject, duration=duration, notes=notes, started_at=started_at, ended_at=ended_at)
    db.session.add(log)

    earned_points = max(1, duration // 5) if duration > 0 else 1
    current_user.points = (current_user.points or 0) + earned_points
    current_user.wisdom = (current_user.wisdom or 0) + (earned_points // 2)

    db.session.commit()
    return jsonify(success=True, points=current_user.points, earned=earned_points)


@app.route("/get_study_logs")
@login_required
def get_study_logs():
    logs = StudyLog.query.filter_by(user_id=current_user.id).order_by(StudyLog.created_at.desc()).all()
    data = [{"id": l.id, "subject": l.subject, "duration": l.duration, "notes": l.notes, "created_at": l.created_at.strftime("%Y-%m-%d %H:%M")} for l in logs]
    return jsonify(data)


@app.route("/delete_study_log/<int:log_id>", methods=["DELETE"])
@login_required
def delete_study_log(log_id):
    log = StudyLog.query.get_or_404(log_id)
    if log.user_id != current_user.id:
        return jsonify({"error": "Forbidden"}), 403
    db.session.delete(log)
    db.session.commit()
    return jsonify({"message": "Study log deleted successfully!"})


# ----- QUESTS -----
@app.route("/quests")
@login_required
def quests_page():
    # Ensure quests exist/up-to-date
    generate_quests_for_user(current_user.id)
    all_quests = get_user_quests(current_user.id)
    return render_template("dashboard/quests.html", quests=all_quests, user=current_user)


@app.route("/get_user_quests")
@login_required
def get_quests_api():
    period = request.args.get("period")
    quests = get_user_quests(current_user.id, period)
    quests_data = [
        {"id": q.id, "title": q.title, "category": q.category, "type": q.type, "difficulty": q.difficulty, "xp": q.xp, "completed": q.completed}
        for q in quests
    ]
    return jsonify(quests_data)


@app.route("/complete_quest", methods=["POST"])
@login_required
def complete_quest():
    data = request.json or {}
    quest_id = data.get("quest_id")
    if not quest_id:
        return jsonify({"success": False, "error": "Quest ID missing"}), 400
    success, result = complete_user_quest(current_user.id, int(quest_id))
    if not success:
        return jsonify({"success": False, "error": result}), 400
    return jsonify({"success": True, "points": result["points"], "quest_id": result["quest_id"]})


@app.route("/regenerate_quests")
@login_required
def regenerate_quests_api():
    generate_quests_for_user(current_user.id)
    return jsonify({"success": True, "message": "Quests regenerated successfully"})


# ----- VOICE COMMAND (simple parser) -----
@app.route("/voice_command", methods=["POST"])
@login_required
def voice_command():
    data = request.get_json() or {}
    cmd = (data.get("command") or "").lower().strip()
    response = {"success": False, "message": "Command not recognized."}

    try:
        if not cmd:
            return jsonify({"success": False, "message": "No command provided."}), 400

        # ========================
        # TASK COMMANDS
        # ========================
        if cmd.startswith("add task"):
            task_name = cmd.replace("add task", "", 1).strip()
            if task_name:
                new_task = Task(title=task_name, user_id=current_user.id)
                db.session.add(new_task)
                db.session.commit()
                response = {"success": True, "message": f"Task '{task_name}' added!"}
            else:
                response = {"success": False, "message": "No task name provided."}

        elif cmd.startswith("complete task"):
            rest = cmd.replace("complete task", "", 1).strip()
            try:
                task_id = int(rest)
                task = Task.query.get(task_id)
                if task and task.user_id == current_user.id:
                    task.completed = True
                    current_user.points = (current_user.points or 0) + 10
                    db.session.commit()
                    response = {"success": True, "message": f"Task {task_id} marked complete!", "points": current_user.points}
                else:
                    response = {"success": False, "message": "Task not found or not yours."}
            except Exception:
                response = {"success": False, "message": "Invalid task ID."}

        elif "show task" in cmd:
            tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.created_at.desc()).limit(5).all()
            task_list = ", ".join([t.title for t in tasks]) or "You have no tasks."
            response = {"success": True, "message": f"Your latest tasks are: {task_list}"}

        elif "open tasks" in cmd:
            response = {"success": True, "message": "Opening tasks page.", "redirect": url_for("tasks_page")}

        # ========================
        # QUEST COMMANDS
        # ========================
        elif cmd.startswith("complete quest"):
            rest = cmd.replace("complete quest", "", 1).strip()
            try:
                quest_id = int(rest)
                success, res = complete_user_quest(current_user.id, quest_id)
                if success:
                    response = {
                        "success": True,
                        "message": f"Quest {quest_id} completed!",
                        "points": res.get("points", current_user.points),
                    }
                else:
                    response = {"success": False, "message": res}
            except Exception:
                response = {"success": False, "message": "Invalid quest ID."}

        elif "open quests" in cmd:
            response = {"success": True, "message": "Opening quests page.", "redirect": url_for("quests_page")}

        # ========================
        # STUDY COMMANDS
        # ========================
        elif cmd.startswith("log study"):
            parts = cmd.split()
            if len(parts) >= 4:
                subject = parts[2]
                try:
                    duration = int(parts[3])
                    log = StudyLog(user_id=current_user.id, subject=subject, duration=duration, started_at="", ended_at="")
                    db.session.add(log)
                    earned = max(1, duration // 5)
                    current_user.points = (current_user.points or 0) + earned
                    db.session.commit()
                    response = {
                        "success": True,
                        "message": f"Logged {duration} min of {subject} study.",
                        "earned": earned,
                        "points": current_user.points,
                    }
                except ValueError:
                    response = {"success": False, "message": "Invalid duration."}
            else:
                response = {"success": False, "message": "Usage: log study <subject> <minutes>"}

        # ========================
        # PROFILE & POINTS
        # ========================
        elif "profile" in cmd or "open profile" in cmd:
            response = {"success": True, "message": "Opening your profile.", "redirect": url_for("profile")}

        elif "points" in cmd or "my points" in cmd:
            response = {"success": True, "message": f"You currently have {current_user.points or 0} points."}

        # ========================
        # GREETINGS & SMALL TALK
        # ========================
        elif "hello" in cmd or "hi" in cmd:
            response = {"success": True, "message": f"Hello {current_user.username}! How can I assist you today?"}

        elif "how are you" in cmd:
            response = {"success": True, "message": "I'm doing great! Ready to help you with your tasks."}

    except Exception as e:
        response = {"success": False, "message": f"Error processing command: {str(e)}"}

    return jsonify(response)



# ----- DEVELOPERS / VIEW OTHER PROFILES -----
@app.route("/developers")
@login_required
def developers():
    developers = [
    {"id": 1, "name": "S.Imam Basha", "role": "Coordinator", "description": "Leads project vision & integration.", "photo": "hameed.jpg"},
    {"id": 2, "name": "S.Abdul Hameed", "role": "Backend Developer", "description": "Handles database & APIs.", "photo": "member2.jpg"},
    {"id": 3, "name": "Sagabala Goutham", "role": "Frontend Developer", "description": "Designs UI/UX with neon theme.", "photo": "member3.jpg"},
    {"id": 4, "name": "M.Yashwanth Kumar", "role": "Tester", "description": "Ensures everything works smoothly.", "photo": "member4.jpg"},
]

    return render_template("dashboard/developers.html", developers=developers)


@app.route("/developer/<int:dev_id>")
@login_required
def view_developer(dev_id):
    dev_user = User.query.get(dev_id)
    if not dev_user:
        return "Developer not found", 404
    return render_template("dashboard/profile_dev.html", user=dev_user)


# ----------------- STARTUP -----------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
