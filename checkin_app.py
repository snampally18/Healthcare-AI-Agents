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
        ✅ Check-in complete! Please have a seat. The nurse will be with you shortly.
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

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Medical Center Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', sans-serif; background: #0f2744; min-height: 100vh; padding: 30px; }

        .header { text-align: center; color: white; margin-bottom: 36px; }
        .header h1 { font-size: 28px; font-weight: 700; letter-spacing: 1px; }
        .header p { font-size: 14px; color: #93c5fd; margin-top: 6px; }

        /* Role selector */
        .role-screen { max-width: 700px; margin: 0 auto; }
        .role-title { text-align: center; color: white; font-size: 18px; font-weight: 600; margin-bottom: 24px; }
        .role-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
        .role-card {
            background: #1e3a5f; border-radius: 14px; padding: 28px 16px;
            text-align: center; cursor: pointer; border: 2px solid #2c4a6e;
            transition: transform 0.15s, border-color 0.15s, box-shadow 0.15s;
        }
        .role-card:hover { transform: translateY(-4px); box-shadow: 0 8px 24px rgba(0,0,0,0.3); }
        .role-card.front-desk:hover { border-color: #2c7bb6; }
        .role-card.nurse:hover      { border-color: #27ae60; }
        .role-card.doctor:hover     { border-color: #e67e22; }
        .role-icon { font-size: 40px; margin-bottom: 12px; }
        .role-name { font-size: 15px; font-weight: 700; color: white; margin-bottom: 6px; }
        .role-desc { font-size: 11px; color: #64748b; line-height: 1.5; }

        /* Dashboard */
        .dashboard { display: none; }
        .role-badge {
            display: inline-flex; align-items: center; gap: 8px;
            background: #1e3a5f; border: 1px solid #2c4a6e;
            border-radius: 20px; padding: 6px 16px;
            color: white; font-size: 13px; font-weight: 600;
            cursor: pointer; margin-bottom: 24px;
        }
        .role-badge:hover { border-color: #2c7bb6; }

        .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; max-width: 900px; margin: 0 auto 20px; }
        .grid-1 { grid-template-columns: 1fr; }

        .card {
            background: #1e3a5f; border-radius: 16px; padding: 24px 26px;
            border: 1.5px solid #2c4a6e; cursor: pointer;
            transition: transform 0.15s, border-color 0.15s, box-shadow 0.15s;
            text-decoration: none; display: block;
        }
        .card:hover { transform: translateY(-4px); box-shadow: 0 8px 24px rgba(0,0,0,0.3); }
        .card-1:hover { border-color: #2c7bb6; }
        .card-2:hover { border-color: #27ae60; }
        .card-3:hover { border-color: #e67e22; }
        .card-4:hover { border-color: #7e22ce; }

        .card-icon  { font-size: 36px; margin-bottom: 12px; }
        .card-title { font-size: 17px; font-weight: 700; color: white; margin-bottom: 6px; }
        .card-desc  { font-size: 12px; color: #64748b; margin-bottom: 16px; line-height: 1.5; }
        .card-link  { font-size: 13px; font-weight: 600; color: #93c5fd; }

        .stats { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; }
        .stat { border-radius: 8px; padding: 6px 12px; font-size: 12px; font-weight: 600; }
        .stat-blue   { background: #1e3a8a; color: #93c5fd; }
        .stat-green  { background: #14532d; color: #86efac; }
        .stat-orange { background: #7c2d12; color: #fdba74; }
        .stat-purple { background: #4c1d95; color: #c4b5fd; }
        .stat-gray   { background: #1e293b; color: #94a3b8; }
        .stat-red    { background: #7f1d1d; color: #fca5a5; }

        .bottom-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; max-width: 900px; margin: 0 auto; }
        .card-sm {
            background: #1e3a5f; border-radius: 14px; padding: 18px 22px;
            border: 1.5px solid #2c4a6e; text-decoration: none; display: block;
            transition: transform 0.15s, border-color 0.15s;
        }
        .card-sm:hover { transform: translateY(-3px); border-color: #2c7bb6; }
        .card-sm-title { font-size: 14px; font-weight: 700; color: white; margin-bottom: 4px; }
        .card-sm-desc  { font-size: 12px; color: #64748b; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏥 Medical Center</h1>
        <p>Staff Portal</p>
    </div>

    <!-- Role Selector Screen -->
    <div class="role-screen" id="roleScreen">
        <p class="role-title">Who are you? Select your role to continue</p>
        <div class="role-grid">
            <div class="role-card front-desk" onclick="selectRole('frontdesk')">
                <div class="role-icon">🏥</div>
                <div class="role-name">Front Desk</div>
                <div class="role-desc">Patient check-in, records, all agents</div>
            </div>
            <div class="role-card nurse" onclick="selectRole('nurse')">
                <div class="role-icon">👩‍⚕️</div>
                <div class="role-name">Nurse</div>
                <div class="role-desc">Room assignment and waiting room display</div>
            </div>
            <div class="role-card doctor" onclick="selectRole('doctor')">
                <div class="role-icon">🩺</div>
                <div class="role-name">Doctor</div>
                <div class="role-desc">Clinical notes and after visit summary</div>
            </div>
        </div>
    </div>

    <!-- Dashboard Screen -->
    <div class="dashboard" id="dashboardScreen">
        <div style="max-width:900px; margin: 0 auto 20px; display:flex; justify-content:space-between; align-items:center;">
            <span class="role-badge" onclick="switchRole()">← Switch Role</span>
            <span id="roleName" style="color:#93c5fd; font-size:13px; font-weight:600;"></span>
        </div>

        <!-- Front Desk Cards -->
        <div id="frontdeskDash">
            <div class="grid" style="max-width:900px; margin: 0 auto 20px;">
                <a class="card card-1" href="/checkin">
                    <div class="card-icon">🏥</div>
                    <div class="card-title">Patient Check-In</div>
                    <div class="card-desc">Collect patient info, insurance details and appointment data</div>
                    <div class="stats">
                        <span class="stat stat-blue">{{ total_today }} checked in today</span>
                        <span class="stat stat-green">{{ waiting }} waiting</span>
                    </div>
                    <div class="card-link">Open Check-In →</div>
                </a>
                <a class="card card-2" href="http://localhost:5001/nurse" target="_blank">
                    <div class="card-icon">👩‍⚕️</div>
                    <div class="card-title">Nurse Room Assignment</div>
                    <div class="card-desc">Assign exam rooms to waiting patients, manage room status</div>
                    <div class="stats">
                        <span class="stat stat-orange">{{ waiting }} waiting</span>
                        <span class="stat stat-red">{{ occupied }} occupied</span>
                        <span class="stat stat-green">{{ available }} available</span>
                    </div>
                    <div class="card-link">Open Nurse Panel →</div>
                </a>
                <a class="card card-3" href="http://localhost:5002/doctor" target="_blank">
                    <div class="card-icon">🩺</div>
                    <div class="card-title">Doctor Clinical Notes</div>
                    <div class="card-desc">Type rough notes — Claude generates structured clinical documentation</div>
                    <div class="stats">
                        <span class="stat stat-orange">{{ in_room }} in room</span>
                        <span class="stat stat-green">{{ visit_done }} completed today</span>
                    </div>
                    <div class="card-link">Open Doctor Notes →</div>
                </a>
                <a class="card card-4" href="http://localhost:5003/summary" target="_blank">
                    <div class="card-icon">📋</div>
                    <div class="card-title">After Visit Summary</div>
                    <div class="card-desc">Generate patient-friendly summaries — send via email or print</div>
                    <div class="stats">
                        <span class="stat stat-purple">{{ pending_summary }} pending</span>
                        <span class="stat stat-gray">{{ summary_sent }} sent today</span>
                    </div>
                    <div class="card-link">Open Summary →</div>
                </a>
            </div>
            <div class="bottom-grid">
                <a class="card-sm" href="http://localhost:5001/display" target="_blank">
                    <div class="card-sm-title">📺 Waiting Room Display</div>
                    <div class="card-sm-desc">Live screen showing patient names and assigned rooms</div>
                </a>
                <a class="card-sm" href="/records" target="_blank">
                    <div class="card-sm-title">🗄 All Patient Records</div>
                    <div class="card-sm-desc">View all check-in records and visit history</div>
                </a>
            </div>
        </div>

        <!-- Nurse Cards -->
        <div id="nurseDash" style="display:none;">
            <div class="grid" style="max-width:900px; margin: 0 auto 20px;">
                <a class="card card-2" href="http://localhost:5001/nurse" target="_blank">
                    <div class="card-icon">👩‍⚕️</div>
                    <div class="card-title">Nurse Room Assignment</div>
                    <div class="card-desc">Assign exam rooms to waiting patients, manage room status</div>
                    <div class="stats">
                        <span class="stat stat-orange">{{ waiting }} patients waiting</span>
                        <span class="stat stat-red">{{ occupied }} rooms occupied</span>
                        <span class="stat stat-green">{{ available }} rooms available</span>
                    </div>
                    <div class="card-link">Open Nurse Panel →</div>
                </a>
                <a class="card-sm" href="http://localhost:5001/display" target="_blank" style="border-radius:16px; padding:24px 26px;">
                    <div class="card-icon">📺</div>
                    <div class="card-title" style="font-size:17px; font-weight:700; color:white; margin-bottom:6px;">Waiting Room Display</div>
                    <div class="card-desc" style="font-size:12px; color:#64748b; margin-bottom:16px;">Live screen showing patient names and assigned rooms</div>
                    <div class="card-link">Open Display →</div>
                </a>
            </div>
        </div>

        <!-- Doctor Cards -->
        <div id="doctorDash" style="display:none;">
            <div class="grid" style="max-width:900px; margin: 0 auto 20px;">
                <a class="card card-3" href="http://localhost:5002/doctor" target="_blank">
                    <div class="card-icon">🩺</div>
                    <div class="card-title">Doctor Clinical Notes</div>
                    <div class="card-desc">Type rough notes — Claude generates structured clinical documentation and After Visit Summary</div>
                    <div class="stats">
                        <span class="stat stat-orange">{{ in_room }} patient(s) in room</span>
                        <span class="stat stat-green">{{ visit_done }} visit(s) completed</span>
                    </div>
                    <div class="card-link">Open Doctor Notes →</div>
                </a>
                <a class="card card-4" href="http://localhost:5003/summary" target="_blank">
                    <div class="card-icon">📋</div>
                    <div class="card-title">After Visit Summary</div>
                    <div class="card-desc">Generate patient-friendly summaries and send via email or print</div>
                    <div class="stats">
                        <span class="stat stat-purple">{{ pending_summary }} pending</span>
                        <span class="stat stat-gray">{{ summary_sent }} sent today</span>
                    </div>
                    <div class="card-link">Open Summary →</div>
                </a>
            </div>
        </div>
    </div>

<script>
function selectRole(role) {
    document.getElementById('roleScreen').style.display = 'none';
    document.getElementById('dashboardScreen').style.display = 'block';

    document.getElementById('frontdeskDash').style.display = 'none';
    document.getElementById('nurseDash').style.display = 'none';
    document.getElementById('doctorDash').style.display = 'none';

    const labels = { frontdesk: '🏥 Front Desk', nurse: '👩‍⚕️ Nurse', doctor: '🩺 Doctor' };
    document.getElementById('roleName').textContent = labels[role];

    if (role === 'frontdesk') document.getElementById('frontdeskDash').style.display = 'block';
    if (role === 'nurse')     document.getElementById('nurseDash').style.display = 'block';
    if (role === 'doctor')    document.getElementById('doctorDash').style.display = 'block';

    localStorage.setItem('clinicRole', role);
}

function switchRole() {
    localStorage.removeItem('clinicRole');
    document.getElementById('roleScreen').style.display = 'block';
    document.getElementById('dashboardScreen').style.display = 'none';
}

// Remember role on refresh
const saved = localStorage.getItem('clinicRole');
if (saved) selectRole(saved);
</script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        today = datetime.now().strftime("%Y-%m-%d")

        total_today = conn.execute(
            "SELECT COUNT(*) FROM checkins WHERE checked_in_at LIKE ?", (f"{today}%",)
        ).fetchone()[0]
        waiting = conn.execute(
            "SELECT COUNT(*) FROM checkins WHERE room_status='waiting'"
        ).fetchone()[0]
        in_room = conn.execute(
            "SELECT COUNT(*) FROM checkins WHERE room_status='in_room'"
        ).fetchone()[0]
        visit_done = conn.execute(
            "SELECT COUNT(*) FROM checkins WHERE room_status='visit_done' AND checked_in_at LIKE ?", (f"{today}%",)
        ).fetchone()[0]
        pending_summary = conn.execute(
            "SELECT COUNT(*) FROM checkins WHERE room_status='visit_done' AND after_visit_summary IS NULL"
        ).fetchone()[0]
        summary_sent = conn.execute(
            "SELECT COUNT(*) FROM checkins WHERE summary_sent_at LIKE ?", (f"{today}%",)
        ).fetchone()[0]
        try:
            occupied = conn.execute("SELECT COUNT(*) FROM rooms WHERE status='occupied'").fetchone()[0]
            available = conn.execute("SELECT COUNT(*) FROM rooms WHERE status='available'").fetchone()[0]
        except Exception:
            occupied = 0
            available = 5

    return render_template_string(DASHBOARD_TEMPLATE,
        total_today=total_today, waiting=waiting, in_room=in_room,
        visit_done=visit_done, pending_summary=pending_summary,
        summary_sent=summary_sent, occupied=occupied, available=available
    )

@app.route('/checkin')
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
    search = request.args.get('q', '').strip()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        if search:
            rows = conn.execute("""
                SELECT * FROM checkins
                WHERE first_name LIKE ? OR last_name LIKE ?
                OR doctor_name LIKE ? OR phone_number LIKE ?
                OR date_of_birth LIKE ?
                ORDER BY checked_in_at DESC
            """, (f'%{search}%', f'%{search}%', f'%{search}%',
                  f'%{search}%', f'%{search}%')).fetchall()
        else:
            rows = conn.execute("SELECT * FROM checkins ORDER BY checked_in_at DESC").fetchall()
    data = [dict(r) for r in rows]

    status_colors = {
        'waiting':    ('background:#fff7ed; color:#c2410c;', 'Waiting'),
        'in_room':    ('background:#f0fdf4; color:#15803d;', 'In Room'),
        'visit_done': ('background:#eff6ff; color:#1d4ed8;', 'Visit Done'),
        'completed':  ('background:#f8fafc; color:#64748b;', 'Completed'),
    }

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Patient Records</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: #f0f4f8; padding: 30px; }}
        .header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; flex-wrap: wrap; gap: 12px; }}
        h1 {{ font-size: 20px; color: #1a3a4a; }}
        .nav {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }}
        .count {{ background: #2c7bb6; color: white; border-radius: 20px; padding: 4px 14px; font-size: 13px; font-weight: 600; }}
        .back {{ text-decoration: none; color: #2c7bb6; font-size: 13px; font-weight: 600; }}
        .report-link {{ text-decoration: none; background: #27ae60; color: white; border-radius: 8px; padding: 7px 16px; font-size: 13px; font-weight: 600; }}

        .search-bar {{ display: flex; gap: 10px; margin-bottom: 20px; }}
        .search-bar input {{
            flex: 1; border: 1.5px solid #c8dde9; border-radius: 9px;
            padding: 10px 16px; font-size: 14px; outline: none; font-family: inherit;
        }}
        .search-bar input:focus {{ border-color: #2c7bb6; }}
        .search-bar button {{
            background: #2c7bb6; color: white; border: none; border-radius: 9px;
            padding: 10px 22px; font-size: 14px; font-weight: 600; cursor: pointer;
        }}
        .search-bar .clear {{ background: #f1f5f9; color: #64748b; }}

        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 16px rgba(0,0,0,0.07); }}
        thead {{ background: #2c7bb6; color: white; }}
        th {{ padding: 12px 14px; text-align: left; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
        td {{ padding: 11px 14px; font-size: 13px; color: #374151; border-bottom: 1px solid #f1f5f9; }}
        tr:last-child td {{ border-bottom: none; }}
        tr:hover td {{ background: #f8fbfe; }}
        .empty {{ text-align: center; padding: 40px; color: #94a3b8; font-size: 15px; }}
        .badge {{ background: #e8f4f8; color: #2c7bb6; border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 600; }}
        .status {{ border-radius: 6px; padding: 3px 10px; font-size: 11px; font-weight: 600; }}
        .highlight {{ background: #fef9c3; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🗄 Patient Records</h1>
        <div class="nav">
            <span class="count">{len(data)} record(s)</span>
            <a class="report-link" href="/daily-report">📊 Daily Report</a>
            <a class="back" href="/">← Dashboard</a>
        </div>
    </div>

    <form class="search-bar" method="GET" action="/records">
        <input type="text" name="q" value="{search}" placeholder="Search by name, doctor, phone, or date of birth...">
        <button type="submit">🔍 Search</button>
        {"<a href='/records' class='search-bar'><button type='button' class='clear'>✕ Clear</button></a>" if search else ""}
    </form>
"""
    if not data:
        html += f'<table><tr><td class="empty">{"No records match your search." if search else "No check-in records yet."}</td></tr></table>'
    else:
        html += """
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>Name</th>
                <th>DOB</th>
                <th>Phone</th>
                <th>Doctor</th>
                <th>Appt</th>
                <th>Insurance</th>
                <th>Status</th>
                <th>Room</th>
                <th>Checked In</th>
            </tr>
        </thead>
        <tbody>
"""
        for r in data:
            status = r.get('room_status') or 'waiting'
            style, label = status_colors.get(status, ('', status))
            row_class = 'highlight' if search and (
                search.lower() in (r['first_name'] or '').lower() or
                search.lower() in (r['last_name'] or '').lower()
            ) else ''
            html += f"""
            <tr class="{row_class}">
                <td><span class="badge">{r['id']}</span></td>
                <td><b>{r['first_name'] or ''} {r['last_name'] or ''}</b></td>
                <td>{r['date_of_birth'] or '-'}</td>
                <td>{r['phone_number'] or '-'}</td>
                <td>{r['doctor_name'] or '-'}</td>
                <td>{r['appointment_time'] or '-'}</td>
                <td>{r['insurance_provider'] or '-'}</td>
                <td><span class="status" style="{style}">{label}</span></td>
                <td>{f"Room {r['room_number']}" if r.get('room_number') else '-'}</td>
                <td>{r['checked_in_at'] or '-'}</td>
            </tr>"""
        html += "</tbody></table>"

    html += "</body></html>"
    return html

@app.route('/daily-report')
def daily_report():
    today = datetime.now().strftime("%Y-%m-%d")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        total = conn.execute(
            "SELECT COUNT(*) FROM checkins WHERE checked_in_at LIKE ?", (f"{today}%",)
        ).fetchone()[0]

        waiting = conn.execute(
            "SELECT COUNT(*) FROM checkins WHERE room_status='waiting'"
        ).fetchone()[0]

        in_room = conn.execute(
            "SELECT COUNT(*) FROM checkins WHERE room_status='in_room'"
        ).fetchone()[0]

        completed = conn.execute(
            "SELECT COUNT(*) FROM checkins WHERE room_status IN ('visit_done','completed') AND checked_in_at LIKE ?",
            (f"{today}%",)
        ).fetchone()[0]

        summaries_sent = conn.execute(
            "SELECT COUNT(*) FROM checkins WHERE summary_sent_at LIKE ?", (f"{today}%",)
        ).fetchone()[0]

        by_doctor = conn.execute("""
            SELECT doctor_name, COUNT(*) as count
            FROM checkins WHERE checked_in_at LIKE ?
            GROUP BY doctor_name ORDER BY count DESC
        """, (f"{today}%",)).fetchall()

        patients = conn.execute("""
            SELECT first_name, last_name, appointment_time, room_status,
                   checked_in_at, room_number, doctor_name
            FROM checkins WHERE checked_in_at LIKE ?
            ORDER BY checked_in_at ASC
        """, (f"{today}%",)).fetchall()

        # Average wait time (checked_in_at to visit_completed_at)
        wait_rows = conn.execute("""
            SELECT checked_in_at, visit_completed_at FROM checkins
            WHERE checked_in_at LIKE ? AND visit_completed_at IS NOT NULL
        """, (f"{today}%",)).fetchall()

        avg_wait = 0
        if wait_rows:
            total_mins = 0
            count = 0
            for row in wait_rows:
                try:
                    ci = datetime.strptime(row['checked_in_at'], "%Y-%m-%d %H:%M:%S")
                    vc = datetime.strptime(row['visit_completed_at'], "%Y-%m-%d %H:%M:%S")
                    total_mins += (vc - ci).seconds // 60
                    count += 1
                except Exception:
                    pass
            if count:
                avg_wait = total_mins // count

    status_colors = {
        'waiting':    '#fff7ed; color:#c2410c',
        'in_room':    '#f0fdf4; color:#15803d',
        'visit_done': '#eff6ff; color:#1d4ed8',
        'completed':  '#f8fafc; color:#64748b',
    }

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Daily Report</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: #f0f4f8; padding: 30px; }}
        .header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }}
        h1 {{ font-size: 20px; color: #1a3a4a; }}
        .back {{ text-decoration: none; color: #2c7bb6; font-size: 13px; font-weight: 600; }}
        .date {{ font-size: 13px; color: #64748b; margin-top: 4px; }}

        .stats-grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-bottom: 28px; }}
        .stat-card {{ background: white; border-radius: 12px; padding: 20px; text-align: center; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }}
        .stat-num {{ font-size: 36px; font-weight: 700; margin-bottom: 6px; }}
        .stat-label {{ font-size: 12px; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
        .blue {{ color: #2c7bb6; }}
        .green {{ color: #27ae60; }}
        .orange {{ color: #e67e22; }}
        .purple {{ color: #7e22ce; }}
        .teal {{ color: #0891b2; }}

        .section {{ background: white; border-radius: 12px; padding: 20px 24px; margin-bottom: 20px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }}
        .section h2 {{ font-size: 13px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 16px; }}

        .doctor-row {{ display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }}
        .doctor-name {{ font-size: 14px; font-weight: 600; color: #1a3a4a; width: 160px; }}
        .bar-wrap {{ flex: 1; background: #f1f5f9; border-radius: 20px; height: 10px; }}
        .bar {{ background: #2c7bb6; border-radius: 20px; height: 10px; }}
        .bar-count {{ font-size: 13px; font-weight: 700; color: #2c7bb6; width: 30px; text-align: right; }}

        table {{ width: 100%; border-collapse: collapse; }}
        th {{ font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase; padding: 8px 10px; text-align: left; border-bottom: 2px solid #f1f5f9; }}
        td {{ font-size: 13px; color: #374151; padding: 10px; border-bottom: 1px solid #f8fafc; }}
        tr:last-child td {{ border-bottom: none; }}
        .status {{ border-radius: 6px; padding: 3px 10px; font-size: 11px; font-weight: 600; }}
        .empty {{ color: #94a3b8; text-align: center; padding: 20px; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>📊 Daily Summary Report</h1>
            <p class="date">{datetime.now().strftime('%A, %B %d, %Y')}</p>
        </div>
        <div style="display:flex; gap:12px;">
            <a class="back" href="/records">🗄 All Records</a>
            <a class="back" href="/">← Dashboard</a>
        </div>
    </div>

    <!-- Stats -->
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-num blue">{total}</div>
            <div class="stat-label">Total Patients</div>
        </div>
        <div class="stat-card">
            <div class="stat-num orange">{waiting}</div>
            <div class="stat-label">Still Waiting</div>
        </div>
        <div class="stat-card">
            <div class="stat-num teal">{in_room}</div>
            <div class="stat-label">In Room Now</div>
        </div>
        <div class="stat-card">
            <div class="stat-num green">{completed}</div>
            <div class="stat-label">Visits Done</div>
        </div>
        <div class="stat-card">
            <div class="stat-num purple">{summaries_sent}</div>
            <div class="stat-label">Summaries Sent</div>
        </div>
    </div>

    <!-- Avg Wait Time -->
    <div class="section">
        <h2>⏱ Average Visit Duration</h2>
        <p style="font-size:28px; font-weight:700; color:#1a3a4a;">
            {avg_wait} mins
            <span style="font-size:13px; color:#64748b; font-weight:400;">
                {"(based on completed visits)" if avg_wait > 0 else "(no completed visits yet today)"}
            </span>
        </p>
    </div>

    <!-- By Doctor -->
    <div class="section">
        <h2>🩺 Patients by Doctor</h2>
        {"".join([f'''
        <div class="doctor-row">
            <div class="doctor-name">{r["doctor_name"] or "Unknown"}</div>
            <div class="bar-wrap"><div class="bar" style="width:{min(100, r["count"] * 20)}%"></div></div>
            <div class="bar-count">{r["count"]}</div>
        </div>''' for r in by_doctor]) if by_doctor else '<p class="empty">No patients today</p>'}
    </div>

    <!-- Patient List -->
    <div class="section">
        <h2>👥 Today's Patients</h2>
        PATIENT_TABLE_PLACEHOLDER
    </div>
</body>
</html>"""

    if not patients:
        patient_table = "<p class='empty'>No patients checked in today yet.</p>"
    else:
        rows = ""
        for p in patients:
            status = p["room_status"] or ""
            status_style = status_colors.get(status, "#f1f5f9; color:#64748b")
            status_label = status.replace("_", " ").title() if status else "-"
            room_display = f"Room {p['room_number']}" if p["room_number"] else "-"
            rows += f"""
            <tr>
                <td><b>{p['first_name']} {p['last_name']}</b></td>
                <td>{p['doctor_name'] or '-'}</td>
                <td>{p['appointment_time'] or '-'}</td>
                <td>{room_display}</td>
                <td><span class="status" style="background:{status_style}">{status_label}</span></td>
                <td>{p['checked_in_at'] or '-'}</td>
            </tr>"""
        patient_table = f"""
        <table>
            <tr>
                <th>Name</th><th>Doctor</th><th>Appt Time</th>
                <th>Room</th><th>Status</th><th>Checked In</th>
            </tr>
            {rows}
        </table>"""

    html = html.replace("PATIENT_TABLE_PLACEHOLDER", patient_table)
    return html

if __name__ == '__main__':
    print("\n Patient Check-In Web App")
    print(" Open http://localhost:5000 in your browser\n")
    app.run(debug=True, port=5000)
