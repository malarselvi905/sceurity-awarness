from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Secret key for sessions
app.secret_key = "security_awareness_secret_key_2026"


# ============================================================
# MySQL Database Connection
# ============================================================

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="security_awareness"
    )


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        # Validation
        if not username or not email or not password:
            flash("All fields are required.")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("Password must contain at least 6 characters.")
            return redirect(url_for("register"))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check existing email
        cursor.execute(
            "SELECT id FROM users WHERE email = %s",
            (email,)
        )

        existing_user = cursor.fetchone()

        if existing_user:

            cursor.close()
            conn.close()

            flash("Email already registered.")
            return redirect(url_for("register"))

        # Hash password
        hashed_password = generate_password_hash(password)

        # Insert user
        cursor.execute(
            """
            INSERT INTO users
            (username, email, password, role)
            VALUES (%s, %s, %s, 'user')
            """,
            (
                username,
                email,
                hashed_password
            )
        )

        conn.commit()

        cursor.close()
        conn.close()

        flash("Registration successful. Please login.")

        return redirect(url_for("login"))

    return render_template("register.html")


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        # Validation
        if not email or not password:

            flash("Please enter email and password.")

            return redirect(url_for("login"))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Find user
        cursor.execute(
            "SELECT * FROM users WHERE email = %s",
            (email,)
        )

        user = cursor.fetchone()

        cursor.close()
        conn.close()

        # Verify password
        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]

            # Admin goes to admin dashboard
            if user["role"] == "admin":
                return redirect(url_for("admin"))

            # Normal user goes to dashboard
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.")

    return render_template("login.html")


# ============================================================
# USER DASHBOARD
# ============================================================

@app.route("/dashboard")
def dashboard():

    # Login check
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # User details
    cursor.execute(
        """
        SELECT username, email
        FROM users
        WHERE id = %s
        """,
        (session["user_id"],)
    )

    user = cursor.fetchone()

    # Quiz statistics
    cursor.execute(
        """
        SELECT
            COUNT(*) AS total_quizzes,
            COALESCE(MAX(score), 0) AS best_score,
            COALESCE(MAX(percentage), 0) AS best_percentage
        FROM quiz_results
        WHERE user_id = %s
        """,
        (session["user_id"],)
    )

    stats = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        "dashboard.html",
        user=user,
        stats=stats
    )


# ============================================================
# START QUIZ
# ============================================================

@app.route("/quiz")
def quiz():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get 5 random questions
    cursor.execute(
        """
        SELECT *
        FROM questions
        ORDER BY RAND()
        LIMIT 5
        """
    )

    questions = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "quiz.html",
        questions=questions
    )


# ============================================================
# SUBMIT QUIZ
# ============================================================

@app.route("/submit_quiz", methods=["POST"])
def submit_quiz():

    if "user_id" not in session:
        return redirect(url_for("login"))

    question_ids = request.form.getlist("question_ids")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    score = 0

    # Check each answer
    for question_id in question_ids:

        cursor.execute(
            """
            SELECT *
            FROM questions
            WHERE id = %s
            """,
            (question_id,)
        )

        question = cursor.fetchone()

        if question:

            user_answer = request.form.get(
                f"answer_{question_id}"
            )

            if user_answer == question["correct_answer"]:
                score += 1

    # Total questions
    total_questions = len(question_ids)

    # Calculate percentage
    if total_questions > 0:
        percentage = (score / total_questions) * 100
    else:
        percentage = 0

    # Save quiz result
    cursor.execute(
        """
        INSERT INTO quiz_results
        (
            user_id,
            score,
            total_questions,
            percentage
        )
        VALUES (%s, %s, %s, %s)
        """,
        (
            session["user_id"],
            score,
            total_questions,
            percentage
        )
    )

    conn.commit()

    cursor.close()
    conn.close()

    # Save last result in session
    session["last_score"] = score
    session["last_total"] = total_questions
    session["last_percentage"] = percentage

    # Security awareness level
    if percentage >= 80:
        level = "Excellent Security Awareness"

    elif percentage >= 60:
        level = "Good Security Awareness"

    elif percentage >= 40:
        level = "Average Security Awareness"

    else:
        level = "Needs Improvement"

    return render_template(
        "result.html",
        score=score,
        total=total_questions,
        total_questions=total_questions,
        percentage=percentage,
        level=level
    )


# ============================================================
# RESULT
# ============================================================

