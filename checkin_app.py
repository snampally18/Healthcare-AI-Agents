from flask import Flask, request, jsonify, render_template_string
import anthropic
import json
import os
import subprocess
import sqlite3
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

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT,
                last_name TEXT,
                date_of_birth TEXT,
                phone_number TEXT,
                email TEXT,
                insurance_provider TEXT,
                member_id TEXT,
                group_number TEXT,
                doctor_name TEXT,
                appointment_time TEXT,
                checked_in_at TEXT
            )
        """)
        try:
            conn.execute("ALTER TABLE checkins ADD COLUMN email TEXT DEFAULT NULL")
        except Exception:
            pass
    conn.close()

def save_checkin(fields):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO checkins (
                first_name, last_name, date_of_birth, phone_number, email,
                insurance_provider, member_id, group_number,
                doctor_name, appointment_time, checked_in_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fields.get("first_name"),
            fields.get("last_name"),
            fields.get("date_of_birth"),
            fields.get("phone_number"),
            fields.get("email"),
            fields.get("insurance_provider"),
            fields.get("member_id"),
            fields.get("group_number"),
            fields.get("doctor_name"),
            fields.get("appointment_time"),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
    conn.close()

init_db()

SYSTEM_PROMPT = """You are a friendly and professional Patient Check-In Assistant at a medical office.

The patient has submitted a check-in form with the following fields:
- First Name (required)
- Last Name (required)
- Date of Birth MM/DD/YYYY (required)
- Phone Number (required)
- Email Address (optional — do NOT flag as missing)
- Insurance Provider (required)
- Insurance Member ID (required)
- Insurance Group Number (required)
- Doctor's Name
- Appointment Time

Your job is to:
1. Review the submitted form data.
2. Identify any missing or invalid fields.
3. If all fields are filled and valid, confirm the check-in with a warm summary.
4. If any fields are missing or invalid, list them clearly and ask the patient to correct them.

