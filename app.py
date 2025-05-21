import streamlit as st
import requests
import base64
from gtts import gTTS
from PIL import Image
import tempfile
import time

MAX_FILE_SIZE = 5 * 1024 * 1024
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

st.set_page_config(page_title="長者友善標籤小幫手", layout="centered")
st.title("👵 長者友善標籤小幫手")
st.write("上傳商品標籤圖片，我們會幫你解讀成分內容，並提供語音播放。")

# ✅ 設定 uploader_key 以便後續重設
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = "uploader_0"

# ✅ 重新開始：清空 session + 換 key 達到完全重設
if st.button("🔄 重新開始"):
    uploader_new_key = f"uploader_{time.time()}"  # 獨特 key
    st.session_state.clear()
    st.session_state.uploader_key = uploader_new_key
    st.rerun()

# ✅ 使用關鍵 key 控制 file_uploader 重置
uploaded_files = st.file_uploader(
    "請上傳商品標籤圖片（可多張，jpg/png，5MB 內）",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True,
    key=st.session_state.uploader_key
)

# 使用者選項
mode = st.radio("請選擇顯示模式：", ["簡易模式（僅總結）", "進階模式（完整解讀）"])
speech_speed = st.radio("請選擇語音播放速度：", ["正常語速", "慢速播放"])

if uploaded_files:
    for uploaded_file in uploaded_files:
        st.markdown("---")
        st.image(uploaded_file, caption="你上傳的圖片預覽", use_container_width=True)

        if uploaded_file.size > MAX_FILE_SIZE:
            st.error("❗ 檔案太大了，請上傳 5MB 以下的圖片。")
            continue

        try:
            image = Image.open(uploaded_file).convert("RGB")
            image.thumbnail((1024, 1024))
        except Exception as e:
            st.error(f"❌ 圖片處理失敗：{e}")
            continue

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            image.save(temp_file.name, format="JPEG")
            image_path = temp_file.name

        with open(image_path, "rb") as img_file:
            img_base64 = base64.b64encode(img_file.read()).decode('utf-8')

        prompt_text = """
這是一張商品標籤的圖片，請協助我判讀以下資訊，並在最後加上一段「總結說明」，適合以語音形式朗讀：

1. 判斷這是食品或藥品。
2. 清楚列出以下項目：
   - 類型（食品 / 藥品）
   - 中文名稱（如果有）
   - 主要成分：每項成分的功能（例如防腐、調味、營養）以及可能注意事項（例如過敏原、對特定族群不建議）
3. 使用不超過國中程度的中文描述，適合長者與一般民眾閱讀
4. **在最後加入一段「總結說明」**，用簡短白話總結這項產品的核心資訊（例如用途、成分關鍵點、誰應避免）

只輸出清楚段落文字，無需任何多餘說明。
        """

        url = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent"
        params = {"key": GEMINI_API_KEY}
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt_text},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": img_base64
                            }
                        }
                    ]
                }
            ]
        }

        with st.spinner("AI 正在解讀標籤中..."):
            response = requests.post(url, params=params, json=payload)

        if response.status_code == 200:
            try:
                text = response.json()["candidates"][0]["content"]["parts"][0]["text"]

                # 分析總結段落
                # ✅ 用簡單邏輯自動擷取最後一段總結內容
            paragraphs = text.strip().split("\n\n")
            summary = paragraphs[-1].strip() if paragraphs else ""
        if not summary or len(summary) < 10:
        summary = "這是一項含有多種成分的產品，請依照個人狀況酌量使用。"


                # 顯示內容（根據模式切換）
                st.subheader("📝 成分說明")
                if mode == "進階模式（完整解讀）":
                    st.markdown(
                        f"<div style='font-size:18px; line-height:1.8;'>{text}</div>",
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f"<div style='font-size:20px; font-weight:bold;'>{summary}</div>",
                        unsafe_allow_html=True
                    )

                # 語音播放（不自動）
                tts = gTTS(summary, lang='zh-TW', slow=(speech_speed == "慢速播放"))
                temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                tts.save(temp_audio.name)

                st.subheader("🔈 總結語音播放")
                st.audio(open(temp_audio.name, 'rb').read(), format='audio/mp3')

                # 顯示信心語
                st.info("🤖 本解讀為 AI 推論結果，若有疑問請諮詢專業人員。")

            except Exception as e:
                st.error(f"✅ 成功回傳但解析失敗：{e}")
        else:
            try:
                err = response.json()
            except Exception:
                err = {"raw_text": response.text}

            st.error(f"❌ 請求錯誤（{response.status_code}）")
            st.subheader("🔍 API 回傳錯誤 JSON")
            st.json(err)
            st.stop()
