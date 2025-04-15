import { useEffect, useState, useRef } from 'react';
import './App.css';

function App() {
  const [lines, setLines] = useState([]);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);

  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const dataArrayRef = useRef(null);
  const animationRef = useRef(null);
  const circleRef = useRef(null);
  const micStreamRef = useRef(null);
  const recognitionRef = useRef(null);
  const audioRef = useRef(null);

  const animateCircle = () => {
    if (!analyserRef.current || !circleRef.current) return;

    analyserRef.current.getByteTimeDomainData(dataArrayRef.current);
    let sum = 0;
    for (let i = 0; i < dataArrayRef.current.length; i++) {
      const val = dataArrayRef.current[i] - 128;
      sum += val * val;
    }
    const volume = Math.sqrt(sum / dataArrayRef.current.length);
    const scale = Math.min(1 + volume / 10, 1.5);
    circleRef.current.style.transform = `scale(${scale})`;
    animationRef.current = requestAnimationFrame(animateCircle);
  };

  const sendToBackend = async (text) => {
    try {
      const res = await fetch("http://localhost:5000/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text }),
      });
      const data = await res.json();
      const answer = data.answer;
      setLines((prev) => [...prev, `🧠 ${answer}`]);

      await speakAnswer(answer);
    } catch (err) {
      console.error("Error:", err);
    }
  };

  const speakAnswer = async (text) => {
    setIsSpeaking(true);
    stopListening(); // prevent overlapping listening

    // Cancel any existing audio
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }

    // Generate speech on backend
    await fetch("http://localhost:5000/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });

    // Play new audio
    audioRef.current = new Audio("output.wav?" + Date.now());
    audioRef.current.play();

    audioRef.current.onended = () => {
      setIsSpeaking(false);
      startListening(); // resume listening after speaking ends
    };
  };

  const startListening = async () => {
    try {
      if (isSpeaking) return;

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      micStreamRef.current = stream;

      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 2048;
      source.connect(analyser);

      const bufferLength = analyser.fftSize;
      const dataArray = new Uint8Array(bufferLength);
      analyserRef.current = analyser;
      dataArrayRef.current = dataArray;

      animateCircle();

      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const recog = new SpeechRecognition();
      recog.continuous = true;
      recog.interimResults = false;
      recognitionRef.current = recog;

      recog.onresult = (event) => {
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            const newLine = event.results[i][0].transcript;
            setLines((prev) => [...prev, `🎤 ${newLine}`]);
            recog.stop(); // prevent double trigger
            sendToBackend(newLine);
          }
        }
      };

      recog.onend = () => {
        setIsListening(false);
      };

      recog.start();
      setIsListening(true);
    } catch (err) {
      console.error("Mic error:", err);
    }
  };

  const stopListening = () => {
    setIsListening(false);
    recognitionRef.current?.stop();
    micStreamRef.current?.getTracks().forEach(track => track.stop());
    cancelAnimationFrame(animationRef.current);
    if (circleRef.current) {
      circleRef.current.style.transform = 'scale(1)';
    }
    audioContextRef.current?.close();
  };

  const handleCircleClick = () => {
    if (isSpeaking && audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setIsSpeaking(false);
      startListening();
    } else {
      isListening ? stopListening() : startListening();
    }
  };

  useEffect(() => {
    return () => stopListening();
  }, []);

  return (
    <div className="app-container" onClick={handleCircleClick}>
      <h1 className="title">🎓 Jarvisha</h1>
      <div
        className={`circle ${isListening ? 'listening' : ''} ${isSpeaking ? 'talking' : ''}`}
        ref={circleRef}
      ></div>
      <div className="transcript-area">
        {lines.map((line, idx) => (
          <p key={idx} className="line">{line}</p>
        ))}
      </div>
    </div>
  );
}

export default App;

