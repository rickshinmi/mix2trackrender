import os
from flask import Flask, request, jsonify
import numpy as np
import io
import soundfile as sf
from pydub import AudioSegment
import requests, time, hmac, hashlib, base64

app = Flask(__name__)

# === ACRCloud credentials from environment ===
ACCESS_KEY = os.environ.get("access_key")
ACCESS_SECRET = os.environ.get("access_secret")
HOST = "identify-ap-southeast-1.acrcloud.com"
REQURL = f"https://{HOST}/v1/identify"

def build_signature():
    timestamp = time.time()
    string_to_sign = '\n'.join(["POST", "/v1/identify", ACCESS_KEY, "audio", "1", str(timestamp)])
    sign = base64.b64encode(hmac.new(
        ACCESS_SECRET.encode(), string_to_sign.encode(), digestmod=hashlib.sha1
    ).digest()).decode()
    return sign, timestamp

def recognize_audio(wav_bytes):
    sign, timestamp = build_signature()
    files = [('sample', ('segment.wav', wav_bytes, 'audio/wav'))]
    data = {
        'access_key': ACCESS_KEY,
        'sample_bytes': len(wav_bytes.getvalue()),
        'timestamp': str(timestamp),
        'signature': sign,
        'data_type': 'audio',
        'signature_version': '1'
    }
    res = requests.post(REQURL, files=files, data=data)
    return res.json()

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    mp3_file = request.files['file']
    audio = AudioSegment.from_file(mp3_file, format="mp3")
    samples = np.array(audio.get_array_of_samples())
    if audio.channels == 2:
        samples = samples.reshape((-1, 2)).mean(axis=1)
    samples = samples.astype(np.float32) / (2**15)

    # Convert 30 seconds to WAV
    sr = audio.frame_rate
    seg = samples[:int(30 * sr)]
    buf = io.BytesIO()
    sf.write(buf, seg, sr, format='WAV')
    buf.seek(0)

    result = recognize_audio(buf)
    return jsonify(result)
