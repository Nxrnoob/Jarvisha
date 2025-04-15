from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import json
import os
from TTS.api import TTS

app = Flask(__name__)
CORS(app)

# File paths
STUDENT_FILE = "backend/data/students.json"
PROFESSOR_FILE = "backend/data/professors.json"
AUDIO_OUTPUT = "backend/response.wav"

# Load Jenny TTS model
tts = TTS(model_name="tts_models/en/jenny/jenny", progress_bar=False, gpu=False)

# Load data from JSON
def load_data(file_path):
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            json.dump({}, f)
    with open(file_path, "r") as f:
        return json.load(f)

def save_data(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

@app.route("/")
def home():
    return jsonify({"status": "AI Assistant Backend is Running 🔥"})

# Fetch student info
@app.route("/student/<string:student_id>", methods=["GET"])
def get_student(student_id):
    students = load_data(STUDENT_FILE)
    student = students.get(student_id)
    if student:
        return jsonify(student)
    else:
        return jsonify({"error": "Student not found"}), 404

# Fetch professor info
@app.route("/professor/<string:professor_id>", methods=["GET"])
def get_professor(professor_id):
    professors = load_data(PROFESSOR_FILE)
    professor = professors.get(professor_id)
    if professor:
        return jsonify(professor)
    else:
        return jsonify({"error": "Professor not found"}), 404

# Add or update student
@app.route("/student/<string:student_id>", methods=["POST"])
def update_student(student_id):
    students = load_data(STUDENT_FILE)
    students[student_id] = request.json
    save_data(STUDENT_FILE, students)
    return jsonify({"message": f"Student {student_id} updated."})

# Add or update professor
@app.route("/professor/<string:professor_id>", methods=["POST"])
def update_professor(professor_id):
    professors = load_data(PROFESSOR_FILE)
    professors[professor_id] = request.json
    save_data(PROFESSOR_FILE, professors)
    return jsonify({"message": f"Professor {professor_id} updated."})

# 🧠 Answering questions (simple logic)
@app.route("/ask", methods=["POST"])
def ask_question():
    data = request.json
    question = data.get("question", "").lower()

    students = load_data(STUDENT_FILE)
    professors = load_data(PROFESSOR_FILE)

    student = next(iter(students.values()), {})
    professor = next(iter(professors.values()), {})

    response = "Sorry, I couldn't understand the question."

    if 'attendance' in question:
        response = f"{student.get('name', 'The student')} has {student.get('attendance', 'N/A')}% attendance."
    elif 'marks' in question or 'grades' in question:
        response = f"{student.get('name', 'The student')}'s latest marks are: {student.get('marks', 'N/A')}."
    elif 'improve' in question or 'advice' in question:
        response = student.get('advice', "No advice available.")
    elif 'subject' in question:
        response = f"Prof. {professor.get('name', 'Unknown')} teaches {professor.get('subject', 'N/A')}."
    elif 'email' in question or 'contact' in question:
        response = f"You can contact Prof. {professor.get('name', 'Unknown')} at {professor.get('email', 'N/A')}."

    return jsonify({"response": response})

# 🔊 Text-to-speech endpoint using Jenny voice
@app.route("/speak", methods=["POST"])
def speak_text():
    data = request.json
    text = data.get("text", "")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        tts.tts_to_file(text=text, file_path=AUDIO_OUTPUT)
        return send_file(AUDIO_OUTPUT, mimetype="audio/wav")
    except Exception as e:
        return jsonify({"error": f"TTS failed: {str(e)}"}), 500

# Sample fallback query endpoint
@app.route("/query", methods=["POST"])
def handle_query():
    data = request.get_json()
    question = data.get("question", "")

    if not question:
        return jsonify({"error": "No question provided"}), 400

    if "marks" in question.lower():
        answer = "Your marks are 85 in Math and 90 in Science."
    elif "attendance" in question.lower():
        answer = "You have 92% attendance."
    elif "improve" in question.lower():
        answer = "Try revising daily and practice with mock tests."
    else:
        answer = "I'm not sure about that yet."

    return jsonify({"answer": answer})

if __name__ == "__main__":
    app.run(debug=True, port=5000)

