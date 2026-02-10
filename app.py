from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime
from config import Config
from models import db, User, LeaveRequest

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# ----------------- DB creation + seed ON STARTUP (Flask 2.3+ safe) -----------------

def seed_data():
    # Students (example names and attendance similar to PDF)
    s1 = User(
        name="Pooja Kale",
        role="student",
        roll_no=10,
        batch="Batch 1",
        attendance=73,
        tg_id=2,
        cc_id=3,
    )
    s2 = User(
        name="Amit Shinde",
        role="student",
        roll_no=5,
        batch="Batch 1",
        attendance=65,
        tg_id=2,
        cc_id=3,
    )
    s3 = User(
        name="Pradnya Jadhav",
        role="student",
        roll_no=19,
        batch="Batch 2",
        attendance=89,
        tg_id=2,
        cc_id=3,
    )
    # Teacher Guardian Batch 3
    tg = User(name="Prof. S. P. Jadhav", role="tg", batch="Batch 3")
    # Class Coordinator
    cc = User(name="Prof. A. B. Marathe", role="cc")
    # Head of Department
    hod = User(name="Dr. P. R. Sonawane", role="hod")

    db.session.add_all([s1, s2,s3, tg, cc, hod])
    db.session.commit()


# Run once when the app starts (instead of @before_first_request)
with app.app_context():
    db.create_all()
    if not User.query.first():
        seed_data()

# ----------------- Dummy login handling -----------------


def login_as(user_id):
    user = User.query.get(user_id)
    session["user_id"] = user.id
    session["role"] = user.role


# ----------------- Helpers -----------------


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return User.query.get(uid)


@app.context_processor
def inject_user():
    # lets you use current_user() in templates
    return dict(current_user=current_user)


# ----------------- Role selection page -----------------


@app.route("/", methods=["GET", "POST"])
def select_role():
    students = User.query.filter_by(role="student").all()
    tgs = User.query.filter_by(role="tg").all()
    ccs = User.query.filter_by(role="cc").all()
    hods = User.query.filter_by(role="hod").all()

    if request.method == "POST":
        role = request.form.get("role")
        user_id = int(request.form.get("user_id"))
        login_as(user_id)
        if role == "student":
            return redirect(url_for("student_dashboard"))
        if role == "tg":
            return redirect(url_for("tg_dashboard"))
        if role == "cc":
            return redirect(url_for("cc_dashboard"))
        if role == "hod":
            return redirect(url_for("hod_dashboard"))

    return render_template(
        "login_select_role.html",
        students=students,
        tgs=tgs,
        ccs=ccs,
        hods=hods,
    )


# ----------------- Student views -----------------


@app.route("/student/dashboard")
def student_dashboard():
    user = current_user()
    if not user or user.role != "student":
        return redirect(url_for("select_role"))

    recent_requests = (
        LeaveRequest.query.filter_by(student_id=user.id)
        .order_by(LeaveRequest.created_at.desc())
        .limit(5)
        .all()
    )

    below_threshold = user.attendance < 75

    return render_template(
        "student/dashboard.html",
        student=user,
        recent_requests=recent_requests,
        below_threshold=below_threshold,
    )


@app.route("/student/apply", methods=["GET", "POST"])
def student_apply_leave():
    user = current_user()
    if not user or user.role != "student":
        return redirect(url_for("select_role"))

    below_threshold = user.attendance < 75
    msg = None

    if request.method == "POST":
        if below_threshold:
            msg = "Your attendance is below 75%. You cannot apply for leave."
        else:
            reason = request.form.get("reason")
            from_date = datetime.strptime(
                request.form.get("from_date"), "%Y-%m-%d"
            ).date()
            to_date = datetime.strptime(
                request.form.get("to_date"), "%Y-%m-%d"
            ).date()

            lr = LeaveRequest(
                student_id=user.id,
                reason=reason,
                from_date=from_date,
                to_date=to_date,
                batch=user.batch,
                attendance=user.attendance,
            )
            db.session.add(lr)
            db.session.commit()
            return redirect(url_for("student_leave_history"))

    return render_template(
        "student/apply_leave.html",
        student=user,
        below_threshold=below_threshold,
        msg=msg,
    )


@app.route("/student/history")
def student_leave_history():
    user = current_user()
    if not user or user.role != "student":
        return redirect(url_for("select_role"))

    requests = (
        LeaveRequest.query.filter_by(student_id=user.id)
        .order_by(LeaveRequest.created_at.desc())
        .all()
    )

    return render_template(
        "student/leave_history.html",
        student=user,
        requests=requests,
    )


# ----------------- Teacher Guardian views -----------------


@app.route("/tg/dashboard")
def tg_dashboard():
    user = current_user()
    if not user or user.role != "tg":
        return redirect(url_for("select_role"))

    students = User.query.filter_by(tg_id=user.id, role="student").all()

    total_students = len(students)
    if students:
        avg_att = sum(s.attendance for s in students) / total_students
    else:
        avg_att = 0

    buckets = {"65": 0, "65-74": 0, "75-84": 0, "85-94": 0, "95-100": 0}
    for s in students:
        if s.attendance < 65:
            buckets["65"] += 1
        elif s.attendance < 75:
            buckets["65-74"] += 1
        elif s.attendance < 85:
            buckets["75-84"] += 1
        elif s.attendance < 95:
            buckets["85-94"] += 1
        else:
            buckets["95-100"] += 1

    pending_requests = (
        LeaveRequest.query.join(User, LeaveRequest.student_id == User.id)
        .filter(User.tg_id == user.id, LeaveRequest.status_tg == "Pending")
        .all()
    )

    return render_template(
        "tg/dashboard.html",
        tg=user,
        total_students=total_students,
        avg_att=round(avg_att, 1),
        buckets=buckets,
        pending_count=len(pending_requests),
    )


