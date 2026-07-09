from flask import Flask, request, jsonify, render_template_string
import anthropic
import sqlite3
import os
import subprocess
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "checkins.db")

# Mailtrap SMTP credentials — loaded from .env
SMTP_HOST = os.getenv("SMTP_HOST", "sandbox.smtp.mailtrap.io")
SMTP_PORT = int(os.getenv("SMTP_PORT", 2525))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "clinic@medicalcenter.com")
SENDER_NAME = os.getenv("SENDER_NAME", "Medical Center")

def get_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        try:
            result = subprocess.run(
                ["bash", "-lc", "echo $ANTHROPIC_API_KEY"],
                capture_output=True, text=True
            )
            key = result.stdout.strip()
        except Exception:
            pass
    return key

client = anthropic.Anthropic(api_key=get_api_key())

SUMMARY_PROMPT = """You are a medical communication specialist.

Your job is to take a doctor's structured clinical notes and convert them into a warm, easy-to-understand After Visit Summary for the patient.

Guidelines:
- Use simple, plain language — NO medical jargon
- Be warm, caring and reassuring in tone
- Include all important information: diagnosis, medications, follow-up
- Format it clearly so the patient can easily reference it later
- End with a warm closing and the clinic's contact reminder

Format the summary as follows:

Dear [Patient Name],

Thank you for visiting us today. Here is a summary of your visit:

VISIT DETAILS:
[Date, Doctor name]

WHAT WE DISCUSSED:
[Plain language explanation of chief complaint and symptoms]

DIAGNOSIS:
[Simple explanation of the diagnosis]

YOUR TREATMENT PLAN:
[Medications with simple instructions, any procedures]

FOLLOW-UP INSTRUCTIONS:
[When to return, what to watch for, warning signs]

IMPORTANT REMINDERS:
[Key things to remember]

We wish you a speedy recovery. If you have any questions or concerns, please don't hesitate to contact our office.

Warm regards,
[Doctor Name]
Medical Center
"""

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        try:
            conn.execute("ALTER TABLE checkins ADD COLUMN after_visit_summary TEXT DEFAULT NULL")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE checkins ADD COLUMN summary_sent_at TEXT DEFAULT NULL")
        except Exception:
            pass

def get_completed_patients():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM checkins
            WHERE room_status = 'visit_done'
            AND structured_notes IS NOT NULL
            ORDER BY visit_completed_at DESC
        """).fetchall()
    return [dict(r) for r in rows]

def get_patient(patient_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM checkins WHERE id=?", (patient_id,)).fetchone()
    return dict(row) if row else None

def save_summary(patient_id, summary):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            UPDATE checkins SET after_visit_summary=?, summary_sent_at=?
            WHERE id=?
        """, (summary, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), patient_id))
        conn.commit()

def send_email(to_email, patient_name, doctor_name, summary_text):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Your After Visit Summary — {datetime.now().strftime('%B %d, %Y')}"
    msg['From'] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg['To'] = to_email

    # Plain text version
    text_part = MIMEText(summary_text, 'plain')

    # HTML version
    html_content = f"""
    <html>
    <body style="font-family: 'Segoe UI', sans-serif; background: #f0f4f8; padding: 30px;">
        <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 14px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.08);">
            <div style="background: linear-gradient(135deg, #1a5276, #2c7bb6); padding: 28px 32px; color: white;">
                <h1 style="margin:0; font-size:22px;">🏥 Medical Center</h1>
                <p style="margin:6px 0 0; opacity:0.85; font-size:14px;">After Visit Summary</p>
            </div>
            <div style="padding: 28px 32px; color: #1a3a4a; line-height: 1.8; font-size: 14px;">
                <pre style="white-space: pre-wrap; font-family: 'Segoe UI', sans-serif; font-size:14px; color:#1a3a4a;">{summary_text}</pre>
            </div>
            <div style="background: #f8fbfe; padding: 18px 32px; font-size: 12px; color: #64748b; border-top: 1px solid #e0eef5;">
                This summary is for your personal reference. Please keep it for your records.
                <br>© {datetime.now().year} Medical Center. All rights reserved.
            </div>
        </div>
    </body>
    </html>
    """
    html_part = MIMEText(html_content, 'html')

    msg.attach(text_part)
    msg.attach(html_part)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())

init_db()

# ── HTML TEMPLATE ─────────────────────────────────────────────

