
import requests
import base64
import uuid
from gtts import gTTS
from PIL import Image
import tempfile

# 設定
MAX_FILE_SIZE = 5 * 1024 * 1024
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

# UI 設定
st.set_page_config(page_title="長者友善標籤小幫手", layout="centered")
st.title("👵 長者友善標籤小幫手")
st.write("上傳商品標籤圖片，我們會幫你解讀成分內容，並提供語音播放。")

# 上傳圖片
uploaded_file = st.file_uploader("請上傳商品標籤圖片（jpg 或 png，5MB 以下）", type=["jpg", "jpeg", "png"])

if uploaded_file:
    st.success(f"✅ 已上傳檔案：{uploaded_file.name}")
    
    if uploaded_file.size > MAX_FILE_SIZE:
        st.error("❗ 檔案太大了，請上傳 5MB 以下的圖片。")
    else:
        try:
            # 開啟圖片 & 縮小解析度
            image = Image.open(uploaded_file).convert("RGB")
            image.verify()  # 確保是有效圖片
            image = Image.open(uploaded_file).convert("RGB")  # verify 會關閉檔案，需要重開
            image.thumbnail((1024, 1024))
        except Exception as e:
            st.error(f"❌ 圖片處理失敗：{e}")
            st.stop()

        # 儲存為暫存檔案，使用英文安全檔名
        safe_filename = f"{uuid.uuid4().hex}.jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg", prefix="image_") as temp_file:
            image.save(temp_file.name, format="JPEG")
            image_path = temp_file.name

        try:
            # 編碼為 base64
            with open(image_path, "rb") as img_file:
                img_base64 = base64.b64encode(img_file.read()).decode("utf-8")
        except Exception as e:
            st.error(f"❌ 圖片 base64 編碼失敗：{e}")
            st.stop()

        # Gemini Prompt
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

        # Gemini API 設定
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

        with st.spinner("🧠 AI 正在解讀標籤中，請稍候..."):
            response = requests.post(url, params=params, json=payload)

        # 成功處理
        if response.status_code == 200:
            try:
                text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                st.subheader("📝 成分說明")
                st.write(text)

                # 擷取「總結說明」段落用語音朗讀
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

                # 轉語音
                tts = gTTS(summary, lang="zh-TW")
                temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                tts.save(temp_audio.name)

                # 播放語音
                st.subheader("🔈 總結語音播放")
                audio_file = open(temp_audio.name, "rb")
                st.audio(audio_file.read(), format="audio/mp3")

            except Exception as e:
                st.error(f"✅ 成功回傳但解析失敗：{e}")

        # API 錯誤處理
        else:
            try:
                err = response.json()
            except Exception:
                err = {"raw_text": response.text}

            st.error(f"❌ 請求錯誤（{response.status_code}）")
            st.subheader("🔍 API 回傳錯誤 JSON")
            st.json(err)
            st.stop()
