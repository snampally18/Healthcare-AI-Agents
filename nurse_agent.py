from flask import Flask, request, jsonify, render_template_string
import anthropic
import sqlite3
import os
import subprocess
from datetime import datetime

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "checkins.db")

ROOMS = [1, 2, 3, 4, 5]

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

NURSE_PROMPT = """You are a smart nurse assistant at a medical office responsible for assigning exam rooms to waiting patients.

You will be given:
- A list of checked-in patients waiting for a room, including their appointment time and actual check-in time
- A list of available exam rooms (1-5)

Your job is to make the smartest room assignment decision by considering:
1. APPOINTMENT TIME — patients with earlier scheduled appointments get priority
2. CHECK-IN TIME — if two patients have the same appointment time, the one who checked in earlier goes first
3. WAIT TIME — flag any patient who has been waiting more than 15 minutes as urgent
4. ROOM ASSIGNMENT — assign the lowest available room number unless a higher room better suits the doctor

Explain your reasoning briefly, then give your final recommendation.

Format your response as:
REASONING: [brief explanation of why this patient and room were chosen]
PATIENT: [full name]
ROOM: [room number]
WAIT TIME: [how long they have been waiting]
MESSAGE: [friendly waiting room announcement for the patient]
"""

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT,
                last_name TEXT,
                date_of_birth TEXT,
                phone_number TEXT,
                insurance_provider TEXT,
                member_id TEXT,
                group_number TEXT,
                doctor_name TEXT,
                appointment_time TEXT,
                checked_in_at TEXT,
                room_number INTEGER DEFAULT NULL,
                room_status TEXT DEFAULT 'waiting'
            )
        """)
        # Add columns if they don't exist (for existing DBs)
        try:
            conn.execute("ALTER TABLE checkins ADD COLUMN room_number INTEGER DEFAULT NULL")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE checkins ADD COLUMN room_status TEXT DEFAULT 'waiting'")
        except Exception:
            pass

        conn.execute("""
            CREATE TABLE IF NOT EXISTS rooms (
                room_number INTEGER PRIMARY KEY,
                status TEXT DEFAULT 'available',
                patient_id INTEGER DEFAULT NULL,
                patient_name TEXT DEFAULT NULL,
                assigned_at TEXT DEFAULT NULL
            )
        """)
        for r in ROOMS:
            conn.execute("INSERT OR IGNORE INTO rooms (room_number, status) VALUES (?, 'available')", (r,))

init_db()

def get_waiting_patients():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM checkins
            WHERE room_status = 'waiting'
            ORDER BY appointment_time ASC
        """).fetchall()
    return [dict(r) for r in rows]

def get_rooms():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM rooms ORDER BY room_number").fetchall()
    return [dict(r) for r in rows]

