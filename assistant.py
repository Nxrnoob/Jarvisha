import subprocess
import threading
import time
import os
import re
import json
import wave
import tempfile
import base64
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from TTS.api import TTS
import ollama
from pydub import AudioSegment
from threading import Lock
from vosk import Model, KaldiRecognizer

app = Flask(__name__)
CORS(app)

# TTS initialization
tts = TTS(model_name="tts_models/en/ljspeech/vits", progress_bar=False, gpu=True)

# Vosk model for offline speech recognition
VOSK_MODEL_PATH = "models/vosk-model-small-en-us-0.15"
try:
    vosk_model = Model(VOSK_MODEL_PATH)
    print("✅ Vosk model loaded successfully")
except Exception as e:
    print(f"❌ Error loading Vosk model: {e}")
    vosk_model = None

# In-memory store for chat histories
chat_histories = {}

# Output audio directory
AUDIO_DIR = "frontend/public"
os.makedirs(AUDIO_DIR, exist_ok=True)

# --- Load data from JSON at startup ---
JSON_STUDENT_FILE = "backend/data/students.json"
JSON_PROFESSOR_FILE = "backend/data/professors.json"

def load_data_from_json(file_path):
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return [] # Return empty list on error

# Load data into memory once
student_data = load_data_from_json(JSON_STUDENT_FILE)
professor_data = load_data_from_json(JSON_PROFESSOR_FILE)

# Convert data to a string format for prompt injection
student_data_str = json.dumps(student_data, indent=2)
professor_data_str = json.dumps(professor_data, indent=2)

print(f"✅ Loaded {len(student_data)} student records.")
print(f"✅ Loaded {len(professor_data)} professor records.")

def clean_response(text):
    cleaned = re.sub(r"\*+", "", text)
    cleaned = re.sub(r"[_`>#\-]+", "", cleaned)
    cleaned = re.sub(r"\n{2,}", "\n", cleaned)
    return cleaned.strip()

def calculate_similarity(str1, str2):
    """Calculate similarity between two strings using simple character matching"""
    if not str1 or not str2:
        return 0
    
    str1, str2 = str1.lower(), str2.lower()
    
    # Count common characters
    common_chars = sum(1 for c in str1 if c in str2)
    total_chars = max(len(str1), len(str2))
    
    return common_chars / total_chars if total_chars > 0 else 0

def find_student_by_name(name, students):
    """Find a student by name with intelligent fuzzy matching"""
    name_lower = name.lower().strip()
    
    if not name_lower or len(name_lower) < 3:
        return None
    
    best_match = None
    best_score = 0.75  # Increased minimum similarity threshold for more strict matching
    
    for student in students:
        student_name = student.get('name', '').lower()
        if not student_name:
            continue
            
        # Calculate similarity score
        similarity = calculate_similarity(name_lower, student_name)
        
        # Check for exact match first
        if name_lower == student_name:
            return student
        
        # Check for substring matches (but be more strict)
        if name_lower in student_name and len(name_lower) >= len(student_name) * 0.6:
            similarity = max(similarity, 0.85)  # Higher threshold for substring matches
        elif student_name in name_lower and len(student_name) >= len(name_lower) * 0.6:
            similarity = max(similarity, 0.85)
        
        # Check for word-based matches (more strict)
        name_words = name_lower.split()
        student_words = student_name.split()
        
        for word in name_words:
            if len(word) > 3:  # Only check words longer than 3 characters
                for student_word in student_words:
                    word_similarity = calculate_similarity(word, student_word)
                    if word_similarity > 0.8:  # Higher word similarity threshold
                        similarity = max(similarity, word_similarity * 0.9)
        
        # Update best match if this is better
        if similarity > best_score:
            best_score = similarity
            best_match = student
    
    return best_match

def get_professor_for_subject(subject, professor_data_str):
    """Directly parse professor data to find who teaches a subject"""
    try:
        import json
        professors = json.loads(professor_data_str)
        subject_lower = subject.lower()
        
        for professor in professors:
            if professor.get('subject', '').lower() == subject_lower:
                return f"{professor.get('name', 'Unknown')} teaches {professor.get('subject', 'Unknown')}"
        
        return f"No professor found for {subject}"
    except:
        return f"Error finding professor for {subject}"

