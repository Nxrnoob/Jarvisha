import subprocess
import threading
import time
import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from TTS.api import TTS
import ollama
from pydub import AudioSegment

app = Flask(__name__)
CORS(app)

# TTS initialization
tts = TTS(model_name="tts_models/en/jenny/jenny", progress_bar=False, gpu=True)

# Static audio folder
AUDIO_DIR = "audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

# TXT file paths
STUDENT_FILE = "backend/student.txt"
PROFESSOR_FILE = "backend/professor.txt"

def read_txt_file(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return f.read()
    return "No data available."

def get_gemma2_response(prompt):
    try:
        response = ollama.chat(
            model="gemma2:2b",
            messages=[{"role": "user", "content": prompt}]
        )
        return response['message']['content']  # fixed from earlier bug
    except Exception as e:
        print("Error with Gemma:", e)
        return "Gemma failed to respond."

@app.route("/")
def home():
    return jsonify({"status": "Backend is running."})

@app.route("/query", methods=["POST"])
def handle_query():
    data = request.get_json()
    question = data.get("question", "").strip().lower()

    # Load data from txt files
    student_data = read_txt_file(STUDENT_FILE)
    professor_data = read_txt_file(PROFESSOR_FILE)

    # Prepare context to assist Gemma
    context = f"""You are an educational assistant. Here is student info:\n{student_data}\n\nHere is professor info:\n{professor_data}\n\nAnswer the following question based on this information:\n{question}"""

    # Get response from Gemma
    answer = get_gemma2_response(context)

    return jsonify({"answer": answer})

@app.route("/speak", methods=["POST"])
def speak():
    try:
        data = request.get_json()
        text = data.get("text", "")

        # Clean weird characters
        cleaned_text = text.replace("%%", "%").replace("\n", " ").strip()

        max_chunk_len = 300
        if len(cleaned_text) > max_chunk_len:
            print("⚠️ Splitting long response for TTS...")
            chunks = [cleaned_text[i:i+max_chunk_len] for i in range(0, len(cleaned_text), max_chunk_len)]
            combined_audio = AudioSegment.silent(duration=0)
            for chunk in chunks:
                tts.tts_to_file(text=chunk, file_path="temp_chunk.wav")
                chunk_audio = AudioSegment.from_wav("temp_chunk.wav")
                combined_audio += chunk_audio
            combined_audio.export("frontend/public/output.wav", format="wav")
        else:
            tts.tts_to_file(text=cleaned_text, file_path="frontend/public/output.wav")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print("TTS error:", e)
        return jsonify({"error": "TTS processing failed"}), 500

@app.route("/audio/<filename>")
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename, mimetype="audio/wav")

def start_react_frontend():
    try:
        subprocess.Popen(["npm", "start"], cwd="frontend")
    except Exception as e:
        print("Error starting frontend:", e)

def start_flask_backend():
    app.run(debug=True, port=5000)

if __name__ == "__main__":
    threading.Thread(target=start_react_frontend).start()
    time.sleep(5)
    start_flask_backend()

