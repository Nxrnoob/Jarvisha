from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import json
import os
import wave
import tempfile
from TTS.api import TTS
from vosk import Model, KaldiRecognizer
import base64

app = Flask(__name__)
CORS(app)

# File paths
STUDENT_FILE = "backend/data/students.json"
PROFESSOR_FILE = "backend/data/professors.json"
AUDIO_OUTPUT = "backend/response.wav"
VOSK_MODEL_PATH = "models/vosk-model-small-en-us-0.15"

# Load Jenny TTS model
tts = TTS(model_name="tts_models/en/jenny/jenny", progress_bar=False, gpu=False)

# Load Vosk model for offline speech recognition
try:
    vosk_model = Model(VOSK_MODEL_PATH)
    print("✅ Vosk model loaded successfully")
except Exception as e:
    print(f"❌ Error loading Vosk model: {e}")
    vosk_model = None

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

# 🔊 Offline Speech Recognition using Vosk
@app.route("/recognize", methods=["POST", "OPTIONS"])
def recognize_speech():
    if request.method == "OPTIONS":
        # Handle CORS preflight request
        response = jsonify({"status": "ok"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST")
        return response
    
    print("🔊 Speech recognition request received")
    
    if not vosk_model:
        print("❌ Vosk model not loaded")
        return jsonify({"error": "Vosk model not loaded"}), 500
    
    try:
        # Get audio data from request
        data = request.get_json()
        print(f"📦 Request data keys: {list(data.keys()) if data else 'None'}")
        
        audio_data = data.get("audio")
        
        if not audio_data:
            print("❌ No audio data provided")
            return jsonify({"error": "No audio data provided"}), 400
        
        print(f"🎵 Audio data length: {len(audio_data)}")
        
        # Decode base64 audio data
        audio_bytes = base64.b64decode(audio_data.split(',')[1])
        print(f"🔊 Decoded audio bytes: {len(audio_bytes)} bytes")
        
        # Create temporary WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_file.write(audio_bytes)
            temp_file_path = temp_file.name
        
        print(f"💾 Temporary file created: {temp_file_path}")
        
        # Read WAV file
        with wave.open(temp_file_path, 'rb') as wf:
            print(f"🎵 WAV file: {wf.getnframes()} frames, {wf.getframerate()} Hz")
            
            # Create recognizer
            rec = KaldiRecognizer(vosk_model, wf.getframerate())
            rec.SetWords(True)
            
            # Process audio
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                rec.AcceptWaveform(data)
            
            # Get result
            result = json.loads(rec.FinalResult())
            transcript = result.get("text", "").strip()
            print(f"📝 Transcript: '{transcript}'")
        
        # Clean up temporary file
        os.unlink(temp_file_path)
        
        return jsonify({"transcript": transcript})
        
    except Exception as e:
        print(f"❌ Error in speech recognition: {str(e)}")
        return jsonify({"error": f"Speech recognition failed: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)

