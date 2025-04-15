from TTS.api import TTS

# List available TTS models
# print(TTS.list_models())

# Load a pre-trained TTS model (can run on CPU)
tts = TTS(model_name="tts_models/en/jenny/jenny", progress_bar=False, gpu=True)

# Run TTS
text = "Hello! I am your AI assistant. How can I help you today? and i would like to eat apples so much that i idk what to say , but what iam trying to say is , i like apples and i also watched attack on titan and i love eren and mikasa plus armin too"
tts.tts_to_file(text=text, file_path="coqui_output.wav")