@app.route("/tg/leave-requests", methods=["GET", "POST"])
def tg_leave_requests():
    user = current_user()
    if not user or user.role != "tg":
        return redirect(url_for("select_role"))

    if request.method == "POST":
        lr_id = int(request.form.get("lr_id"))
        action = request.form.get("action")  # approve/reject
        lr = LeaveRequest.query.get(lr_id)
        if lr:
            lr.status_tg = "Approved" if action == "approve" else "Rejected"
            lr.tg_action_date = datetime.utcnow()
            db.session.commit()

    pending = (
        LeaveRequest.query.join(User, LeaveRequest.student_id == User.id)
        .filter(User.tg_id == user.id, LeaveRequest.status_tg == "Pending")
        .all()
    )

    return render_template(
        "tg/leave_requests.html",
        tg=user,
        pending=pending,
    )


@app.route("/tg/my-students")
def tg_my_students():
    user = current_user()
    if not user or user.role != "tg":
        return redirect(url_for("select_role"))

    students = User.query.filter_by(tg_id=user.id, role="student").all()
    return render_template(
        "tg/my_students.html",
        tg=user,
        students=students,
    )


# ----------------- Class Coordinator views -----------------


@app.route("/cc/dashboard")
def cc_dashboard():
    user = current_user()
    if not user or user.role != "cc":
        return redirect(url_for("select_role"))

    students = User.query.filter_by(role="student").all()
    total_students = len(students)

    buckets_all = {"65": 0, "65-74": 0, "75-84": 0, "85-94": 0, "95-100": 0}
    for s in students:
        if s.attendance < 65:
            buckets_all["65"] += 1
        elif s.attendance < 75:
            buckets_all["65-74"] += 1
        elif s.attendance < 85:
            buckets_all["75-84"] += 1
        elif s.attendance < 95:
            buckets_all["85-94"] += 1
        else:
            buckets_all["95-100"] += 1

    pending_cc = LeaveRequest.query.filter_by(
        status_tg="Approved", status_cc="Pending"
    ).all()

    approved_cc = LeaveRequest.query.filter_by(status_cc="Approved").count()

    return render_template(
        "cc/dashboard.html",
        cc=user,
        total_students=total_students,
        buckets_all=buckets_all,
        pending_cc_count=len(pending_cc),
        approved_cc=approved_cc,
    )


@app.route("/cc/pending-approval", methods=["GET", "POST"])
def cc_pending_approval():
    user = current_user()
    if not user or user.role != "cc":
        return redirect(url_for("select_role"))

    if request.method == "POST":
        lr_id = int(request.form.get("lr_id"))
        action = request.form.get("action")
        lr = LeaveRequest.query.get(lr_id)
        if lr:
            lr.status_cc = "Approved" if action == "approve" else "Rejected"
            lr.cc_action_date = datetime.utcnow()
            db.session.commit()

    pending_cc = LeaveRequest.query.filter_by(
        status_tg="Approved", status_cc="Pending"
    ).all()
    return render_template(
        "cc/pending_approval.html",
        cc=user,
        pending_cc=pending_cc,
    )


# ----------------- HOD views -----------------


@app.route("/hod/dashboard")
def hod_dashboard():
    user = current_user()
    if not user or user.role != "hod":
        return redirect(url_for("select_role"))

    students = User.query.filter_by(role="student").all()
    total_students = len(students)

    buckets_all = {"65": 0, "65-74": 0, "75-84": 0, "85-94": 0, "95-100": 0}
    for s in students:
        if s.attendance < 65:
            buckets_all["65"] += 1
        elif s.attendance < 75:
            buckets_all["65-74"] += 1
        elif s.attendance < 85:
            buckets_all["75-84"] += 1
        elif s.attendance < 95:
            buckets_all["85-94"] += 1
        else:
            buckets_all["95-100"] += 1

    pending = LeaveRequest.query.filter_by(status_hod="Pending").count()
    approved = LeaveRequest.query.filter_by(status_hod="Approved").count()
    rejected = LeaveRequest.query.filter_by(status_hod="Rejected").count()

    return render_template(
        "hod/dashboard.html",
        hod=user,
        total_students=total_students,
        buckets_all=buckets_all,
        pending=pending,
        approved=approved,
        rejected=rejected,
    )


@app.route("/hod/final-approval", methods=["GET", "POST"])
def hod_final_approval():
    user = current_user()
    if not user or user.role != "hod":
        return redirect(url_for("select_role"))

    if request.method == "POST":
        lr_id = int(request.form.get("lr_id"))
        action = request.form.get("action")
        lr = LeaveRequest.query.get(lr_id)
        if lr:
            lr.status_hod = "Approved" if action == "approve" else "Rejected"
            lr.hod_action_date = datetime.utcnow()
            db.session.commit()

    pending_hod = LeaveRequest.query.filter_by(
        status_tg="Approved", status_cc="Approved", status_hod="Pending"
    ).all()

    return render_template(
        "hod/final_approval.html",
        hod=user,
        pending_hod=pending_hod,
    )


@app.route("/hod/all-requests")
def hod_all_requests():
    user = current_user()
    if not user or user.role != "hod":
        return redirect(url_for("select_role"))

    requests = LeaveRequest.query.order_by(
        LeaveRequest.created_at.desc()
    ).all()
    return render_template(
        "hod/all_requests.html",
        hod=user,
        requests=requests,
    )


# ----------------- Logout -----------------


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("select_role"))


if __name__ == "__main__":
    app.run(debug=True)