Be warm, professional, and concise.
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Patient Check-In</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #e8f4f8 0%, #d1e8f0 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }
        .container {
            background: white;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            width: 100%;
            max-width: 680px;
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #2c7bb6, #1a5276);
            color: white;
            padding: 24px 28px;
            display: flex;
            align-items: center;
            gap: 14px;
        }
        .header-icon { font-size: 32px; }
        .header h1 { font-size: 22px; font-weight: 600; }
        .header p { font-size: 13px; opacity: 0.85; margin-top: 3px; }

        .form-body { padding: 28px 32px; }

        .section-title {
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #2c7bb6;
            margin: 22px 0 12px;
            padding-bottom: 6px;
            border-bottom: 2px solid #e0eef5;
        }
        .section-title:first-child { margin-top: 0; }

        .row { display: flex; gap: 16px; }
        .field { display: flex; flex-direction: column; flex: 1; margin-bottom: 14px; }
        .field label {
            font-size: 12px;
            font-weight: 600;
            color: #555;
            margin-bottom: 5px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .field input {
            border: 1.5px solid #c8dde9;
            border-radius: 8px;
            padding: 9px 12px;
            font-size: 14px;
            font-family: inherit;
            outline: none;
            transition: border-color 0.2s;
            color: #1a3a4a;
        }
        .field input:focus { border-color: #2c7bb6; box-shadow: 0 0 0 3px rgba(44,123,182,0.1); }
        .field input.error { border-color: #e74c3c; }

        .agent-box {
            background: #f0f7fc;
            border: 1px solid #b8d9ec;
            border-radius: 10px;
            padding: 14px 16px;
            margin-top: 18px;
            font-size: 14px;
            color: #1a3a4a;
            line-height: 1.6;
            display: none;
            white-space: pre-wrap;
        }
        .agent-box.visible { display: block; }

        .footer {
            padding: 18px 32px 24px;
            display: flex;
            gap: 12px;
            justify-content: flex-end;
            border-top: 1px solid #e0eef5;
            background: #fafcfe;
        }
        .btn-submit {
            background: #2c7bb6;
            color: white;
            border: none;
            border-radius: 10px;
            padding: 11px 28px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }
        .btn-submit:hover { background: #1a5276; }
        .btn-submit:disabled { background: #aac7de; cursor: not-allowed; }

        .btn-done {
            background: linear-gradient(135deg, #27ae60, #1e8449);
            color: white;
            border: none;
            border-radius: 10px;
            padding: 11px 32px;
            font-size: 15px;
            font-weight: 700;
            cursor: pointer;
            box-shadow: 0 4px 14px rgba(39,174,96,0.3);
            transition: transform 0.15s, box-shadow 0.15s;
            display: none;
        }
        .btn-done:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(39,174,96,0.4); }

        .success-banner {
            display: none;
            background: linear-gradient(135deg, #27ae60, #1e8449);
            color: white;
            padding: 18px 28px;
            text-align: center;
            font-size: 15px;
            font-weight: 600;
        }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <div class="header-icon">🏥</div>
        <div>
            <h1>Patient Check-In</h1>
            <p>Please fill in all fields below to complete your check-in</p>
        </div>
    </div>

    <div class="form-body">
        <div class="section-title">Patient Information</div>
        <div class="row">
            <div class="field">
                <label>First Name</label>
                <input type="text" id="firstName" placeholder="e.g. Jane">
            </div>
            <div class="field">
                <label>Last Name</label>
                <input type="text" id="lastName" placeholder="e.g. Smith">
            </div>
        </div>
        <div class="row">
            <div class="field">
                <label>Date of Birth</label>
                <input type="text" id="dob" placeholder="MM/DD/YYYY">
            </div>
            <div class="field">
                <label>Phone Number</label>
                <input type="text" id="phone" placeholder="e.g. (555) 123-4567">
            </div>
        </div>
        <div class="field">
            <label>Email Address <span style="font-weight:400; color:#94a3b8; font-size:11px;">(Optional — for After Visit Summary)</span></label>
            <input type="email" id="email" placeholder="e.g. jane.smith@email.com">
        </div>

        <div class="section-title">Insurance Information</div>
        <div class="field">
            <label>Insurance Provider</label>
            <input type="text" id="insuranceProvider" placeholder="e.g. Blue Cross Blue Shield">
        </div>
        <div class="row">
            <div class="field">
                <label>Member ID</label>
                <input type="text" id="memberId" placeholder="e.g. XYZ123456">
            </div>
            <div class="field">
                <label>Group Number</label>
                <input type="text" id="groupNumber" placeholder="e.g. GRP-789">
            </div>
        </div>

        <div class="section-title">Appointment Details</div>
        <div class="row">
            <div class="field">
                <label>Doctor's Name</label>
                <input type="text" id="doctorName" placeholder="e.g. Dr. Patel">
            </div>
            <div class="field">
                <label>Appointment Time</label>
                <input type="text" id="apptTime" placeholder="e.g. 10:30 AM">
            </div>
        </div>

        <div class="agent-box" id="agentBox"></div>
    </div>

    <div class="footer">
        <button class="btn-submit" id="submitBtn" onclick="submitForm()">Submit Check-In</button>
        <button class="btn-done" id="doneBtn" onclick="confirmDone()">✓ Done — Confirm</button>
    </div>

    <div class="success-banner" id="successBanner">
        ✅ Check-In Complete! Please have a seat. A staff member will be with you shortly.
        <div style="font-size:12px; margin-top:6px; opacity:0.85;">Form will reset for the next patient in 3 seconds...</div>
    </div>
</div>

<script>
let conversationHistory = [];

async function submitForm() {
    const fields = {
        first_name:        document.getElementById('firstName').value.trim(),
        last_name:         document.getElementById('lastName').value.trim(),
        date_of_birth:     document.getElementById('dob').value.trim(),
        phone_number:      document.getElementById('phone').value.trim(),
        email:             document.getElementById('email').value.trim(),
        insurance_provider:document.getElementById('insuranceProvider').value.trim(),
        member_id:         document.getElementById('memberId').value.trim(),
        group_number:      document.getElementById('groupNumber').value.trim(),
        doctor_name:       document.getElementById('doctorName').value.trim(),
        appointment_time:  document.getElementById('apptTime').value.trim()
    };

    const submitBtn = document.getElementById('submitBtn');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Checking...';

    const res = await fetch('/submit', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({fields, history: conversationHistory})
    });
    const data = await res.json();
    conversationHistory = data.history;

    const box = document.getElementById('agentBox');
    box.textContent = data.reply;
    box.classList.add('visible');

    if (data.all_valid) {
        document.getElementById('doneBtn').style.display = 'inline-block';
        submitBtn.style.display = 'none';
    } else {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Submit Check-In';
    }
}

async function confirmDone() {
    document.getElementById('doneBtn').style.display = 'none';

    const fields = {
        first_name:         document.getElementById('firstName').value.trim(),
        last_name:          document.getElementById('lastName').value.trim(),
        date_of_birth:      document.getElementById('dob').value.trim(),
        phone_number:       document.getElementById('phone').value.trim(),
        email:              document.getElementById('email').value.trim(),
        insurance_provider: document.getElementById('insuranceProvider').value.trim(),
        member_id:          document.getElementById('memberId').value.trim(),
        group_number:       document.getElementById('groupNumber').value.trim(),
        doctor_name:        document.getElementById('doctorName').value.trim(),
        appointment_time:   document.getElementById('apptTime').value.trim()
    };

    const res = await fetch('/done', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({history: conversationHistory, fields: fields})
    });
    const data = await res.json();

    // Show success banner
    const banner = document.getElementById('successBanner');
    banner.style.display = 'block';

    // Wait 3 seconds then reset the form for the next patient
    setTimeout(() => {
        // Clear all input fields
        document.querySelectorAll('input').forEach(i => i.value = '');

        // Hide banner and agent box
        banner.style.display = 'none';
        const box = document.getElementById('agentBox');
        box.textContent = '';
        box.classList.remove('visible');

        // Reset buttons
        const submitBtn = document.getElementById('submitBtn');
        submitBtn.style.display = 'inline-block';
        submitBtn.disabled = false;
        submitBtn.textContent = 'Submit Check-In';
        document.getElementById('doneBtn').style.display = 'none';

        // Reset conversation history
        conversationHistory = [];
    }, 3000);
}
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/submit', methods=['POST'])
def submit():
    data = request.json
    fields = data.get('fields', {})
    history = data.get('history', [])

    optional_fields = {'email'}
    missing = [k.replace('_', ' ').title() for k, v in fields.items() if not v and k not in optional_fields]

    form_summary = f"""Patient submitted the following check-in form:
- First Name: {fields.get('first_name') or '(missing)'}
- Last Name: {fields.get('last_name') or '(missing)'}
- Date of Birth: {fields.get('date_of_birth') or '(missing)'}
- Phone Number: {fields.get('phone_number') or '(missing)'}
- Insurance Provider: {fields.get('insurance_provider') or '(missing)'}
- Member ID: {fields.get('member_id') or '(missing)'}
- Group Number: {fields.get('group_number') or '(missing)'}
- Doctor's Name: {fields.get('doctor_name') or '(missing)'}
- Appointment Time: {fields.get('appointment_time') or '(missing)'}

{'Please review and confirm this information is correct. Tell the patient to click Done to confirm.' if not missing else f'The following fields are missing: {", ".join(missing)}. Please ask the patient to complete them.'}"""

    history = [{"role": "user", "content": form_summary}]

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=history
    )

    reply = response.content[0].text
    history.append({"role": "assistant", "content": reply})

    all_valid = len(missing) == 0
    return jsonify({"reply": reply, "history": history, "all_valid": all_valid})

@app.route('/done', methods=['POST'])
def done():
    data = request.json
    history = data.get('history', [])
    fields = data.get('fields', {})

    save_checkin(fields)

    history.append({"role": "user", "content": "Done. I confirm all my check-in information is correct."})

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=history
    )

    reply = response.content[0].text
    return jsonify({"reply": reply})

@app.route('/records', methods=['GET'])
def records():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM checkins ORDER BY checked_in_at DESC").fetchall()
    data = [dict(r) for r in rows]

    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Check-In Records</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', sans-serif; background: #f0f4f8; padding: 30px; }
        .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
        h1 { font-size: 20px; color: #1a3a4a; }
        .count { background: #2c7bb6; color: white; border-radius: 20px; padding: 4px 14px; font-size: 13px; font-weight: 600; }
        .back { text-decoration: none; color: #2c7bb6; font-size: 13px; font-weight: 600; }
        table { width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 16px rgba(0,0,0,0.07); }
        thead { background: #2c7bb6; color: white; }
        th { padding: 12px 14px; text-align: left; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
        td { padding: 11px 14px; font-size: 13px; color: #374151; border-bottom: 1px solid #f1f5f9; }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background: #f8fbfe; }
        .empty { text-align: center; padding: 40px; color: #94a3b8; font-size: 15px; }
        .badge { background: #e8f4f8; color: #2c7bb6; border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 600; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🗄 Patient Check-In Records</h1>
        <div style="display:flex; gap:14px; align-items:center;">
            <span class="count">""" + str(len(data)) + """ record(s)</span>
            <a class="back" href="/">← Back to Check-In</a>
        </div>
    </div>
"""
    if not data:
        html += '<table><tr><td class="empty">No check-in records yet. Complete a check-in to see records here.</td></tr></table>'
    else:
        html += """
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>First Name</th>
                <th>Last Name</th>
                <th>Date of Birth</th>
                <th>Phone</th>
                <th>Insurance Provider</th>
                <th>Member ID</th>
                <th>Group No.</th>
                <th>Doctor</th>
                <th>Appt Time</th>
                <th>Checked In At</th>
            </tr>
        </thead>
        <tbody>
"""
        for r in data:
            html += f"""
            <tr>
                <td><span class="badge">{r['id']}</span></td>
                <td>{r['first_name'] or '-'}</td>
                <td>{r['last_name'] or '-'}</td>
                <td>{r['date_of_birth'] or '-'}</td>
                <td>{r['phone_number'] or '-'}</td>
                <td>{r['insurance_provider'] or '-'}</td>
                <td>{r['member_id'] or '-'}</td>
                <td>{r['group_number'] or '-'}</td>
                <td>{r['doctor_name'] or '-'}</td>
                <td>{r['appointment_time'] or '-'}</td>
                <td>{r['checked_in_at'] or '-'}</td>
            </tr>"""
        html += "</tbody></table>"

    html += "</body></html>"
    return html

if __name__ == '__main__':
    print("\n Patient Check-In Web App")
    print(" Open http://localhost:5000 in your browser\n")
    app.run(debug=True, port=5000)
