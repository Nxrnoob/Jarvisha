import React from 'react';

const VoiceButton = ({ onClick, listening }) => {
  return (
    <button onClick={onClick} className="voice-button">
      🎙 {listening ? "Stop Listening" : "Speak Now"}
    </button>
  );
};

export default VoiceButton;

