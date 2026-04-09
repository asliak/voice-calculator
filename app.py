from flask import Flask, render_template, request, jsonify
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv
import os, subprocess, tempfile

load_dotenv()

app = Flask(__name__)

# ── Azure Speech config ────────────────────────────────────
AZURE_KEY    = os.getenv("AZURE_SPEECH_KEY")
AZURE_REGION = os.getenv("AZURE_SPEECH_REGION")

# ── Number to words ────────────────────────────────────────
def number_to_words(n):
    if isinstance(n, float) and not n.is_integer():
        return str(n)
    n = int(n)
    if n < 0:
        return "Minus " + number_to_words(-n)
    if n == 0:
        return "Zero"
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six",
            "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve",
            "Thirteen", "Fourteen", "Fifteen", "Sixteen",
            "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty",
            "Sixty", "Seventy", "Eighty", "Ninety"]
    if n < 20:
        return ones[n]
    if n < 100:
        return tens[n // 10] + (" " + ones[n % 10] if n % 10 else "")
    if n < 1000:
        return ones[n // 100] + " Hundred" + (" " + number_to_words(n % 100) if n % 100 else "")
    return str(n)

# ── Word to operator map ───────────────────────────────────
WORD_TO_BUTTON = {
    # word form
    'zero':'0','one':'1','two':'2','three':'3','four':'4',
    'five':'5','six':'6','seven':'7','eight':'8','nine':'9',
    'point':'.','over':'÷','times':'×','plus':'+','minus':'-','is':'=',
    # digit form
    '0':'0','1':'1','2':'2','3':'3','4':'4',
    '5':'5','6':'6','7':'7','8':'8','9':'9',
    # symbol form (Azure returns these instead of words)
    '+':'+','-':'-','*':'×','/':'÷','=':'=',
    # other alternatives
    'divided':'÷','multiply':'×','multiplied':'×','add':'+','subtract':'-','equals':'='
}

# ── Routes ─────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.get_json()
    expression = data.get("expression", "")
    try:
        safe_expr = expression.replace("×", "*").replace("÷", "/")
        result = eval(safe_expr, {"__builtins__": {}}, {})
        result_word = number_to_words(result)
        return jsonify({"result": str(result), "result_word": result_word, "success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/recognize", methods=["POST"])
def recognize():
    webm_path = None
    wav_path  = None
    try:
        audio_data = request.data
        print(f"[DEBUG] Received audio bytes: {len(audio_data)}")

        if len(audio_data) == 0:
            return jsonify({"success": False, "error": "No audio data received"})

        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
            f.write(audio_data)
            webm_path = f.name
        print(f"[DEBUG] Saved to: {webm_path}")

        wav_path = webm_path.replace('.mp4', '.wav')
        ffmpeg_result = subprocess.run(
            ['ffmpeg', '-y', '-i', webm_path,
             '-ar', '16000', '-ac', '1', '-f', 'wav', wav_path],
            capture_output=True
        )
        print(f"[DEBUG] ffmpeg return code: {ffmpeg_result.returncode}")
        print(f"[DEBUG] ffmpeg stderr: {ffmpeg_result.stderr.decode()}")

        if ffmpeg_result.returncode != 0:
            return jsonify({"success": False, "error": "ffmpeg failed"})

        print(f"[DEBUG] WAV file size: {os.path.getsize(wav_path)}")
        print(f"[DEBUG] Azure key set: {bool(AZURE_KEY)}, region: {AZURE_REGION}")

        speech_config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
        speech_config.speech_recognition_language = "en-US"
        audio_config  = speechsdk.audio.AudioConfig(filename=wav_path)
        recognizer    = speechsdk.SpeechRecognizer(speech_config=speech_config,
                                                    audio_config=audio_config)
        result = recognizer.recognize_once()

        print(f"[DEBUG] Azure result reason: {result.reason}")
        print(f"[DEBUG] Azure result text: {result.text}")

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            transcript = result.text.lower().strip().rstrip('.')
            words = transcript.split()
            buttons = [WORD_TO_BUTTON[w.strip('.,?!')] for w in words if w.strip('.,?!') in WORD_TO_BUTTON]
            return jsonify({"success": True, "transcript": transcript, "buttons": buttons})
        elif result.reason == speechsdk.ResultReason.NoMatch:
            return jsonify({"success": False, "error": f"NoMatch: {result.no_match_details}"})
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = result.cancellation_details
            print(f"[DEBUG] Canceled reason: {cancellation.reason}")
            print(f"[DEBUG] Canceled error details: {cancellation.error_details}")
            return jsonify({"success": False, "error": f"Canceled: {cancellation.error_details}"})
        else:
            return jsonify({"success": False, "error": f"Unknown reason: {result.reason}"})

    except Exception as e:
        import traceback
        print(f"[DEBUG] Exception: {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)})
    finally:
        for path in [webm_path, wav_path]:
            if path and os.path.exists(path):
                os.unlink(path)
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
