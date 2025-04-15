import React, { useEffect, useRef, useState } from 'react';

const Bouncer = ({ listening }) => {
  const circleRef = useRef(null);
  const [audioContext, setAudioContext] = useState(null);

  useEffect(() => {
    let analyser, dataArray, mic, rafId;

    const initMic = async () => {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const context = new (window.AudioContext || window.webkitAudioContext)();
      setAudioContext(context);

      analyser = context.createAnalyser();
      const source = context.createMediaStreamSource(stream);
      source.connect(analyser);

      analyser.fftSize = 64;
      const bufferLength = analyser.frequencyBinCount;
      dataArray = new Uint8Array(bufferLength);

      const animate = () => {
        analyser.getByteFrequencyData(dataArray);
        const volume = dataArray.reduce((a, b) => a + b) / bufferLength;

        const scale = Math.max(1, volume / 50);
        const color = volume > 15 ? '#9b5de5' : 'white';

        if (circleRef.current) {
          circleRef.current.style.transform = `scale(${scale})`;
          circleRef.current.style.backgroundColor = color;
        }

        rafId = requestAnimationFrame(animate);
      };

      animate();
    };

    if (listening) {
      initMic();
    } else {
      if (audioContext) {
        audioContext.close();
        setAudioContext(null);
      }
      if (circleRef.current) {
        circleRef.current.style.transform = 'scale(1)';
        circleRef.current.style.backgroundColor = 'white';
      }
      cancelAnimationFrame(rafId);
    }

    return () => {
      if (audioContext) audioContext.close();
      cancelAnimationFrame(rafId);
    };
  }, [listening]);

  return (
    <div className="bouncer-container">
      <div className="circle" ref={circleRef}></div>
    </div>
  );
};

export default Bouncer;