def assign_room(patient_id, room_number):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        patient = conn.execute("SELECT * FROM checkins WHERE id=?", (patient_id,)).fetchone()
        if not patient:
            return False
        patient_name = f"{patient['first_name']} {patient['last_name']}"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            UPDATE checkins SET room_number=?, room_status='in_room' WHERE id=?
        """, (room_number, patient_id))
        conn.execute("""
            UPDATE rooms SET status='occupied', patient_id=?, patient_name=?, assigned_at=?
            WHERE room_number=?
        """, (patient_id, patient_name, now, room_number))
        conn.commit()
    return True

def release_room(room_number):
    with sqlite3.connect(DB_PATH) as conn:
        patient = conn.execute(
            "SELECT patient_id FROM rooms WHERE room_number=?", (room_number,)
        ).fetchone()
        if patient and patient['patient_id']:
            conn.execute(
                "UPDATE checkins SET room_status='completed' WHERE id=?",
                (patient['patient_id'],)
            )
        conn.execute("""
            UPDATE rooms SET status='available', patient_id=NULL, patient_name=NULL, assigned_at=NULL
            WHERE room_number=?
        """, (room_number,))

# ── HTML TEMPLATES ────────────────────────────────────────────

STAFF_PANEL = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nurse Staff Panel</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', sans-serif; background: #f0f4f8; padding: 24px; }
        h1 { font-size: 20px; color: #1a3a4a; margin-bottom: 4px; }
        .subtitle { font-size: 13px; color: #64748b; margin-bottom: 24px; }
        .nav { display: flex; gap: 12px; margin-bottom: 24px; }
        .nav a { text-decoration: none; padding: 8px 18px; border-radius: 8px; font-size: 13px; font-weight: 600; }
        .nav a.active { background: #2c7bb6; color: white; }
        .nav a:not(.active) { background: white; color: #2c7bb6; border: 1.5px solid #2c7bb6; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
        .card h2 { font-size: 14px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 14px; }
        table { width: 100%; border-collapse: collapse; }
        th { font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase; padding: 8px 10px; text-align: left; border-bottom: 2px solid #f1f5f9; }
        td { font-size: 13px; color: #374151; padding: 10px; border-bottom: 1px solid #f8fafc; vertical-align: middle; }
        tr:last-child td { border-bottom: none; }
        .badge { border-radius: 20px; padding: 3px 10px; font-size: 11px; font-weight: 600; }
        .badge-waiting  { background: #fff7ed; color: #c2410c; }
        .badge-occupied { background: #fef2f2; color: #dc2626; }
        .badge-available{ background: #f0fdf4; color: #15803d; }
        .badge-done     { background: #f0f9ff; color: #0369a1; }
        .btn { border: none; border-radius: 7px; padding: 6px 14px; font-size: 12px; font-weight: 600; cursor: pointer; }
        .btn-assign  { background: #2c7bb6; color: white; }
        .btn-release { background: #e74c3c; color: white; }
        .btn-ai      { background: linear-gradient(135deg, #e67e22, #d35400); color: white; padding: 10px 22px; font-size: 13px; border-radius: 9px; margin-bottom: 16px; }
        .btn:hover { opacity: 0.88; }
        .ai-box { background: #fff8f0; border: 1px solid #fdba74; border-radius: 9px; padding: 14px; font-size: 13px; color: #1a3a4a; line-height: 1.7; display: none; margin-bottom: 14px; white-space: pre-wrap; }
        .empty { color: #94a3b8; font-size: 13px; text-align: center; padding: 20px; }
        select { border: 1.5px solid #c8dde9; border-radius: 6px; padding: 5px 8px; font-size: 12px; outline: none; }
    </style>
</head>
<body>
    <h1>🏥 Nurse Staff Panel</h1>
    <p class="subtitle">Manage patient room assignments</p>

    <div class="nav">
        <a href="/nurse" class="active">Staff Panel</a>
        <a href="/display">Waiting Room Display</a>
        <a href="http://localhost:5000">Check-In Form</a>
        <a href="http://localhost:5000/records">All Records</a>
    </div>

    <button class="btn btn-ai" onclick="getAISuggestion()">🤖 Get AI Room Suggestion</button>
    <div class="ai-box" id="aiBox"></div>

    <div class="grid">
        <!-- Waiting Patients -->
        <div class="card">
            <h2>Waiting Patients ({{ waiting_count }})</h2>
            {% if waiting %}
            <table>
                <tr>
                    <th>Patient</th>
                    <th>Doctor</th>
                    <th>Appt</th>
                    <th>Assign Room</th>
                </tr>
                {% for p in waiting %}
                <tr>
                    <td><b>{{ p.first_name }} {{ p.last_name }}</b></td>
                    <td>{{ p.doctor_name }}</td>
                    <td>{{ p.appointment_time }}</td>
                    <td>
                        <select id="room_{{ p.id }}">
                            {% for r in available_rooms %}
                            <option value="{{ r.room_number }}">Room {{ r.room_number }}</option>
                            {% endfor %}
                        </select>
                        <button class="btn btn-assign" onclick="assignRoom({{ p.id }})">Assign</button>
                    </td>
                </tr>
                {% endfor %}
            </table>
            {% else %}
            <p class="empty">No patients waiting</p>
            {% endif %}
        </div>

        <!-- Room Status -->
        <div class="card">
            <h2>Exam Rooms (1–5)</h2>
            <table>
                <tr>
                    <th>Room</th>
                    <th>Status</th>
                    <th>Patient</th>
                    <th>Action</th>
                </tr>
                {% for r in rooms %}
                <tr>
                    <td><b>Room {{ r.room_number }}</b></td>
                    <td>
                        <span class="badge {% if r.status == 'available' %}badge-available{% else %}badge-occupied{% endif %}">
                            {{ r.status }}
                        </span>
                    </td>
                    <td>{{ r.patient_name or '—' }}</td>
                    <td>
                        {% if r.status == 'occupied' %}
                        <button class="btn btn-release" onclick="releaseRoom({{ r.room_number }})">Release</button>
                        {% else %}
                        <span style="color:#94a3b8; font-size:12px;">—</span>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </table>
        </div>
    </div>

<script>
async function assignRoom(patientId) {
    const roomSelect = document.getElementById('room_' + patientId);
    const roomNumber = roomSelect.value;
    const res = await fetch('/nurse/assign', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({patient_id: patientId, room_number: parseInt(roomNumber)})
    });
    const data = await res.json();
    if (data.success) location.reload();
    else alert('Could not assign room: ' + data.error);
}

async function releaseRoom(roomNumber) {
    const res = await fetch('/nurse/release', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({room_number: roomNumber})
    });
    const data = await res.json();
    if (data.success) location.reload();
}

async function getAISuggestion() {
    const box = document.getElementById('aiBox');
    box.style.display = 'block';
    box.textContent = 'Thinking...';
    const res = await fetch('/nurse/suggest', { method: 'POST' });
    const data = await res.json();
    box.textContent = data.suggestion;
}
</script>
</body>
</html>
"""

