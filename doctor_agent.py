from flask import Flask, request, jsonify, render_template_string
import anthropic
import sqlite3
import os
import subprocess
from datetime import datetime

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "checkins.db")

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

DOCTOR_PROMPT = """You are a professional medical scribe assistant helping a doctor document a patient visit.

The doctor will type rough, shorthand notes during their conversation with the patient.
Your job is to convert those rough notes into a structured, professional clinical note.

Always format your response exactly as follows:

CHIEF COMPLAINT:
[main reason for visit in one sentence]

SYMPTOMS:
[bullet list of all symptoms mentioned, with duration if provided]

VITAL SIGNS / OBSERVATIONS:
[any measurements like temperature, blood pressure, weight mentioned]

DIAGNOSIS:
[doctor's diagnosis or suspected diagnosis]

TREATMENT PLAN:
[medications prescribed with dosage, procedures, or treatments]

FOLLOW-UP:
[when patient should return or what to watch for]

DOCTOR'S NOTES:
[any additional observations or notes]

Keep the language professional and clinical. If any section has no information, write "Not provided."
"""

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        try:
            conn.execute("ALTER TABLE checkins ADD COLUMN doctor_notes TEXT DEFAULT NULL")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE checkins ADD COLUMN structured_notes TEXT DEFAULT NULL")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE checkins ADD COLUMN visit_completed_at TEXT DEFAULT NULL")
        except Exception:
            pass

def get_patient(patient_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM checkins WHERE id=?", (patient_id,)).fetchone()
    return dict(row) if row else None

def get_inroom_patients():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM checkins
            WHERE room_status = 'in_room'
            ORDER BY appointment_time ASC
        """).fetchall()
    return [dict(r) for r in rows]

def save_notes(patient_id, raw_notes, structured_notes):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            UPDATE checkins
            SET doctor_notes=?, structured_notes=?, visit_completed_at=?, room_status='visit_done'
            WHERE id=?
        """, (raw_notes, structured_notes, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), patient_id))
        conn.commit()

init_db()

# ── HTML TEMPLATE ─────────────────────────────────────────────

