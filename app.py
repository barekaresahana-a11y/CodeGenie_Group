import streamlit as st
import random
import os
import shutil
import io
import copy

import google.generativeai as genai  # Gemini SDK

# ---------- OCR IMPORTS ----------
from PIL import Image
import pytesseract

# ---------- PAGE SETUP ----------
st.set_page_config(page_title="Gemini Chatbot 💬", page_icon="🤖", layout="wide")
st.title("🤖 Chatbot")

# ---------- 🔑 GEMINI API CONFIGURATION ----------
# Replace with your actual Gemini API key or keep env var

os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
model = genai.GenerativeModel("gemini-2.5-flash-preview-09-2025")

# ---------- TESSERACT AUTO-DETECT ----------
def find_tesseract():
    exe = shutil.which("tesseract")
    if exe:
        return exe
    possible = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
    ]
    for p in possible:
        if os.path.exists(p):
            return p
    return None

tesseract_path = find_tesseract()
if tesseract_path:
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
else:
    st.warning("Tesseract executable not found on PATH or common locations. If OCR fails, install Tesseract and add it to PATH or set the path manually.")

# ---------- SIDEBAR (CHAT HISTORY + OCR Options + PDF Settings) ----------
with st.sidebar:
    st.header("💬 Chat History")
    if "saved_chats" not in st.session_state:
        st.session_state.saved_chats = []

    for i, chat in enumerate(st.session_state.saved_chats):
        if st.button(f" Chat {i+1}"):
            st.session_state["messages"] = copy.deepcopy(chat)

    st.markdown("---")
    if st.button("🗑️ Clear Chat"):
        st.session_state["messages"] = []
        st.success("Chat cleared!")

    # OCR options (hidden from main chat output)
    #with st.expander("OCR Options (hidden from chat output)", expanded=True):
        #lang = st.text_input("OCR language (e.g. 'eng' or 'eng+hin')", value="eng", key="ocr_lang")
        #psm = st.selectbox("PSM (page segmentation mode)", ["3", "6", "7", "11"], index=1, key="ocr_psm")
        #oem = st.selectbox("OEM (engine mode)", ["0", "1", "2", "3"], index=3, key="ocr_oem")

    # PDF OCR Settings (for scanned PDFs)
    with st.expander("PDF OCR Settings", expanded=False):
        st.write("If you're on Windows, paste the Poppler 'Library\\bin' folder path here (or leave blank if Poppler is on PATH).")
        poppler_path = st.text_input(
            "poppler_path (Windows users only)",
            value="",
            placeholder=r"C:\poppler-23.11.0\Library\bin",
            key="poppler_path"
        )
        max_pages = st.number_input(
            "Max PDF pages to OCR (scanned PDFs)",
            min_value=1,
            max_value=100,
            value=10,
            step=1,
            key="max_pdf_pages"
        )

# ---------- SESSION STATE ----------
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# ---------- GEMINI BOT RESPONSE FUNCTION ----------
def gemini_bot_response(user_prompt):
    try:
        response = model.generate_content(user_prompt)
        return response.text if hasattr(response, "text") else str(response)
    except Exception as e:
        return f"⚠️ Gemini API Error: {e}"

# ---------- CHAT DISPLAY AREA ----------
chat_container = st.container()
with chat_container:
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

st.markdown("<br><hr>", unsafe_allow_html=True)

# ---------- USER INPUT + FILE UPLOAD (no OCR options here) ----------
with st.container():
    col1, col2 = st.columns([8, 2])

    with col1:
        user_input = st.text_input("Type your message (optional if you upload files)...", key="input_bar")

    with col2:
        uploaded_files = st.file_uploader(
            "📎 Upload Files",
            type=["txt", "pdf", "docx", "png", "jpg", "jpeg"],
            accept_multiple_files=True,
            label_visibility="collapsed"
        )
        if uploaded_files:
            st.write("✅ Files uploaded:")
            for f in uploaded_files:
                st.write(f"- {f.name}")

    send = st.button("Send")

