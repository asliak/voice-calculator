const buttonToWord = {
  '0':'Zero','1':'One','2':'Two','3':'Three','4':'Four',
  '5':'Five','6':'Six','7':'Seven','8':'Eight','9':'Nine',
  '.':'Point','÷':'Over','×':'Times','+':'Plus','-':'Minus','=':'is'
};

let expression = '';
let justCalculated = false;
let mediaRecorder = null;
let audioChunks = [];

function speak(text) {
  const utter = new SpeechSynthesisUtterance(text);
  utter.rate = 0.9;
  speechSynthesis.speak(utter);
}

async function pressButton(key) {
  const word = buttonToWord[key] || key;

  if (key === '=') {
    try {
      const response = await fetch('/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ expression: expression })
      });
      const data = await response.json();

      if (data.success) {
        speak('is ' + data.result_word);
        document.getElementById('expression').textContent = expression + ' =';
        document.getElementById('result').textContent = data.result;
        expression = data.result;
        justCalculated = true;
      } else {
        speak('Error');
        document.getElementById('result').textContent = 'Error';
        expression = '';
      }
    } catch {
      speak('Error');
      document.getElementById('result').textContent = 'Error';
    }
    return;
  }

  speak(word);

  if (justCalculated && !isNaN(key)) {
    expression = '';
    justCalculated = false;
  }

  expression += key;
  document.getElementById('expression').textContent = expression;
  document.getElementById('result').textContent = expression;
}

function clearCalc() {
  expression = '';
  justCalculated = false;
  document.getElementById('expression').textContent = '';
  document.getElementById('result').textContent = '0';
  speak('Clear');
}

// ── Voice recognition via microphone (Safari-compatible) ───
async function startVoice() {
  const micBtn = document.getElementById('micBtn');
  const status = document.getElementById('status');

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    // Safari records as audio/mp4 — use that explicitly
    const mimeType = 'audio/mp4';
    mediaRecorder = new MediaRecorder(stream, { mimeType });
    audioChunks = [];

    micBtn.classList.add('listening');
    status.textContent = 'Listening... (speak now)';

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      micBtn.classList.remove('listening');
      status.textContent = 'Processing...';
      stream.getTracks().forEach(t => t.stop());

      const audioBlob = new Blob(audioChunks, { type: mimeType });
      const arrayBuffer = await audioBlob.arrayBuffer();

      try {
        const response = await fetch('/recognize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/octet-stream' },
          body: arrayBuffer
        });
        const data = await response.json();

        if (data.success && data.buttons.length > 0) {
          status.textContent = 'Heard: "' + data.transcript + '"';
          for (const btn of data.buttons) {
            await pressButton(btn);
            await new Promise(r => setTimeout(r, 300));
          }
        } else {
          status.textContent = 'Not understood. Try again.';
          speak('Sorry, I did not understand');
        }
      } catch {
        status.textContent = 'Server error. Try again.';
      }
    };

    // Record for 5 seconds then stop 
    mediaRecorder.start();
    setTimeout(() => {
      if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
      }
    }, 5000);

  } catch (err) {
    status.textContent = 'Microphone access denied.';
    micBtn.classList.remove('listening');
  }
}