DOCTOR_PANEL = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Doctor Notes Agent</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', sans-serif; background: #f0f4f8; padding: 24px; }
        h1 { font-size: 20px; color: #1a3a4a; margin-bottom: 4px; }
        .subtitle { font-size: 13px; color: #64748b; margin-bottom: 20px; }

        .nav { display: flex; gap: 12px; margin-bottom: 24px; }
        .nav a { text-decoration: none; padding: 8px 18px; border-radius: 8px; font-size: 13px; font-weight: 600; }
        .nav a.active { background: #1a5276; color: white; }
        .nav a:not(.active) { background: white; color: #1a5276; border: 1.5px solid #1a5276; }

        .grid { display: grid; grid-template-columns: 280px 1fr; gap: 20px; }

        /* Patient list */
        .patient-list { background: white; border-radius: 12px; padding: 16px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
        .patient-list h2 { font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 14px; }
        .patient-card { border-radius: 9px; padding: 12px 14px; cursor: pointer; border: 1.5px solid #e2e8f0; margin-bottom: 8px; transition: all 0.15s; }
        .patient-card:hover { border-color: #1a5276; background: #f0f4f8; }
        .patient-card.selected { border-color: #1a5276; background: #eff6ff; }
        .patient-name { font-size: 14px; font-weight: 700; color: #1a3a4a; }
        .patient-meta { font-size: 11px; color: #64748b; margin-top: 3px; }
        .badge-room { background: #1a5276; color: white; border-radius: 20px; padding: 2px 8px; font-size: 10px; font-weight: 600; margin-top: 5px; display: inline-block; }
        .empty { color: #94a3b8; font-size: 13px; text-align: center; padding: 20px; }

        /* Notes area */
        .notes-area { background: white; border-radius: 12px; padding: 20px 24px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
        .patient-header { background: #f0f4f8; border-radius: 9px; padding: 14px 16px; margin-bottom: 18px; display: none; }
        .patient-header h3 { font-size: 15px; font-weight: 700; color: #1a3a4a; }
        .patient-header p { font-size: 12px; color: #64748b; margin-top: 3px; }

        label { font-size: 12px; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.5px; display: block; margin-bottom: 6px; }
        textarea {
            width: 100%; border: 1.5px solid #c8dde9; border-radius: 9px;
            padding: 12px 14px; font-size: 14px; font-family: inherit;
            resize: vertical; outline: none; line-height: 1.6;
        }
        textarea:focus { border-color: #1a5276; box-shadow: 0 0 0 3px rgba(26,82,118,0.1); }
        .hint { font-size: 11px; color: #94a3b8; margin-top: 5px; margin-bottom: 16px; }

        .btn-row { display: flex; gap: 10px; margin-top: 16px; }
        .btn { border: none; border-radius: 9px; padding: 11px 24px; font-size: 13px; font-weight: 600; cursor: pointer; transition: opacity 0.2s; }
        .btn:hover { opacity: 0.88; }
        .btn-generate { background: linear-gradient(135deg, #e67e22, #d35400); color: white; }
        .btn-save     { background: linear-gradient(135deg, #27ae60, #1e8449); color: white; display: none; }
        .btn-clear    { background: #f1f5f9; color: #64748b; }

        .structured-box {
            background: #f8fbff; border: 1.5px solid #bfdbfe;
            border-radius: 9px; padding: 16px 18px; margin-top: 18px;
            font-size: 13px; color: #1a3a4a; line-height: 1.8;
            white-space: pre-wrap; display: none;
        }
        .structured-box h4 { font-size: 12px; font-weight: 700; color: #1a5276; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; }

        .success-msg { background: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 12px 16px; color: #15803d; font-size: 13px; font-weight: 600; display: none; margin-top: 14px; }
        .placeholder-msg { color: #94a3b8; font-size: 14px; text-align: center; padding: 60px 20px; }
        .btn-summary { background: linear-gradient(135deg, #7e22ce, #6b21a8); color: white; }
        .btn-email   { background: linear-gradient(135deg, #2c7bb6, #1a5276); color: white; }
        .btn-print   { background: linear-gradient(135deg, #27ae60, #1e8449); color: white; }
        @media print {
            .nav, .patient-list, .btn-row, h1, .subtitle, .patient-header, textarea, label, .hint { display: none !important; }
            body { background: white; padding: 0; }
            .grid { display: block; }
            .notes-area { box-shadow: none; }
            #summaryBox { display: block !important; border: none; background: white; }
        }
    </style>
</head>
<body>
    <h1>🩺 Doctor Notes Agent</h1>
    <p class="subtitle">Select a patient, type rough notes, Claude will structure them</p>

    <div class="nav">
        <a href="/doctor" class="active">Doctor Notes</a>
        <a href="http://localhost:5001/nurse">Nurse Panel</a>
        <a href="http://localhost:5001/display">Waiting Room</a>
        <a href="http://localhost:5000/records">All Records</a>
    </div>

    <div class="grid">
        <!-- Patient List -->
        <div class="patient-list">
            <h2>Patients In Room ({{ patients|length }})</h2>
            {% if patients %}
                {% for p in patients %}
                <div class="patient-card" onclick="selectPatient({{ p.id }}, '{{ p.first_name }} {{ p.last_name }}', '{{ p.doctor_name }}', '{{ p.room_number }}', '{{ p.appointment_time }}')">
                    <div class="patient-name">{{ p.first_name }} {{ p.last_name }}</div>
                    <div class="patient-meta">{{ p.doctor_name }} · {{ p.appointment_time }}</div>
                    <span class="badge-room">Room {{ p.room_number }}</span>
                </div>
                {% endfor %}
            {% else %}
                <p class="empty">No patients currently in a room.<br>Assign a room from the Nurse Panel first.</p>
            {% endif %}
        </div>

        <!-- Notes Area -->
        <div class="notes-area">
            <div class="patient-header" id="patientHeader">
                <h3 id="patientName">—</h3>
                <p id="patientMeta">—</p>
            </div>

            <div id="placeholder" class="placeholder-msg">
                👈 Select a patient from the list to begin
            </div>

            <div id="notesForm" style="display:none;">
                <label>Doctor's Rough Notes</label>
                <textarea id="roughNotes" rows="6"
                    placeholder="Type rough notes here as you talk with the patient...&#10;&#10;Example: fever 101, headache 3 days, sore throat, strep test positive, prescribe amoxicillin 500mg twice daily 10 days, follow up in 1 week if no improvement"></textarea>
                <p class="hint">Keep it short — Claude will structure it into a professional clinical note.</p>

                <div class="btn-row">
                    <button class="btn btn-generate" onclick="generateNotes()">🤖 Generate Clinical Notes</button>
                    <button class="btn btn-clear" onclick="clearNotes()">Clear</button>
                </div>

                <div class="structured-box" id="structuredBox">
                    <h4>Structured Clinical Notes</h4>
                    <div id="structuredContent"></div>
                </div>

                <button class="btn btn-save" id="saveBtn" onclick="saveNotes()">💾 Save & Complete Visit</button>

                <!-- After Visit Summary Section -->
                <div id="summarySection" style="display:none; margin-top:20px; border-top: 2px solid #e0eef5; padding-top:20px;">
                    <label>After Visit Summary</label>
                    <div class="btn-row">
                        <button class="btn btn-summary" id="summaryBtn" onclick="generateSummary()">📋 Generate After Visit Summary</button>
                    </div>
                    <div class="structured-box" id="summaryBox" style="display:none;">
                        <h4>After Visit Summary</h4>
                        <div id="summaryContent"></div>
                    </div>
                    <div class="btn-row" id="sendBtnRow" style="display:none;">
                        <button class="btn btn-email" id="emailBtn" onclick="sendEmail()">📧 Send to Patient Email</button>
                        <button class="btn btn-print" onclick="window.print()">🖨️ Print Summary</button>
                    </div>
                    <div class="success-msg" id="emailSuccess" style="display:none;">✅ After Visit Summary sent to patient's email!</div>
                    <div class="success-msg" id="noEmailMsg" style="display:none; background:#fff7ed; border-color:#fdba74; color:#c2410c;">⚠️ No email on file — please print the summary for the patient.</div>
                </div>

                <div class="success-msg" id="successMsg">✅ Visit notes saved!</div>
            </div>
        </div>
    </div>

<script>
let currentPatientId = null;
let structuredNotes = '';

function selectPatient(id, name, doctor, room, appt) {
    currentPatientId = id;

    document.querySelectorAll('.patient-card').forEach(c => c.classList.remove('selected'));
    event.currentTarget.classList.add('selected');

    document.getElementById('placeholder').style.display = 'none';
    document.getElementById('notesForm').style.display = 'block';

    const header = document.getElementById('patientHeader');
    header.style.display = 'block';
    document.getElementById('patientName').textContent = name;
    document.getElementById('patientMeta').textContent = `${doctor} · Room ${room} · Appt: ${appt}`;

    // Reset
    document.getElementById('roughNotes').value = '';
    document.getElementById('structuredBox').style.display = 'none';
    document.getElementById('saveBtn').style.display = 'none';
    document.getElementById('successMsg').style.display = 'none';
    structuredNotes = '';
}

async function generateNotes() {
    const raw = document.getElementById('roughNotes').value.trim();
    if (!raw) { alert('Please type some notes first.'); return; }

    const btn = document.querySelector('.btn-generate');
    btn.textContent = '⏳ Generating...';
    btn.disabled = true;

    const res = await fetch('/doctor/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({patient_id: currentPatientId, raw_notes: raw})
    });
    const data = await res.json();
    structuredNotes = data.structured_notes;

    document.getElementById('structuredContent').textContent = structuredNotes;
    document.getElementById('structuredBox').style.display = 'block';
    document.getElementById('saveBtn').style.display = 'inline-block';

    btn.textContent = '🤖 Regenerate Notes';
    btn.disabled = false;
}

async function saveNotes() {
    const raw = document.getElementById('roughNotes').value.trim();
    const res = await fetch('/doctor/save', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({patient_id: currentPatientId, raw_notes: raw, structured_notes: structuredNotes})
    });
    const data = await res.json();
    if (data.success) {
        document.getElementById('saveBtn').style.display = 'none';
        document.getElementById('successMsg').style.display = 'block';
        document.getElementById('roughNotes').disabled = true;
        document.getElementById('summarySection').style.display = 'block';
    }
}

let summaryText = '';

async function generateSummary() {
    const btn = document.getElementById('summaryBtn');
    btn.textContent = '⏳ Generating...';
    btn.disabled = true;

    const res = await fetch('/doctor/generate-summary', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({patient_id: currentPatientId})
    });
    const data = await res.json();
    summaryText = data.summary;
    currentEmail = data.email;

    document.getElementById('summaryContent').textContent = summaryText;
    document.getElementById('summaryBox').style.display = 'block';
    document.getElementById('sendBtnRow').style.display = 'flex';

    if (!currentEmail) {
        document.getElementById('emailBtn').style.display = 'none';
        document.getElementById('noEmailMsg').style.display = 'block';
    }

    btn.textContent = '📋 Regenerate Summary';
    btn.disabled = false;
}

async function sendEmail() {
    const btn = document.getElementById('emailBtn');
    btn.textContent = '⏳ Sending...';
    btn.disabled = true;

    const res = await fetch('/doctor/send-summary-email', {
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

function clearNotes() {
    document.getElementById('roughNotes').value = '';
    document.getElementById('structuredBox').style.display = 'none';
    document.getElementById('saveBtn').style.display = 'none';
    document.getElementById('successMsg').style.display = 'none';
    structuredNotes = '';
}
</script>
</body>
</html>
"""

# ── ROUTES ───────────────────────────────────────────────────

@app.route('/doctor')
def doctor_panel():
    patients = get_inroom_patients()
    return render_template_string(DOCTOR_PANEL, patients=patients)

@app.route('/doctor/generate', methods=['POST'])
def generate():
    data = request.json
    patient_id = data.get('patient_id')
    raw_notes = data.get('raw_notes', '')

    patient = get_patient(patient_id)
    context = f"""Patient: {patient['first_name']} {patient['last_name']}
Date of Birth: {patient['date_of_birth']}
Doctor: {patient['doctor_name']}
Appointment Time: {patient['appointment_time']}
Visit Date: {datetime.now().strftime('%Y-%m-%d')}

Doctor's rough notes:
{raw_notes}"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=DOCTOR_PROMPT,
        messages=[{"role": "user", "content": context}]
    )
    structured = response.content[0].text
    return jsonify({"structured_notes": structured})

@app.route('/doctor/save', methods=['POST'])
def save():
    data = request.json
    patient_id = data.get('patient_id')
    raw_notes = data.get('raw_notes', '')
    structured_notes = data.get('structured_notes', '')
    save_notes(patient_id, raw_notes, structured_notes)
    return jsonify({"success": True})

@app.route('/doctor/generate-summary', methods=['POST'])
def generate_summary():
    from dotenv import load_dotenv
    import smtplib
    load_dotenv()

    data = request.json
    patient_id = data.get('patient_id')
    patient = get_patient(patient_id)

    summary_prompt = """You are a medical communication specialist.
Convert the doctor's clinical notes into a warm, easy-to-understand After Visit Summary for the patient.
Use simple plain language — no medical jargon. Be warm and caring.
Format it clearly with sections: Visit Details, What We Discussed, Diagnosis, Treatment Plan, Follow-Up Instructions, Important Reminders.
End with a warm closing from the doctor."""

    prompt = f"""Patient: {patient['first_name']} {patient['last_name']}
Date of Birth: {patient['date_of_birth']}
Doctor: {patient['doctor_name']}
Visit Date: {datetime.now().strftime('%B %d, %Y')}

Clinical Notes:
{patient['structured_notes']}

Please generate a warm patient-friendly After Visit Summary."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=summary_prompt,
        messages=[{"role": "user", "content": prompt}]
    )
    summary = response.content[0].text

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE checkins SET after_visit_summary=? WHERE id=?", (summary, patient_id))
        conn.commit()

    return jsonify({"summary": summary, "email": patient.get('email', '')})

@app.route('/doctor/send-summary-email', methods=['POST'])
def send_summary_email():
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from dotenv import load_dotenv
    load_dotenv()

    data = request.json
    patient_id = data.get('patient_id')
    summary = data.get('summary', '')
    patient = get_patient(patient_id)

    if not patient.get('email'):
        return jsonify({"success": False, "error": "No email address on file."})

    try:
        smtp_host = os.getenv("SMTP_HOST", "sandbox.smtp.mailtrap.io")
        smtp_port = int(os.getenv("SMTP_PORT", 2525))
        smtp_user = os.getenv("SMTP_USER", "")
        smtp_pass = os.getenv("SMTP_PASS", "")

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Your After Visit Summary — {datetime.now().strftime('%B %d, %Y')}"
        msg['From'] = "Medical Center <clinic@medicalcenter.com>"
        msg['To'] = patient['email']

        html = f"""<html><body style="font-family:Segoe UI,sans-serif;background:#f0f4f8;padding:30px;">
        <div style="max-width:600px;margin:0 auto;background:white;border-radius:14px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08);">
            <div style="background:linear-gradient(135deg,#1a5276,#2c7bb6);padding:28px 32px;color:white;">
                <h1 style="margin:0;font-size:22px;">🏥 Medical Center</h1>
                <p style="margin:6px 0 0;opacity:0.85;font-size:14px;">After Visit Summary</p>
            </div>
            <div style="padding:28px 32px;color:#1a3a4a;line-height:1.8;font-size:14px;">
                <pre style="white-space:pre-wrap;font-family:Segoe UI,sans-serif;font-size:14px;">{summary}</pre>
            </div>
            <div style="background:#f8fbfe;padding:18px 32px;font-size:12px;color:#64748b;border-top:1px solid #e0eef5;">
                This summary is for your personal reference. Please keep it for your records.
            </div>
        </div></body></html>"""

        msg.attach(MIMEText(summary, 'plain'))
        msg.attach(MIMEText(html, 'html'))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail("clinic@medicalcenter.com", patient['email'], msg.as_string())

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE checkins SET summary_sent_at=? WHERE id=?",
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), patient_id))
            conn.commit()

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    print("\n Doctor Notes Agent")
    print(" Doctor Panel → http://localhost:5002/doctor\n")
    app.run(debug=True, port=5002)
