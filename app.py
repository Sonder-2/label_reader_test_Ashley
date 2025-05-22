import streamlit as st
from google.cloud import texttospeech
from google.oauth2 import service_account
import json
import tempfile

st.set_page_config(page_title="語音測試", layout="centered")
st.title("🔈 Google TTS 測試")

# ✅ 從 secrets 中讀取 JSON 字串並轉為 dict
GOOGLE_TTS_CREDENTIALS = json.loads(st.secrets["GOOGLE_TTS_CREDENTIALS"])

# ✅ 用正確格式初始化憑證物件
credentials = service_account.Credentials.from_service_account_info(GOOGLE_TTS_CREDENTIALS)
client = texttospeech.TextToSpeechClient(credentials=credentials)

if st.button("生成語音"):
    synthesis_input = texttospeech.SynthesisInput(text="您好，這是一段語音測試。")

    voice = texttospeech.VoiceSelectionParams(
        language_code="zh-TW",
        name="cmn-TW-Wavenet-A"
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.0
    )

    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    with open(temp_audio.name, "wb") as out:
        out.write(response.audio_content)

    st.audio(open(temp_audio.name, "rb").read(), format="audio/mp3")