DISPLAY_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Waiting Room Display</title>
    <meta http-equiv="refresh" content="10">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', sans-serif; background: #0f2744; min-height: 100vh; padding: 30px; }
        .header { text-align: center; color: white; margin-bottom: 30px; }
        .header h1 { font-size: 28px; font-weight: 700; letter-spacing: 1px; }
        .header p  { font-size: 14px; color: #93c5fd; margin-top: 6px; }
        .rooms { display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; margin-bottom: 30px; }
        .room-card { border-radius: 14px; padding: 18px 12px; text-align: center; }
        .room-card.available { background: #1e3a5f; border: 2px solid #2c7bb6; }
        .room-card.occupied  { background: #1a4731; border: 2px solid #27ae60; }
        .room-num { font-size: 13px; font-weight: 700; color: #93c5fd; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
        .room-status { font-size: 12px; font-weight: 600; border-radius: 20px; padding: 3px 10px; display: inline-block; margin-bottom: 8px; }
        .available .room-status { background: #1e3a5f; color: #7dd3fc; border: 1px solid #2c7bb6; }
        .occupied  .room-status { background: #166534; color: #86efac; }
        .room-patient { font-size: 14px; font-weight: 700; color: white; line-height: 1.4; }

        .announcements { background: #1e3a5f; border-radius: 14px; padding: 20px 24px; }
        .announcements h2 { font-size: 14px; color: #93c5fd; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 16px; }
        .announcement { display: flex; align-items: center; gap: 16px; background: #0f2744; border-radius: 10px; padding: 14px 18px; margin-bottom: 10px; border-left: 4px solid #27ae60; }
        .announcement:last-child { margin-bottom: 0; }
        .ann-icon { font-size: 22px; }
        .ann-text { font-size: 16px; font-weight: 600; color: white; }
        .ann-time { font-size: 12px; color: #64748b; margin-top: 3px; }
        .empty-ann { color: #475569; font-size: 14px; text-align: center; padding: 20px; }
        .footer { text-align: center; color: #334155; font-size: 12px; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏥 Medical Center — Waiting Room</h1>
        <p>Please watch for your name. Auto-refreshes every 10 seconds.</p>
    </div>

    <!-- Room Status Grid -->
    <div class="rooms">
        {% for r in rooms %}
        <div class="room-card {{ r.status }}">
            <div class="room-num">Exam Room {{ r.room_number }}</div>
            <div class="room-status">{{ 'In Use' if r.status == 'occupied' else 'Available' }}</div>
            <div class="room-patient">{{ r.patient_name if r.patient_name else '—' }}</div>
        </div>
        {% endfor %}
    </div>

    <!-- Announcements -->
    <div class="announcements">
        <h2>📢 Patient Announcements</h2>
        {% if occupied %}
            {% for r in occupied %}
            <div class="announcement">
                <div class="ann-icon">🚶</div>
                <div>
                    <div class="ann-text">{{ r.patient_name }} — please proceed to Exam Room {{ r.room_number }}</div>
                    <div class="ann-time">Assigned at {{ r.assigned_at }}</div>
                </div>
            </div>
            {% endfor %}
        {% else %}
            <p class="empty-ann">No announcements at this time. Please remain seated.</p>
        {% endif %}
    </div>

    <div class="footer">Page auto-refreshes every 10 seconds &nbsp;|&nbsp; <a href="/nurse" style="color:#2c7bb6;">Staff Panel</a></div>
</body>
</html>
"""

# ── ROUTES ───────────────────────────────────────────────────

from flask import render_template_string as rts

@app.route('/nurse')
def nurse_panel():
    waiting = get_waiting_patients()
    rooms = get_rooms()
    available_rooms = [r for r in rooms if r['status'] == 'available']
    return rts(STAFF_PANEL,
               waiting=waiting,
               waiting_count=len(waiting),
               rooms=rooms,
               available_rooms=available_rooms)

@app.route('/display')
def display():
    rooms = get_rooms()
    occupied = [r for r in rooms if r['status'] == 'occupied']
    return rts(DISPLAY_PAGE, rooms=rooms, occupied=occupied)

@app.route('/nurse/assign', methods=['POST'])
def nurse_assign():
    data = request.json
    patient_id = data.get('patient_id')
    room_number = data.get('room_number')
    if not patient_id or not room_number:
        return jsonify({"success": False, "error": "Missing patient_id or room_number"})
    success = assign_room(patient_id, room_number)
    return jsonify({"success": success})

@app.route('/nurse/release', methods=['POST'])
def nurse_release():
    data = request.json
    room_number = data.get('room_number')
    release_room(room_number)
    return jsonify({"success": True})

@app.route('/nurse/suggest', methods=['POST'])
def nurse_suggest():
    waiting = get_waiting_patients()
    rooms = get_rooms()
    available_rooms = [r for r in rooms if r['status'] == 'available']

    if not waiting:
        return jsonify({"suggestion": "No patients are currently waiting for a room."})
    if not available_rooms:
        return jsonify({"suggestion": "All exam rooms are currently occupied. Please wait for a room to become available."})

    waiting_summary = "\n".join([
        f"- {p['first_name']} {p['last_name']} | Doctor: {p['doctor_name']} | Appt: {p['appointment_time']} | Checked in: {p['checked_in_at']}"
        for p in waiting
    ])
    rooms_summary = "\n".join([
        f"- Room {r['room_number']}: {r['status']}" + (f" (patient: {r['patient_name']})" if r['patient_name'] else "")
        for r in rooms
    ])

    prompt = f"""Waiting patients:
{waiting_summary}

Exam room status:
{rooms_summary}

Please recommend the next room assignment."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=NURSE_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    return jsonify({"suggestion": response.content[0].text})

if __name__ == '__main__':
    print("\n Nurse Agent")
    print(" Staff Panel  → http://localhost:5001/nurse")
    print(" Display Room → http://localhost:5001/display\n")
    app.run(debug=True, port=5001)