# ---------- HELPER: RUN OCR ON IMAGE FILE-LIKE ----------
def run_ocr_on_image(file_like, lang="eng", psm="3", oem="3"):
    try:
        img = Image.open(file_like).convert("RGB")
    except Exception as e:
        return f"[Error opening image: {e}]"

    config = f"--oem {oem} --psm {psm}"
    try:
        text = pytesseract.image_to_string(img, lang=lang, config=config)
    except pytesseract.TesseractNotFoundError:
        return "[Tesseract executable not found — install Tesseract and/or set pytesseract.pytesseract.tesseract_cmd]"
    except Exception as e:
        return f"[OCR error: {e}]"

    return text.strip()

# ---------- PROCESS USER INPUT OR UPLOADED FILES ----------
# NOTE: OCR options and PDF settings are read from sidebar widget keys
if send and (user_input or uploaded_files):
    # If user typed something, add it to chat
    if user_input:
        st.session_state["messages"].append({"role": "user", "content": user_input})
    else:
        # If no typed message, add a small placeholder to indicate the user uploaded files
        st.session_state["messages"].append({"role": "user", "content": "📂 Uploaded files (no typed message). Please respond to their contents."})

    # read OCR options from sidebar state
    lang = st.session_state.get("ocr_lang", "eng")
    psm = st.session_state.get("ocr_psm", "3")
    oem = st.session_state.get("ocr_oem", "3")

    # read PDF settings from sidebar state
    poppler_path = st.session_state.get("poppler_path", "") or None
    max_pages = int(st.session_state.get("max_pdf_pages", 10))

    # Process uploaded files and automatically send OCR/text as user messages
    ocr_summaries = []
    if uploaded_files:
        for f in uploaded_files:
            name = f.name.lower()

            # IMAGE -> OCR and send as a user message
            if name.endswith((".png", ".jpg", ".jpeg")):
                st.info(f"Running OCR on image: {f.name}")
                ocr_text = run_ocr_on_image(f, lang=lang, psm=psm, oem=oem)
                if ocr_text:
                    # show extracted text to user
                    st.subheader(f"📄 Extracted from {f.name}")
                    st.text_area(f"Extracted text — {f.name}", value=ocr_text, height=200, key=f"ocr_{f.name}_{random.random()}")

                    # AUTOMATICALLY send OCR result as a user message (so Gemini sees it)
                    user_msg_content = f"Extracted text from {f.name}:\n{ocr_text}"
                    st.session_state["messages"].append({"role": "user", "content": user_msg_content})
                    ocr_summaries.append(user_msg_content)
                else:
                    st.write(f"No text extracted from {f.name}.")

            # TXT -> read and send as user message
            elif name.endswith(".txt"):
                try:
                    raw = f.getvalue().decode("utf-8", errors="ignore")
                    st.subheader(f"📄 Contents of {f.name}")
                    st.text_area(f"{f.name}", value=raw, height=200, key=f"text_{f.name}")
                    user_msg_content = f"Contents of {f.name}:\n{raw}"
                    st.session_state["messages"].append({"role": "user", "content": user_msg_content})
                    ocr_summaries.append(user_msg_content)
                except Exception as e:
                    st.write(f"Could not read {f.name}: {e}")

            # PDF -> try searchable text first, otherwise convert pages to images + OCR
            elif name.endswith(".pdf"):
                st.info(f"Processing PDF: {f.name}")
                try:
                    import PyPDF2
                    reader = PyPDF2.PdfReader(io.BytesIO(f.getvalue()))
                    pdf_text_pages = []
                    for page in reader.pages:
                        try:
                            page_text = page.extract_text() or ""
                        except Exception:
                            page_text = ""
                        pdf_text_pages.append(page_text)

                    pdf_text_combined = "\n".join([p for p in pdf_text_pages if p]).strip()

                    if pdf_text_combined:
                        # If searchable text found, display & send it
                        st.subheader(f"📄 Extracted text (PDF) — {f.name}")
                        st.text_area(f"{f.name}", value=pdf_text_combined, height=200, key=f"pdf_{f.name}")
                        user_msg_content = f"PDF text from {f.name}:\n{pdf_text_combined}"
                        st.session_state["messages"].append({"role": "user", "content": user_msg_content})
                        ocr_summaries.append(user_msg_content)
                    else:
                        # No searchable text -> do image OCR using pdf2image + pytesseract
                        st.write("No embedded selectable text found — performing OCR on PDF pages (this may take time).")

                        try:
                            from pdf2image import convert_from_bytes
                        except ModuleNotFoundError:
                            st.write("pdf2image not installed. Install with `pip install pdf2image`. Also install Poppler on your system.")
                            continue

                        # convert PDF pages to images
                        try:
                            images = convert_from_bytes(f.getvalue(), dpi=200, poppler_path=poppler_path)
                        except Exception as e:
                            st.write(f"Error converting PDF pages to images: {e}")
                            st.write("On Windows set `poppler_path` in the sidebar to the Poppler 'Library\\bin' folder.")
                            continue

                        # Process only first N pages to avoid long runs
                        page_texts = []
                        for i, page_image in enumerate(images[:max_pages], start=1):
                            st.info(f"Running OCR on {f.name} — page {i}")
                            try:
                                page_bytes_io = io.BytesIO()
                                page_image.save(page_bytes_io, format="PNG")
                                page_bytes_io.seek(0)
                                page_ocr_text = run_ocr_on_image(page_bytes_io, lang=lang, psm=psm, oem=oem)
                            except Exception as e:
                                page_ocr_text = f"[OCR error on page {i}: {e}]"

                            # show per-page results
                            st.subheader(f"📄 Extracted (page {i}) — {f.name}")
                            st.text_area(f"{f.name} - page {i}", value=page_ocr_text, height=200, key=f"pdf_{f.name}_page_{i}")

                            page_texts.append(f"--- Page {i} ---\n{page_ocr_text}")

                        combined_pdf_ocr = "\n\n".join(page_texts).strip()
                        if combined_pdf_ocr:
                            user_msg_content = f"OCR text from scanned PDF {f.name}:\n{combined_pdf_ocr}"
                            st.session_state["messages"].append({"role": "user", "content": user_msg_content})
                            ocr_summaries.append(user_msg_content)
                        else:
                            st.write("No text could be extracted from scanned PDF pages.")

                except ModuleNotFoundError:
                    st.write("PyPDF2 not installed. Install it with `pip install PyPDF2` to extract searchable text from PDFs.")
                except Exception as e:
                    st.write(f"PDF processing error: {e}")

            # DOCX -> extract text with python-docx if available
            elif name.endswith(".docx"):
                st.info(f"Processing DOCX: {f.name}")
                try:
                    import docx
                    doc = docx.Document(io.BytesIO(f.getvalue()))
                    paragraphs = [p.text for p in doc.paragraphs]
                    doc_text = "\n".join(paragraphs).strip()
                    st.subheader(f"📄 Extracted text (DOCX) — {f.name}")
                    st.text_area(f"{f.name}", value=doc_text, height=200, key=f"docx_{f.name}")
                    user_msg_content = f"DOCX text from {f.name}:\n{doc_text}"
                    st.session_state["messages"].append({"role": "user", "content": user_msg_content})
                    ocr_summaries.append(user_msg_content)
                except ModuleNotFoundError:
                    st.write("python-docx not installed. Install it with `pip install python-docx` to extract text from .docx files.")
                except Exception as e:
                    st.write(f"DOCX error: {e}")

            else:
                st.write(f"Unsupported file type for automatic processing: {f.name}")

    # Build the prompt to send to Gemini:
    combined_ocr_text = "\n\n".join(ocr_summaries) if ocr_summaries else ""
    if user_input and combined_ocr_text:
        prompt_to_gemini = f"{user_input}\n\nAttached files contents:\n{combined_ocr_text}"
    elif user_input:
        prompt_to_gemini = user_input
    elif combined_ocr_text:
        prompt_to_gemini = combined_ocr_text
    else:
        prompt_to_gemini = "No user message or file content to send."

    # Send prompt to Gemini and display assistant reply
    with st.chat_message("assistant"):
        with st.spinner("Thinking with Gemini... 🤖"):
            reply = gemini_bot_response(prompt_to_gemini)
            st.markdown(reply)

    st.session_state["messages"].append({"role": "assistant", "content": reply})
    # deep copy messages when saving to avoid storing references
    st.session_state.saved_chats.append(copy.deepcopy(st.session_state["messages"]))
