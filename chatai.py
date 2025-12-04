import streamlit as st
import speech_recognition as sr
from PIL import Image
import numpy as np
import pytesseract
import cv2
import requests
import markdown

# ---------- OPTIONAL: Set Tesseract path (Windows only) ----------
# Change the path below if your installation is different
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="Chatbot", page_icon="🤖", layout="wide")

# ---------- CUSTOM CSS (ChatGPT Style) ----------
st.markdown("""
    <style>
        body { background-color: #1E1E1E; color: white; }
        .stTextInput > div > div > input {
            background-color: #2A2A2A; color: white; border-radius: 10px;
        }
    </style>
""", unsafe_allow_html=True)

# ---------- SESSION STATE ----------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "history" not in st.session_state:
    st.session_state.history = []

# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("💬 Chat History")
    if st.session_state.history:
        for i, hist in enumerate(st.session_state.history):
            st.write(f"🗨️ Chat {i+1}")
            for msg in hist:
                st.text(msg)
    else:
        st.write("No previous chats yet.")

    if st.button("🆕 New Chat"):
        if st.session_state.messages:
            st.session_state.history.append(st.session_state.messages.copy())
        st.session_state.messages = []

# ---------- MAIN UI ----------
st.title("🤖 Chatbot")

uploaded_image = st.file_uploader("🖼️ Upload Image for OCR", type=["jpg", "jpeg", "png"])
extracted_text = ""

# ---------- OCR PROCESS (PyTesseract) ----------
if uploaded_image:
    img = Image.open(uploaded_image)
    st.image(img, caption="Uploaded Image", use_column_width=True)

    img_np = np.array(img)
    img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

    # Preprocessing for better OCR accuracy
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Perform OCR
    extracted_text = pytesseract.image_to_string(thresh)

    st.subheader("📄 Extracted Text:")
    st.write(extracted_text.strip())

# ---------- VOICE INPUT ----------
voice_text = ""
if st.button("🎤 Record Voice"):
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        st.info("Listening...")
        audio = recognizer.listen(source, phrase_time_limit=5)
    try:
        voice_text = recognizer.recognize_google(audio)
        st.success(f"You said: {voice_text}")
    except:
        st.error("Could not recognize your voice.")

# ---------- TEXT INPUT ----------
user_input = st.text_input("💬 Type your message:", value=voice_text)

# ---------- AI RESPONSE (TinyLlama) ----------
def get_bot_response(user_text):
    global extracted_text

    # If user asks to explain the image
    explain_triggers = [
        "explain", "explain above", "explain the image",
        "what is in the image", "describe the image",
        "explain the picture", "explain above picture"
    ]

    if extracted_text and any(t in user_text.lower() for t in explain_triggers):
        user_text = (
            f"The user uploaded an image and OCR extracted this text:\n\n"
            f"'{extracted_text.strip()}'\n\n"
            f"Explain what this image likely represents in simple words."
        )

    elif extracted_text and not user_text.strip():
        user_text = (
            f"The image contains this extracted text: '{extracted_text.strip()}'. "
            f"Explain what the image might be."
        )

    # Safety fallback
    if not user_text:
        return "Bot: Please upload an image or type something."

    # Send to TinyLlama (Ollama)
    try:
        resp = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "tinyllama",
                "prompt": f"You are a helpful assistant. {user_text}",
                "options": {"num_predict": 180, "temperature": 0.7}
            },
            stream=True,
            timeout=60
        )

        result = ""
        for raw in resp.iter_lines():
            if raw:
                line = raw.decode("utf-8")
                if '"response":"' in line:
                    result += line.split('"response":"', 1)[1].split('"', 1)[0]

        cleaned = result.replace("\\n", "\n").strip()
        return f"Bot: {cleaned}"

    except Exception as e:
        return f"Bot: Error contacting Ollama → {e}"

# ---------- HANDLE SEND ----------
if st.button("Send") and user_input:
    st.session_state.messages.append(f"You: {user_input}")
    reply = get_bot_response(user_input)
    st.session_state.messages.append(reply)

# ---------- CHAT DISPLAY (CHATGPT STYLE) ----------
st.subheader("💬 Chat Conversation")

for msg in st.session_state.messages:
    if not msg:
        continue  # Skip None or empty messages

    if msg.startswith("You:"):
        st.markdown(
            f"""
            <div style='background-color:#DCF8C6;
                         color:#000; padding:10px; border-radius:15px;
                         margin:8px 0; text-align:right; max-width:80%;
                         float:right; clear:both; word-wrap:break-word;'>
                {msg.replace("You:", "")}
            </div>
            """, unsafe_allow_html=True)
    else:
        bot_msg = msg.replace("Bot:", "").strip()
        html_msg = markdown.markdown(bot_msg)
        st.markdown(
            f"""
            <div style='background-color:#2F2F2F;
                         color:white; padding:10px; border-radius:15px;
                         margin:8px 0; text-align:left; max-width:80%;
                         float:left; clear:both; word-wrap:break-word;'>
                {html_msg}
            </div>
            """, unsafe_allow_html=True)
