from flask import Flask, render_template, request, jsonify
import numpy as np
import soundfile as sf
from pydub import AudioSegment
import requests, time, hmac, hashlib, base64
import io
import os

app = Flask(__name__)

# ACRCloud Credentials from environment variables
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

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "ファイルがありません"}), 400

    mp3_file = request.files['file']
    audio = AudioSegment.from_file(mp3_file, format="mp3")
    sr = audio.frame_rate
    samples = np.array(audio.get_array_of_samples())

    if audio.channels == 2:
        samples = samples.reshape((-1, 2)).mean(axis=1)
    audio_data = samples.astype(np.float32) / (2**15)

    # 30秒ごとに分割して識別
    segment_len = int(30 * sr)
    results = []
    displayed = []

    for i in range(0, len(audio_data), segment_len):
        segment = audio_data[i:i + segment_len]
        buf = io.BytesIO()
        sf.write(buf, segment, sr, format='WAV')
        buf.seek(0)

        result = recognize_audio(buf)
        if result.get("status", {}).get("msg") == "Success":
            metadata = result['metadata']['music'][0]
            title = metadata.get("title", "Unknown").strip()
            artist = metadata.get("artists", [{}])[0].get("name", "Unknown").strip()
            if (title, artist) not in displayed:
                displayed.append((title, artist))
                mmss = f"{i//sr//60:02}:{i//sr%60:02}"
                results.append({"time": mmss, "title": title, "artist": artist})

    return jsonify(results)
