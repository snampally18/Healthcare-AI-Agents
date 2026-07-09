import anthropic
import json

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are a friendly and professional Patient Check-In Assistant at a medical office.

Your job is to collect the following information from the patient, one step at a time:
1. Full Name
2. Date of Birth (MM/DD/YYYY)
3. Phone Number
4. Insurance Card Information (Insurance Provider, Member ID, Group Number)
5. Doctor's Name
6. Appointment Time

Guidelines:
- Greet the patient warmly at the start.
- Ask for one piece of information at a time.
- Validate the format where appropriate (e.g., date format, phone number format).
- If a patient provides an unclear or incomplete answer, politely ask them to clarify.
- Once all information is collected, summarize the check-in details clearly and ask the patient to confirm by saying "Done" or clicking Done.
- Keep responses concise and friendly.
- Track which fields have been collected and which are still needed.
- When all fields are filled, display a complete summary and prompt for confirmation.

Current check-in data format you maintain internally:
{
  "name": null,
  "date_of_birth": null,
  "phone_number": null,
  "insurance_provider": null,
  "insurance_member_id": null,
  "insurance_group_number": null,
  "doctor_name": null,
  "appointment_time": null
}
"""

def run_checkin_agent():
    print("\n" + "="*60)
    print("       PATIENT CHECK-IN SYSTEM")
    print("="*60)
    print("Type your responses below. Type 'quit' to exit.\n")

    conversation_history = []

    # Initial greeting
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": "Hello, I'm here to check in."}]
    )

    assistant_message = response.content[0].text
    print(f"Assistant: {assistant_message}\n")
    conversation_history.append({"role": "user", "content": "Hello, I'm here to check in."})
    conversation_history.append({"role": "assistant", "content": assistant_message})

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() == "quit":
            print("\nExiting check-in. Goodbye!")
            break

        if user_input.lower() in ["done", "confirm", "yes"]:
            conversation_history.append({"role": "user", "content": user_input})
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=conversation_history
            )
            final_message = response.content[0].text
            print(f"\nAssistant: {final_message}\n")
            print("="*60)
            print("CHECK-IN COMPLETE. Please have a seat.")
            print("="*60)
            break

        if not user_input:
            continue

        conversation_history.append({"role": "user", "content": user_input})

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=conversation_history
        )

        assistant_message = response.content[0].text
        conversation_history.append({"role": "assistant", "content": assistant_message})

        print(f"\nAssistant: {assistant_message}\n")

if __name__ == "__main__":
    run_checkin_agent()