def get_gemma3_response(question, student_data_str, professor_data_str, history):
    history_str = "\n".join([f"User: {turn['user']}\nAssistant: {turn['ai']}" for turn in history]) if history else "No conversation history yet."

    # Check if user is asking about themselves specifically
    self_references = ["my", "i", "me", "myself", "i am", "my name"]
    is_self_reference = any(ref in question.lower() for ref in self_references)
    
    # Check if it's a general academic question (about subjects, professors, etc.)
    academic_keywords = ["teaches", "teach", "professor", "teacher", "subject", "subjects", "physics", "math", "chemistry", "biology", "computer", "engineering"]
    is_academic_question = any(keyword in question.lower() for keyword in academic_keywords)
    
    # Check if we're in the middle of a conversation about a specific student
    current_student = None
    if history:
        # Look for recent mentions of student names in the conversation
        import json
        try:
            students = json.loads(student_data_str)
            for student in students:
                student_name = student.get('name', '').lower()
                if student_name and student_name in history_str.lower():
                    current_student = student
                    break
        except:
            pass
    
    # Only ask for personal identification if it's a self-reference AND not an academic question
    if is_self_reference and not is_academic_question and student_data_str != "[]" and not current_student:
        # Check if the user just provided their name in this question
        import json
        try:
            students = json.loads(student_data_str)
            # Extract potential name from the question
            words = question.lower().split()
            for word in words:
                if len(word) > 2:  # Skip short words
                    found_student = find_student_by_name(word, students)
                    if found_student:
                        current_student = found_student
                        break
        except:
            pass
        
        if not current_student:
            return "I'd be happy to help you with your information! Could you please tell me your name or student ID so I can look up your specific details?"

    # Check if it's specifically asking about who teaches a subject
    if "teaches" in question.lower() or "teacher" in question.lower():
        # Extract subject from question
        subjects = ["physics", "mathematics", "math", "chemistry", "biology"]
        for subject in subjects:
            if subject in question.lower():
                return get_professor_for_subject(subject, professor_data_str)

    # Check if asking about marks without specifying a student
    mark_keywords = ["mark", "marks", "score", "scores", "grade", "grades"]
    if any(keyword in question.lower() for keyword in mark_keywords):
        # Check if a student name is mentioned
        import json
        try:
            students = json.loads(student_data_str)
            student_mentioned = False
            for student in students:
                student_name = student.get('name', '').lower()
                if student_name and student_name in question.lower():
                    student_mentioned = True
                    break
            
            if not student_mentioned:
                return "Which student's marks would you like to know?"
        except:
            pass

    prompt = f"""You are Jarvisha, a helpful AI assistant for students and professors. Give simple, direct answers.

IMPORTANT RULES:
1. ONLY provide specific student information when a student name is clearly identified
2. If someone asks about "students" in general, provide general information about the student body
3. If someone asks about a specific student without naming them, ask for clarification
4. Do NOT default to any specific student unless their name is mentioned
5. Be precise and accurate with student data
6. Keep answers SHORT and DIRECT - no long paragraphs or formal language
7. Use simple, conversational language
8. For questions about professors, subjects, or general academic info, provide the information directly
9. ALWAYS use the exact data provided - do NOT make up or guess information
10. Check the professor data carefully for subject assignments
11. Be professional and helpful - no sarcastic or inappropriate responses
12. If someone asks about marks without specifying a student name, ask them to provide the student name

EXACT PROFESSOR DATA (use this exactly):
{professor_data_str}

If the question is about education, student life, or academic topics, provide a helpful answer using the information provided below.

If the question is completely unrelated to education or academic topics, reply with: "I'm here to assist with educational and college-related topics only."

---
Student Information:
{student_data_str}

Previous Conversation:
{history_str}
---

User Question: "{question}"

IMPORTANT: 
- When someone asks about their own information (marks, attendance, etc.), look for their name in the student data. The system will automatically match names with variations and misspellings. If you find a matching student, provide their specific information. If you can't find their name, ask them to clarify their name.
- For professor questions, use ONLY the exact professor data provided above.
- Do NOT change professor names or subjects.
- If someone asks about marks without specifying which student, ask "Which student's marks would you like to know?"

Give a simple, direct answer. No long explanations or formal language. Just the facts.
"""
    try:
        response = ollama.chat(
            model="gemma3:1b",
            messages=[{"role": "user", "content": prompt}]
        )
        return clean_response(response['message']['content'])
    except Exception as e:
        print("Gemma error:", e)
        return "I'm sorry, I couldn't find an answer at the moment."

@app.route("/")
def home():
    return jsonify({"status": "Backend is running."})

@app.route("/query", methods=["POST"])
def handle_query():
    data = request.get_json()
    question = data.get("question", "").strip()
    session_id = data.get("sessionId")

    if not session_id:
        return jsonify({"error": "Session ID is missing"}), 400

    history = chat_histories.get(session_id, [])

    answer = get_gemma3_response(question, student_data_str, professor_data_str, history)

    history.append({"user": question, "ai": answer})
    chat_histories[session_id] = history

    return jsonify({"answer": answer})

@app.route("/speak", methods=["POST"])
def speak():
    try:
        data = request.get_json()
        text = data.get("text", "")
        cleaned_text = clean_response(text)
        output_path = os.path.join(AUDIO_DIR, "output.wav")
        tts.tts_to_file(text=cleaned_text, file_path=output_path)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print("TTS error:", e)
        return jsonify({"error": "TTS processing failed"}), 500

