# Healthcare AI Agents 🏥

A multi-agent AI system that automates the complete patient journey in a medical clinic — from check-in to after visit summary — powered by Claude AI (Anthropic).

---

## System Architecture

```
Patient Check-In → Nurse Room Assignment → Doctor Clinical Notes → After Visit Summary
     Agent 1              Agent 2                 Agent 3                Agent 4
  Port 5000            Port 5001               Port 5002              Port 5003
```

---

## Agents

### Agent 1 — Patient Check-In (`checkin_app.py`)
- Patient fills a web form with personal, insurance, and appointment details
- Claude AI validates all fields and flags missing information
- Confirmed check-ins are saved to SQLite database
- Form auto-resets for the next patient after confirmation

**Fields collected:**
- First Name, Last Name
- Date of Birth, Phone Number
- Email Address *(optional — for After Visit Summary)*
- Insurance Provider, Member ID, Group Number
- Doctor's Name, Appointment Time

---

### Agent 2 — Nurse Room Assignment (`nurse_agent.py`)
- Nurse sees all waiting patients on a Staff Panel
- **Wait Time Tracker** — color-coded wait time per patient (green < 10 min, orange 10–19 min, red ⚠️ 20+ min)
- Claude AI suggests the best room assignment based on appointment time and check-in time
- Nurse assigns patients to Exam Rooms 1–5
- Waiting Room Display auto-refreshes every 10 seconds showing patient name and room number
- Nurse can release rooms when visits are complete

---

### Agent 3 — Doctor Clinical Notes (`doctor_agent.py`)
- Doctor selects a patient currently in an exam room
- Doctor types rough shorthand notes during the patient conversation
- Claude AI structures the rough notes into professional clinical documentation:
  - Chief Complaint
  - Symptoms
  - Vital Signs / Observations
  - Diagnosis
  - Treatment Plan
  - Follow-Up Instructions
  - Doctor's Notes
- Structured notes are saved to the database

---

### Agent 4 — After Visit Summary (`summary_agent.py`)
- Automatically pulls the doctor's clinical notes from the database
- Claude AI converts medical notes into a warm, patient-friendly summary
- Two delivery options:
  - 📧 **Email** — sends summary to patient's email via Mailtrap
  - 🖨️ **Print** — browser print dialog for a paper copy

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| AI Model | Claude claude-sonnet-4-6 (Anthropic) |
| Backend | Python, Flask |
| Database | SQLite |
| Frontend | HTML, CSS, JavaScript |
| Email | Mailtrap SMTP (testing) |
| Architecture | Multi-Agent System |

---

## Additional Features

### Search Patient Records
- Search box on the records page filters by patient name, doctor, phone, or date of birth
- Matching rows are highlighted for quick identification

### Wait Time Tracker
- Nurse panel shows how long each patient has been waiting
- Color-coded urgency: 🟢 green (< 10 min) → 🟠 orange (10–19 min) → 🔴 red ⚠️ (20+ min)

### Daily Summary Report (`/daily-report`)
- End-of-day stats: total patients, still waiting, in room, visits completed, summaries sent
- Average visit duration
- Patients broken down by doctor
- Full list of today's patients with status

---

## Project URLs

| URL | Description | User |
|-----|-------------|------|
| `http://localhost:5000` | Patient Check-In Form | Patient |
| `http://localhost:5000/records` | All Patient Records + Search | Staff |
| `http://localhost:5000/daily-report` | Daily Summary Report | Staff |
| `http://localhost:5001/nurse` | Nurse Staff Panel + Wait Time Tracker | Nurse |
| `http://localhost:5001/display` | Waiting Room Display | Patients |
| `http://localhost:5002/doctor` | Doctor Notes + After Visit Summary | Doctor |
| `http://localhost:5003/summary` | After Visit Summary (standalone) | Doctor/Staff |

---

## Setup Instructions

### 1. Clone the repository
```bash
git clone https://github.com/your-username/Healthcare-AI-Agents.git
cd Healthcare-AI-Agents
```

### 2. Install dependencies
```bash
pip install flask anthropic python-dotenv
```

### 3. Configure environment variables
```bash
cp .env.example .env
```
Edit `.env` and add your credentials:
- `ANTHROPIC_API_KEY` — from [console.anthropic.com](https://console.anthropic.com)
- `SMTP_USER` and `SMTP_PASS` — from [mailtrap.io](https://mailtrap.io)

### 4. Start all agents
Open 4 terminal windows and run:

```bash
# Terminal 1 — Patient Check-In
python checkin_app.py

# Terminal 2 — Nurse Room Assignment
python nurse_agent.py

# Terminal 3 — Doctor Clinical Notes
python doctor_agent.py

# Terminal 4 — After Visit Summary
python summary_agent.py
```

### 5. Open your browser
Go to `http://localhost:5000` to start the patient check-in flow.

---

## Patient Journey Flow

```
1. Patient fills check-in form
        ↓
2. Claude validates all fields
        ↓
3. Record saved to SQLite database
        ↓
4. Nurse sees patient in waiting list
        ↓
5. Claude suggests best room assignment
        ↓
6. Nurse assigns Exam Room (1-5)
        ↓
7. Waiting room display shows patient name + room
        ↓
8. Doctor types rough notes during visit
        ↓
9. Claude generates structured clinical notes
        ↓
10. Claude writes patient-friendly After Visit Summary
        ↓
11. Summary sent to patient email or printed
```

---

## HIPAA Notice

This is a **Proof of Concept** using synthetic test data only. In production, the following would be required:
- HIPAA-compliant email service (AWS SES with BAA)
- Encrypted database
- User authentication and role-based access
- Audit logging
- Business Associate Agreement (BAA) with Anthropic
- HTTPS encryption

---

## Screenshots

### Patient Check-In Form
![Check-In Form](screenshots/checkin.png)

### Nurse Staff Panel
![Nurse Panel](screenshots/nurse.png)

### Doctor Clinical Notes
![Doctor Notes](screenshots/doctor.png)

### After Visit Summary
![Summary](screenshots/summary.png)

---

## Author

Built as a portfolio project demonstrating multi-agent AI architecture in a healthcare setting.