@app.route("/result")
def result():

    if "user_id" not in session:
        return redirect(url_for("login"))

    score = session.get("last_score", 0)
    total = session.get("last_total", 0)
    percentage = session.get("last_percentage", 0)

    # Calculate level
    if percentage >= 80:
        level = "Excellent Security Awareness"

    elif percentage >= 60:
        level = "Good Security Awareness"

    elif percentage >= 40:
        level = "Average Security Awareness"

    else:
        level = "Needs Improvement"

    return render_template(
        "result.html",
        score=score,
        total=total,
        total_questions=total,
        percentage=percentage,
        level=level
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin")
def admin():

    # Login check
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Admin check
    if session.get("role") != "admin":
        return "Access Denied - Admin Only", 403

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get all questions
    cursor.execute(
        """
        SELECT *
        FROM questions
        ORDER BY id DESC
        """
    )

    questions = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin.html",
        questions=questions
    )


# ============================================================
# ADMIN - ADD QUESTION
# ============================================================

@app.route("/admin/add_question", methods=["GET", "POST"])
def add_question():

    # Login check
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Admin check
    if session.get("role") != "admin":
        return "Access Denied - Admin Only", 403

    # POST request
    if request.method == "POST":

        question = request.form.get(
            "question",
            ""
        ).strip()

        option_a = request.form.get(
            "option_a",
            ""
        ).strip()

        option_b = request.form.get(
            "option_b",
            ""
        ).strip()

        option_c = request.form.get(
            "option_c",
            ""
        ).strip()

        option_d = request.form.get(
            "option_d",
            ""
        ).strip()

        correct_answer = request.form.get(
            "correct_answer",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        # Validation
        if not all([
            question,
            option_a,
            option_b,
            option_c,
            option_d,
            correct_answer,
            category
        ]):

            flash("All question fields are required.")

            return redirect(
                url_for("add_question")
            )

        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert question
        cursor.execute(
            """
            INSERT INTO questions
            (
                question,
                option_a,
                option_b,
                option_c,
                option_d,
                correct_answer,
                category
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                question,
                option_a,
                option_b,
                option_c,
                option_d,
                correct_answer,
                category
            )
        )

        conn.commit()

        cursor.close()
        conn.close()

        flash("Question added successfully.")

        return redirect(url_for("admin"))

    # GET request
    return render_template(
        "add_question.html"
    )


# ============================================================
# ADMIN - EDIT QUESTION
# ============================================================

@app.route(
    "/admin/edit_question/<int:question_id>",
    methods=["GET", "POST"]
)
def edit_question(question_id):

    # Login check
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Admin check
    if session.get("role") != "admin":
        return "Access Denied - Admin Only", 403

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # POST - update question
    if request.method == "POST":

        question = request.form.get(
            "question",
            ""
        ).strip()

        option_a = request.form.get(
            "option_a",
            ""
        ).strip()

        option_b = request.form.get(
            "option_b",
            ""
        ).strip()

        option_c = request.form.get(
            "option_c",
            ""
        ).strip()

        option_d = request.form.get(
            "option_d",
            ""
        ).strip()

        correct_answer = request.form.get(
            "correct_answer",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        cursor.execute(
            """
            UPDATE questions
            SET
                question = %s,
                option_a = %s,
                option_b = %s,
                option_c = %s,
                option_d = %s,
                correct_answer = %s,
                category = %s
            WHERE id = %s
            """,
            (
                question,
                option_a,
                option_b,
                option_c,
                option_d,
                correct_answer,
                category,
                question_id
            )
        )

        conn.commit()

        cursor.close()
        conn.close()

        flash("Question updated successfully.")

        return redirect(
            url_for("admin")
        )

    # GET - fetch question
    cursor.execute(
        """
        SELECT *
        FROM questions
        WHERE id = %s
        """,
        (question_id,)
    )

    question = cursor.fetchone()

    cursor.close()
    conn.close()

    if not question:
        return "Question not found", 404

    return render_template(
        "edit_question.html",
        question=question
    )


# ============================================================
# ADMIN - DELETE QUESTION
# ============================================================

@app.route(
    "/admin/delete_question/<int:question_id>",
    methods=["GET", "POST"]
)
def delete_question(question_id):

    # Login check
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Admin check
    if session.get("role") != "admin":
        return "Access Denied - Admin Only", 403

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM questions
        WHERE id = %s
        """,
        (question_id,)
    )

    conn.commit()

    cursor.close()
    conn.close()

    flash("Question deleted successfully.")

    return redirect(
        url_for("admin")
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    flash("You have been logged out.")

    return redirect(
        url_for("login")
    )


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )

