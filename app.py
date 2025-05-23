import streamlit as st
import requests
import base64
from gtts import gTTS
from PIL import Image
import tempfile
# 📦 成分小資料庫（可以之後換成 csv）
ingredient_info = {
    "苯甲酸鈉": {
        "用途": "防腐劑，抑制黴菌與酵母菌生長",
        "風險": "部分人可能對其產生過敏反應，兒童過量攝取可能影響注意力"
    },
    "亞硝酸鈉": {
        "用途": "肉品防腐、固定紅色",
        "風險": "與胺類反應可能產生亞硝胺，有潛在致癌疑慮"
    },
    "阿斯巴甜": {
        "用途": "人工甜味劑，代替蔗糖",
        "風險": "苯酮尿症患者須避免，部分研究指出可能影響代謝"
    },
    "膠原蛋白": {
        "用途": "測試中",
        "風險": "測試中"
    },
    # 你可以繼續加～
}

# ✅ 強制放最前面
st.set_page_config(page_title="長者友善標籤小幫手", layout="centered")

# ✅ 頁面強制刷新處理（用 URL query 判斷）
if "reset" in st.query_params:
    st.markdown(
        """<meta http-equiv="refresh" content="0; url='/'" />""",
        unsafe_allow_html=True
    )
    st.stop()

# 🔄 重新開始按鈕（觸發 URL query）
if st.button("🔄 重新開始"):
    st.query_params["reset"] = "true"
    st.rerun()

MAX_FILE_SIZE = 5 * 1024 * 1024
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

st.title("👵 長者友善標籤小幫手")
st.write("上傳商品標籤圖片，我們會幫你解讀成分內容，並提供語音播放。")

# 使用者選項
mode = st.radio("請選擇顯示模式：", ["簡易模式（僅總結）", "進階模式（完整解讀）"])
speech_speed = st.radio("請選擇語音播放速度：", ["正常語速", "慢速播放"])
font_size_choice = st.radio("請選擇字體大小：", ["小", "中", "大"], index=1)

# 對應字級大小設定
font_size_map = {
    "小": "16px",
    "中": "20px",
    "大": "26px"
}
chosen_font_size = font_size_map[font_size_choice]


# 上傳圖片（多圖支援）
uploaded_files = st.file_uploader("請上傳商品標籤圖片（可多張，jpg/png，5MB 內）", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

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
                text = response.json()["candidates"][0]["content"]["parts"][0].get("text", "").strip()

                if not text:
                    st.warning("⚠️ 此圖片未產出有效文字，可能為圖像不清晰或無內容。")
                    continue

                import re
                summary = ""
                found = False
                for line in text.splitlines():
                    if "總結說明" in line:
                        found = True
                        line = re.sub(r"^\d+\.\s*", "", line)
                        summary += line.strip() + "\n"
                    elif found and line.strip():
                        summary += line.strip() + "\n"
                    elif found and not line.strip():
                        break

                if not summary:
                    summary = "這是一項含有多種成分的產品，請依照個人狀況酌量使用。"
                # ✨ 將 summary 中出現的成分轉換成可點擊的 expander
                def highlight_ingredients(text, db):
                    for ing in db:
                        if ing in text:
                            replacement = f"<span style='color:#0066cc; font-weight:bold;'>{ing}</span>"
                            text = text.replace(ing, replacement)
                    return text

                highlighted_summary = highlight_ingredients(summary, ingredient_info)

                # 顯示內容（根據模式）
                st.subheader("📝 成分說明")
                if mode == "進階模式（完整解讀）":
                    st.markdown(
                        f"<div style='font-size:{chosen_font_size}; line-height:1.8;'>{text}</div>",
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f"<div style='font-size:{chosen_font_size}; font-weight:bold;'>{highlighted_summary}</div>",
                        unsafe_allow_html=True
                    )
                for name, info in ingredient_info.items():
                    if name in summary:
                        with st.expander(f"🔍 關於「{name}」的說明"):
                            st.markdown(f"**用途：** {info['用途']}")
                            st.markdown(f"**風險：** {info['風險']}")

                # 語音播放
                tts = gTTS(summary, lang='zh-TW', slow=(speech_speed == "慢速播放"))
                temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                tts.save(temp_audio.name)

                st.subheader("🔈 總結語音播放")
                st.audio(open(temp_audio.name, 'rb').read(), format='audio/mp3')

                st.info("🤖 本解讀為 AI 推論結果，若有疑問請諮詢專業人員。")
                # 🔧 定義清理 markdown 的函式（可以放在檔案開頭）
                import re

                def remove_markdown(text):
                    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
                    text = re.sub(r"\*(.*?)\*", r"\1", text)
                    text = re.sub(r"__(.*?)__", r"\1", text)
                    text = re.sub(r"`(.*?)`", r"\1", text)
                    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
                    text = re.sub(r"^- ", "", text, flags=re.MULTILINE)
                    return text.strip()

                # 📝 建立純文字版 summary
                plain_summary = remove_markdown(summary)

                # 📋 一鍵複製按鈕（顯示在頁面上）
                import streamlit.components.v1 as components

                st.markdown("### 📋 一鍵複製總結內容")
                components.html(f"""
                    <textarea id="summary-text" style="width:100%; height:150px;">{plain_summary}</textarea>
                    <button onclick="copyToClipboard()" style="margin-top:10px;">點我複製到剪貼簿</button>
                    <script>
                    function copyToClipboard() {{
                        var copyText = document.getElementById("summary-text");
                        copyText.select();
                        document.execCommand("copy");
                        alert("✅ 已複製到剪貼簿！");
                    }}
                    </script>
                """, height=250)
                

                from PIL import Image, ImageDraw, ImageFont

                def generate_summary_image(text, output_path="summary_card.png"):
                    # 設定圖片大小與樣式
                    width, height = 800, 600
                    background_color = (255, 255, 255)
                    text_color = (30, 30, 30)

                    # 建立空白圖片
                    img = Image.new("RGB", (width, height), color=background_color)
                    draw = ImageDraw.Draw(img)

                    # 載入字型（mac 可以改成 Apple 系統內字型）
                    try:
                        font = ImageFont.truetype("arial.ttf", size=28)
                    except:
                        font = ImageFont.load_default()

                    # 自動換行處理
                    lines = []
                    line = ""
                    for word in text.split():
                        if draw.textlength(line + " " + word, font=font) <= width - 80:
                            line += " " + word
                        else:
                            lines.append(line.strip())
                            line = word
                    lines.append(line.strip())

                    # 印文字上圖
                    y = 50
                    for line in lines:
                        draw.text((40, y), line, font=font, fill=text_color)
                        y += 40

                    img.save(output_path)
                    return output_path
                    image_path = generate_summary_image(plain_summary)
                    st.image(image_path, caption="📸 分享用成分說明卡", use_column_width=True)

                    with open(image_path, "rb") as file:
                        st.download_button(
                            label="⬇️ 下載圖片卡",
                            data=file,
                            file_name="summary_card.png",
                            mime="image/png"
                        )

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



