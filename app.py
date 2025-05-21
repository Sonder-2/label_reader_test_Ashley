import streamlit as st
import requests
import base64
from gtts import gTTS
from PIL import Image
import tempfile

# 參數設定
MAX_FILE_SIZE = 5 * 1024 * 1024
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

st.set_page_config(page_title="長者友善標籤小幫手", layout="centered")
st.title("👵 長者友善標籤小幫手")
st.write("上傳商品標籤圖片，我們會幫你解讀成分內容，並提供語音播放。")

# 語音選項與自動播放
speech_speed = st.radio("請選擇語音播放速度：", ["正常語速", "慢速播放"])
auto_play = st.checkbox("✅ 成分說明完成後，自動播放語音", value=True)

# 上傳圖片
uploaded_file = st.file_uploader("請上傳商品標籤圖片（jpg 或 png，5MB 以下，檔名須為英文或數字）", type=["jpg", "jpeg", "png"])

if uploaded_file:
    if uploaded_file.size > MAX_FILE_SIZE:
        st.error("❗ 檔案太大了，請上傳 5MB 以下的圖片。")
    else:
        try:
            image = Image.open(uploaded_file).convert("RGB")
            image.thumbnail((1024, 1024))
        except Exception as e:
            st.error(f"❌ 圖片處理失敗：{e}")
            st.stop()

        # 顯示圖片預覽
        # 顯示圖片預覽
        st.image(image, caption="你上傳的圖片預覽", use_container_width=True)


        # 圖片轉 base64
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            image.save(temp_file.name, format="JPEG")
            image_path = temp_file.name

        with open(image_path, "rb") as img_file:
            img_base64 = base64.b64encode(img_file.read()).decode('utf-8')

        # AI 提示詞
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

        # 呼叫 Gemini API
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

        # 處理回傳結果
        if response.status_code == 200:
            try:
                text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                st.subheader("📝 成分說明")
                st.markdown(
                    f"<div style='font-size:20px; line-height:1.8;'>{text}</div>",
                    unsafe_allow_html=True
                )

                # 抓取總結語句
                summary = ""
                for line in text.splitlines():
                    if "總結說明" in line:
                        summary = line.strip()
                    elif summary and line.strip():
                        summary += "\n" + line.strip()
                    elif summary and not line.strip():
                        break

                if not summary:
                    summary = "這是一項含有多種成分的產品，請依照個人狀況酌量使用。"

                # TTS 語音合成
                tts = gTTS(summary, lang='zh-TW', slow=(speech_speed == "慢速播放"))
                temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                tts.save(temp_audio.name)

                # 播放語音
                st.subheader("🔈 總結語音播放")
                audio_file = open(temp_audio.name, 'rb')
                st.audio(audio_file.read(), format='audio/mp3', start_time=0 if auto_play else None)

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