SUMMARY_PANEL = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>After Visit Summary Agent</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', sans-serif; background: #f0f4f8; padding: 24px; }
        h1 { font-size: 20px; color: #1a3a4a; margin-bottom: 4px; }
        .subtitle { font-size: 13px; color: #64748b; margin-bottom: 20px; }

        .nav { display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }
        .nav a { text-decoration: none; padding: 8px 18px; border-radius: 8px; font-size: 13px; font-weight: 600; }
        .nav a.active { background: #7e22ce; color: white; }
        .nav a:not(.active) { background: white; color: #7e22ce; border: 1.5px solid #7e22ce; }

        .grid { display: grid; grid-template-columns: 280px 1fr; gap: 20px; }

        .patient-list { background: white; border-radius: 12px; padding: 16px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
        .patient-list h2 { font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 14px; }
        .patient-card { border-radius: 9px; padding: 12px 14px; cursor: pointer; border: 1.5px solid #e2e8f0; margin-bottom: 8px; transition: all 0.15s; }
        .patient-card:hover { border-color: #7e22ce; background: #faf5ff; }
        .patient-card.selected { border-color: #7e22ce; background: #faf5ff; }
        .patient-name { font-size: 14px; font-weight: 700; color: #1a3a4a; }
        .patient-meta { font-size: 11px; color: #64748b; margin-top: 3px; }
        .badge-done { background: #7e22ce; color: white; border-radius: 20px; padding: 2px 8px; font-size: 10px; font-weight: 600; margin-top: 5px; display: inline-block; }
        .empty { color: #94a3b8; font-size: 13px; text-align: center; padding: 20px; }

        .summary-area { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
        .patient-header { background: #faf5ff; border-radius: 9px; padding: 14px 16px; margin-bottom: 18px; display: none; border-left: 4px solid #7e22ce; }
        .patient-header h3 { font-size: 15px; font-weight: 700; color: #1a3a4a; }
        .patient-header p { font-size: 12px; color: #64748b; margin-top: 3px; }

        .btn-row { display: flex; gap: 10px; margin-bottom: 18px; flex-wrap: wrap; }
        .btn { border: none; border-radius: 9px; padding: 11px 22px; font-size: 13px; font-weight: 600; cursor: pointer; transition: opacity 0.2s; }
        .btn:hover { opacity: 0.88; }
        .btn-generate { background: linear-gradient(135deg, #7e22ce, #6b21a8); color: white; }
        .btn-email    { background: linear-gradient(135deg, #2c7bb6, #1a5276); color: white; display: none; }
        .btn-print    { background: linear-gradient(135deg, #27ae60, #1e8449); color: white; display: none; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }

        .email-badge { background: #dbeafe; color: #1d4ed8; border-radius: 6px; padding: 3px 10px; font-size: 11px; font-weight: 600; margin-left: 8px; }
        .no-email-badge { background: #f1f5f9; color: #64748b; border-radius: 6px; padding: 3px 10px; font-size: 11px; }

        .summary-box {
            background: #faf5ff; border: 1.5px solid #d8b4fe;
            border-radius: 9px; padding: 20px 24px;
            font-size: 13px; color: #1a3a4a; line-height: 1.9;
            white-space: pre-wrap; display: none;
            margin-bottom: 16px;
        }

        .success-msg { border-radius: 8px; padding: 12px 16px; font-size: 13px; font-weight: 600; display: none; margin-top: 14px; }
        .success-email { background: #eff6ff; border: 1px solid #bfdbfe; color: #1d4ed8; }
        .success-print { background: #f0fdf4; border: 1px solid #86efac; color: #15803d; }

        .placeholder-msg { color: #94a3b8; font-size: 14px; text-align: center; padding: 60px 20px; }

        @media print {
            .nav, .btn-row, .patient-list, h1, .subtitle, .patient-header { display: none !important; }
            body { background: white; padding: 0; }
            .grid { display: block; }
            .summary-area { box-shadow: none; padding: 0; }
            .summary-box { display: block !important; border: none; background: white; }
        }
    </style>
</head>
<body>
    <h1>📋 After Visit Summary Agent</h1>
    <p class="subtitle">Generate and send patient After Visit Summaries</p>

    <div class="nav">
        <a href="/summary" class="active">Summary Agent</a>
        <a href="http://localhost:5002/doctor">Doctor Notes</a>
        <a href="http://localhost:5001/nurse">Nurse Panel</a>
        <a href="http://localhost:5000/records">All Records</a>
    </div>

    <div class="grid">
        <!-- Patient List -->
        <div class="patient-list">
            <h2>Visit Completed ({{ patients|length }})</h2>
            {% if patients %}
                {% for p in patients %}
                <div class="patient-card" onclick="selectPatient(
                    {{ p.id }},
                    '{{ p.first_name }} {{ p.last_name }}',
                    '{{ p.doctor_name }}',
                    '{{ p.email or '' }}',
                    '{{ p.appointment_time }}'
                )">
                    <div class="patient-name">{{ p.first_name }} {{ p.last_name }}</div>
                    <div class="patient-meta">{{ p.doctor_name }} · {{ p.appointment_time }}</div>
                    <span class="badge-done">✓ Visit Done</span>
                </div>
                {% endfor %}
            {% else %}
                <p class="empty">No completed visits yet.<br>Complete a visit in Doctor Notes first.</p>
            {% endif %}
        </div>

        <!-- Summary Area -->
        <div class="summary-area">
            <div class="patient-header" id="patientHeader">
                <h3 id="patientName">—</h3>
                <p id="patientMeta">—</p>
            </div>

            <div id="placeholder" class="placeholder-msg">
                👈 Select a patient to generate their After Visit Summary
            </div>

            <div id="summaryForm" style="display:none;">
                <div class="btn-row">
                    <button class="btn btn-generate" id="generateBtn" onclick="generateSummary()">
                        🤖 Generate After Visit Summary
                    </button>
                    <button class="btn btn-email" id="emailBtn" onclick="sendEmail()">
                        📧 Send to Patient Email
                    </button>
                    <button class="btn btn-print" id="printBtn" onclick="window.print()">
                        🖨️ Print Summary
                    </button>
                </div>

                <div class="summary-box" id="summaryBox"></div>
                <div class="success-msg success-email" id="emailSuccess">✅ Summary sent to patient's email successfully!</div>
                <div class="success-msg success-print" id="printSuccess">✅ Summary sent to printer!</div>
            </div>
        </div>
    </div>

<script>
let currentPatientId = null;
let currentEmail = '';
let summaryText = '';

function selectPatient(id, name, doctor, email, appt) {
    currentPatientId = id;
    currentEmail = email;

    document.querySelectorAll('.patient-card').forEach(c => c.classList.remove('selected'));
    event.currentTarget.classList.add('selected');

    document.getElementById('placeholder').style.display = 'none';
    document.getElementById('summaryForm').style.display = 'block';

    const header = document.getElementById('patientHeader');
    header.style.display = 'block';

    const emailBadge = email
        ? `<span class="email-badge">📧 ${email}</span>`
        : `<span class="no-email-badge">No email — Print only</span>`;
    document.getElementById('patientName').innerHTML = name + emailBadge;
    document.getElementById('patientMeta').textContent = `${doctor} · Appt: ${appt}`;

    // Reset
    document.getElementById('summaryBox').style.display = 'none';
    document.getElementById('emailBtn').style.display = 'none';
    document.getElementById('printBtn').style.display = 'none';
    document.getElementById('emailSuccess').style.display = 'none';
    document.getElementById('printSuccess').style.display = 'none';
    summaryText = '';
}

async function generateSummary() {
    const btn = document.getElementById('generateBtn');
    btn.textContent = '⏳ Generating...';
    btn.disabled = true;

    const res = await fetch('/summary/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({patient_id: currentPatientId})
    });
    const data = await res.json();
    summaryText = data.summary;

    document.getElementById('summaryBox').textContent = summaryText;
    document.getElementById('summaryBox').style.display = 'block';

    // Show email button only if email exists
    if (currentEmail) {
        document.getElementById('emailBtn').style.display = 'inline-block';
    }
    document.getElementById('printBtn').style.display = 'inline-block';

    btn.textContent = '🤖 Regenerate Summary';
    btn.disabled = false;
}

async function sendEmail() {
    const btn = document.getElementById('emailBtn');
    btn.textContent = '⏳ Sending...';
    btn.disabled = true;

    const res = await fetch('/summary/send-email', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({patient_id: currentPatientId, summary: summaryText})
    });
    const data = await res.json();

    if (data.success) {
        document.getElementById('emailSuccess').style.display = 'block';
        btn.textContent = '✅ Email Sent';
    } else {
        btn.textContent = '❌ Failed — Retry';
        btn.disabled = false;
        alert('Email failed: ' + data.error);
    }
}
</script>
</body>
</html>
"""

# ── ROUTES ───────────────────────────────────────────────────

@app.route('/summary')
def summary_panel():
    patients = get_completed_patients()
    return render_template_string(SUMMARY_PANEL, patients=patients)

@app.route('/summary/generate', methods=['POST'])
def generate():
    data = request.json
    patient_id = data.get('patient_id')
    patient = get_patient(patient_id)

    prompt = f"""Patient Information:
- Name: {patient['first_name']} {patient['last_name']}
- Date of Birth: {patient['date_of_birth']}
- Doctor: {patient['doctor_name']}
- Visit Date: {datetime.now().strftime('%B %d, %Y')}

Doctor's Structured Clinical Notes:
{patient['structured_notes']}

Please generate a warm, patient-friendly After Visit Summary."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SUMMARY_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    summary = response.content[0].text
    save_summary(patient_id, summary)
    return jsonify({"summary": summary})

@app.route('/summary/send-email', methods=['POST'])
def send_email_route():
    data = request.json
    patient_id = data.get('patient_id')
    summary = data.get('summary', '')
    patient = get_patient(patient_id)

    if not patient.get('email'):
        return jsonify({"success": False, "error": "No email address on file for this patient."})

    try:
        send_email(
            to_email=patient['email'],
            patient_name=f"{patient['first_name']} {patient['last_name']}",
            doctor_name=patient['doctor_name'],
            summary_text=summary
        )
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    print("\n After Visit Summary Agent")
    print(" Summary Panel → http://localhost:5003/summary\n")
    app.run(debug=True, port=5003)
