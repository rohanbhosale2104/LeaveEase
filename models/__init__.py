from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # student, tg, cc, hod
    roll_no = db.Column(db.Integer)                  # only for students
    batch = db.Column(db.String(20))                 # e.g. "Batch 1", "Batch 3"
    attendance = db.Column(db.Float)                 # percentage
    # For routing approvals:
    tg_id = db.Column(db.Integer, db.ForeignKey("user.id"))    # student's TG
    cc_id = db.Column(db.Integer, db.ForeignKey("user.id"))    # student's CC

class LeaveRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    from_date = db.Column(db.Date, nullable=False)
    to_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    status_tg = db.Column(db.String(20), default="Pending")   # Pending/Approved/Rejected
    status_cc = db.Column(db.String(20), default="Pending")   # Pending/Approved/Rejected
    status_hod = db.Column(db.String(20), default="Pending")  # Pending/Approved/Rejected

    tg_action_date = db.Column(db.DateTime)
    cc_action_date = db.Column(db.DateTime)
    hod_action_date = db.Column(db.DateTime)

    # cached student info at time of request (for easy display)
    batch = db.Column(db.String(20))
    attendance = db.Column(db.Float)

    def overall_status(self):
        # simple logic: if any layer rejects -> Rejected; else if all Approved -> Approved; else Pending
        if self.status_tg == "Rejected" or self.status_cc == "Rejected" or self.status_hod == "Rejected":
            return "Rejected"
        if self.status_tg == "Approved" and self.status_cc == "Approved" and self.status_hod == "Approved":
            return "Approved"
        return "Pending"