@app.route("/audio/<filename>")
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename, mimetype="audio/wav")

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
        
        # Create temporary files for conversion
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as temp_input:
            temp_input.write(audio_bytes)
            temp_input_path = temp_input.name
        
        temp_output_path = tempfile.mktemp(suffix='.wav')
        
        print(f"💾 Temporary input file created: {temp_input_path}")
        
        # Convert audio to WAV using pydub
        try:
            audio = AudioSegment.from_file(temp_input_path)
            # Force mono and 16kHz for Vosk compatibility
            audio = audio.set_channels(1).set_frame_rate(16000)
            audio.export(temp_output_path, format="wav")
            print(f"🔄 Audio converted to WAV (mono, 16kHz): {temp_output_path}")
        except Exception as e:
            print(f"❌ Audio conversion failed: {e}")
            # Clean up
            os.unlink(temp_input_path)
            return jsonify({"error": "Audio conversion failed"}), 500
        
        # Read WAV file with Vosk
        with wave.open(temp_output_path, 'rb') as wf:
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
        
        # Clean up temporary files
        os.unlink(temp_input_path)
        os.unlink(temp_output_path)
        
        return jsonify({"transcript": transcript})
        
    except Exception as e:
        print(f"❌ Error in speech recognition: {str(e)}")
        return jsonify({"error": f"Speech recognition failed: {str(e)}"}), 500

@app.route("/test", methods=["GET"])
def test_tts():
    try:
        tts.tts_to_file(
            text="This is a test. The assistant voice is working perfectly.",
            file_path=os.path.join(AUDIO_DIR, "output.wav")
        )
        return jsonify({"status": "TTS test complete"}), 200
    except Exception as e:
        print("TTS test error:", e)
        return jsonify({"error": "TTS test failed"}), 500

def start_react_frontend():
    try:
        subprocess.Popen(["npm", "start"], cwd="frontend")
    except Exception as e:
        print("Error starting frontend:", e)

def start_flask_backend():
    app.run(debug=True, port=5000)

# --- Admin API Endpoints ---
student_data_lock = Lock()
professor_data_lock = Lock()

def save_data_to_json(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

@app.route('/api/students', methods=['GET'])
def api_get_students():
    return jsonify(student_data)

@app.route('/api/students', methods=['POST'])
def api_add_student():
    new_student = request.json
    with student_data_lock:
        student_data.append(new_student)
        save_data_to_json(JSON_STUDENT_FILE, student_data)
    return jsonify({'status': 'ok', 'student': new_student}), 201

@app.route('/api/students/<int:index>', methods=['PUT'])
def api_update_student(index):
    updated_student = request.json
    with student_data_lock:
        if 0 <= index < len(student_data):
            student_data[index] = updated_student
            save_data_to_json(JSON_STUDENT_FILE, student_data)
            return jsonify({'status': 'ok', 'student': updated_student})
        else:
            return jsonify({'error': 'Student not found'}), 404

@app.route('/api/students/<int:index>', methods=['DELETE'])
def api_delete_student(index):
    with student_data_lock:
        if 0 <= index < len(student_data):
            removed = student_data.pop(index)
            save_data_to_json(JSON_STUDENT_FILE, student_data)
            return jsonify({'status': 'ok', 'removed': removed})
        else:
            return jsonify({'error': 'Student not found'}), 404

@app.route('/api/professors', methods=['GET'])
def api_get_professors():
    return jsonify(professor_data)

@app.route('/api/professors', methods=['POST'])
def api_add_professor():
    new_prof = request.json
    with professor_data_lock:
        professor_data.append(new_prof)
        save_data_to_json(JSON_PROFESSOR_FILE, professor_data)
    return jsonify({'status': 'ok', 'professor': new_prof}), 201

@app.route('/api/professors/<int:index>', methods=['PUT'])
def api_update_professor(index):
    updated_prof = request.json
    with professor_data_lock:
        if 0 <= index < len(professor_data):
            professor_data[index] = updated_prof
            save_data_to_json(JSON_PROFESSOR_FILE, professor_data)
            return jsonify({'status': 'ok', 'professor': updated_prof})
        else:
            return jsonify({'error': 'Professor not found'}), 404

@app.route('/api/professors/<int:index>', methods=['DELETE'])
def api_delete_professor(index):
    with professor_data_lock:
        if 0 <= index < len(professor_data):
            removed = professor_data.pop(index)
            save_data_to_json(JSON_PROFESSOR_FILE, professor_data)
            return jsonify({'status': 'ok', 'removed': removed})
        else:
            return jsonify({'error': 'Professor not found'}), 404

if __name__ == "__main__":
    threading.Thread(target=start_react_frontend).start()
    time.sleep(5)
    start_flask_backend()

