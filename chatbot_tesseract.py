import streamlit as st
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
import requests
import os
import warnings
import numpy as np

warnings.filterwarnings("ignore")
os.environ["FLAGS_logtostderr"] = "0"
os.environ["GLOG_minloglevel"] = "2"


# -------------------- IMPROVED OCR FOR CODE --------------------
def preprocess_for_code(image):
    gray = image.convert("L")
    # convert dark background to clean binary (removes VSCode UI noise)
    bw = gray.point(lambda x: 0 if x < 160 else 255, "1")
    return bw


def clean_code_output(text):
    cleaned = []
    menu_garbage = (
        "File", "Edit", "Selection", "View", "Go", "Run", "Terminal", "Help",
        "Network URL", "Activate Windows", "Share", "PROBLEMS", "OUTPUT", "DEBUG",
        "TERMINAL", "PORTS"
    )
    for line in text.split("\n"):
        if len(line.strip()) == 0:
            continue
        if any(ignore in line for ignore in menu_garbage):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def run_ocr(image_pil):
    try:
        img = preprocess_for_code(image_pil)
        raw_text = pytesseract.image_to_string(
            img,
            lang='eng',
            config='--oem 3 --psm 6 -c preserve_interword_spaces=1'
        )
        if not raw_text.strip():
            return "no text detected"
        cleaned = clean_code_output(raw_text)
        return cleaned if cleaned.strip() else raw_text
    except Exception as e:
        return f"OCR failed: {e}"
# ---------------------------------------------------------------


# ------------------ MODEL HANDLER (Ollama) ---------------------
def ollama_generate(prompt):
    try:
        response = requests.post(
            "http://127.0.0.1:11434/api/chat",
            json={
                "model": "qwen:0.5b",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            },
            timeout=60
        )
        data = response.json()
        if "message" in data:
            return data["message"].get("content", "Empty reply from model")
        if "response" in data:
            return data["response"]
        return f"Unexpected response format: {data}"
    except Exception as e:
        return f"Error connecting to model: {e}"
# ---------------------------------------------------------------


# ------------------------ UI SETUP -----------------------------
st.set_page_config(page_title="Smart Chatbot", page_icon="🤖", layout="wide")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

with st.sidebar:
    st.header("📝 Chat History")
    if st.session_state.chat_history:
        for idx, item in enumerate(reversed(st.session_state.chat_history)):
            if item["type"] == "text":
                st.markdown(f"**Q:** {item['content']}")
            elif item["type"] == "image":
                st.image(item["image_bytes"], caption=f"Image {len(st.session_state.chat_history) - idx}", width=120)
    else:
        st.info("No chat history yet.")

    if st.button("Clear History"):
        st.session_state.chat_history = []
        st.success("History cleared!")


st.title("🤖 Smart Chatbot ")
st.markdown("#### Ask or Upload:")

colq, coli = st.columns([4, 1])
with colq:
    user_question = st.text_input("Type your question here...", key="user_question_input")
with coli:
    uploaded_file = st.file_uploader("Browse files", type=['png', 'jpg', 'jpeg', 'bmp'], label_visibility='collapsed')

send = st.button("Send 🚀")

if "conversation" not in st.session_state:
    st.session_state.conversation = []


# --------------------- MAIN HANDLING ---------------------------
if send:
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.session_state.chat_history.append({"type": "image", "content": "", "image_bytes": uploaded_file.getvalue()})
        st.session_state.conversation.append({"role": "user", "type": "image", "image_bytes": uploaded_file.getvalue()})

        st.image(image, caption="You uploaded this image.", width=300)

        extracted_text = run_ocr(image)
        st.session_state.conversation.append({"role": "bot", "type": "text", "content": f"📄 Extracted Code:\n\n{extracted_text}"})

        if extracted_text != "no text detected" and not extracted_text.startswith("OCR failed"):
            st.info("Extracted code is being explained...")
            bot_reply = ollama_generate(f"Explain this code in detail:\n\n{extracted_text}")
            st.session_state.conversation.append({"role": "bot", "type": "text", "content": bot_reply})

    elif user_question.strip():
        st.session_state.chat_history.append({"type": "text", "content": user_question})
        st.session_state.conversation.append({"role": "user", "type": "text", "content": user_question})
        bot_reply = ollama_generate(user_question)
        st.session_state.conversation.append({"role": "bot", "type": "text", "content": bot_reply})


# --------------------- DISPLAY CONVERSATION --------------------
st.markdown("---")
st.markdown("### 💬 Conversation")

if st.session_state.conversation:
    for entry in st.session_state.conversation:
        if entry["role"] == "user":
            if entry.get("type") == "text":
                st.markdown(f"**You:** {entry['content']}")
            elif entry.get("type") == "image":
                st.image(entry["image_bytes"], caption="You uploaded:", width=230)
        else:
            st.markdown(f"**Bot:** {entry['content']}")
else:
    st.info("No conversation yet. Please ask something or upload an image.")
