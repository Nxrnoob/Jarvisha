import { useEffect, useState, useRef } from 'react';
import './App.css';

function TypingBubble({ text, isUser, animate, onDone }) {
  const [displayed, setDisplayed] = useState([]);
  const words = text.split(' ');
  
  useEffect(() => {
    if (!animate) {
      setDisplayed(words);
      if (onDone) onDone();
      return;
    }
    setDisplayed([]);
    let i = 0;
    function showNext() {
      setDisplayed(d => [...d, words[i]]);
      i++;
      if (i < words.length) {
        setTimeout(showNext, 60);
      } else if (onDone) {
        setTimeout(onDone, 200);
      }
    }
    showNext();
    // eslint-disable-next-line
  }, [text, animate]);
  
  return (
    <div className={`chat-bubble${isUser ? ' user' : ''}`}>
      {displayed.map((word, idx) => (
        <span key={idx} className="fade-in-word">{word} </span>
      ))}
    </div>
  );
}

function App() {
  const [lines, setLines] = useState([]); // {text, isUser}
  const [pending, setPending] = useState(null); // for animating
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [sessionId, setSessionId] = useState(null);

  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const dataArrayRef = useRef(null);
  const animationRef = useRef(null);
  const circleRef = useRef(null);
  const micStreamRef = useRef(null);
  const recognitionRef = useRef(null);
  const audioRef = useRef(null);
  const chatEndRef = useRef(null);

  useEffect(() => {
    setSessionId(Date.now().toString());
  }, []);

  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [lines, pending]);

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
    if (!sessionId) return;
    try {
      const res = await fetch("http://localhost:5000/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text, sessionId }),
      });
      const data = await res.json();
      // Immediately add the assistant response to lines so it doesn't disappear
      setLines(l => [...l, { text: data.answer, isUser: false }]);
      await speakAnswer(data.answer);
    } catch (err) {
      const errorMessage = 'Error: Could not get answer.';
      setLines(l => [...l, { text: errorMessage, isUser: false }]);
      console.error("Error:", err);
    }
  };

  const speakAnswer = async (text) => {
    setIsSpeaking(true);
    if (isListening) stopListening();
    await fetch("http://localhost:5000/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    audioRef.current = new Audio(`http://localhost:5000/audio/output.wav?t=${Date.now()}`);
    audioRef.current.play();
    audioRef.current.onended = () => {
      setIsSpeaking(false);
      startListening();
    };
  };

  const stopListening = () => {
    setIsListening(false);
    recognitionRef.current?.stop();
    micStreamRef.current?.getTracks().forEach(track => track.stop());
    cancelAnimationFrame(animationRef.current);
    if (circleRef.current) circleRef.current.style.transform = 'scale(1)';
    audioContextRef.current?.close();
  };

  const startListening = async () => {
    if (isSpeaking || isListening) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      micStreamRef.current = stream;
      const context = new (window.AudioContext || window.webkitAudioContext)();
      audioContextRef.current = context;
      const source = context.createMediaStreamSource(stream);
      const analyser = context.createAnalyser();
      analyser.fftSize = 2048;
      source.connect(analyser);
      dataArrayRef.current = new Uint8Array(analyser.frequencyBinCount);
      analyserRef.current = analyser;
      animateCircle();

      // Use Web Speech API
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = false;
      recognitionRef.current.interimResults = false;
      recognitionRef.current.onresult = (event) => {
        const transcript = event.results[event.resultIndex][0].transcript;
        setLines(l => [...l, { text: transcript, isUser: true }]);
        sendToBackend(transcript);
      };
      recognitionRef.current.onend = () => stopListening();
      recognitionRef.current.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
        stopListening();
      };
      recognitionRef.current.start();
      setIsListening(true);
    } catch (err) {
      console.error("Microphone access error:", err);
    }
  };

  const handleCircleClick = () => {
    if (isSpeaking) {
      audioRef.current?.pause();
      setIsSpeaking(false);
    } else {
      isListening ? stopListening() : startListening();
    }
  };

  useEffect(() => {
    return () => stopListening(); // Cleanup on unmount
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
          <div
            key={idx}
            className={`transcript-line${line.isUser ? ' user' : ''}`}
            style={{ animationDelay: `${idx * 0.08}s` }}
          >
            {line.text}
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>
    </div>
  );
}

export default App;