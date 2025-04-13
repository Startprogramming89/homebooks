import streamlit as st
import os
from pathlib import Path
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from ebooklib import epub
from bs4 import BeautifulSoup
import PyPDF2
import docx
from pptx import Presentation

# Page config
st.set_page_config(page_title="Document Chatbot", page_icon="📚", layout="wide")

# --- Init session state ---
if 'index' not in st.session_state:
    st.session_state.index = None
    st.session_state.processing_complete = False

# --- Readers ---
def read_epub(file_path):
    book = epub.read_epub(file_path)
    text = ""
    for item in book.get_items():
        if isinstance(item, epub.EpubHtml):
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            text += soup.get_text() + "\n"
    return text

def read_pdf(file_path):
    text = ""
    with open(file_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
    return text

def read_docx(file_path):
    doc = docx.Document(file_path)
    return "\n".join(p.text for p in doc.paragraphs)

def read_pptx(file_path):
    prs = Presentation(file_path)
    text = ""
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text += shape.text + "\n"
    return text

def process_file(file_path):
    ext = Path(file_path).suffix.lower()
    if ext == '.epub':
        return read_epub(file_path)
    elif ext == '.pdf':
        return read_pdf(file_path)
    elif ext in ['.docx', '.doc']:
        return read_docx(file_path)
    elif ext in ['.pptx', '.ppt']:
        return read_pptx(file_path)
    elif ext == '.txt':
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        return None

# --- Auto-process book on load ---
book_folder = "books"
os.makedirs(book_folder, exist_ok=True)

uploaded_files = os.listdir(book_folder)
processed_files = []
displayed_files = set()

for file in uploaded_files:
    full_path = os.path.join(book_folder, file)
    ext = Path(file).suffix.lower()

    # Skip already-generated .txt files
    if ext == ".txt":
        continue

    # Prevent duplicate display
    if file not in displayed_files:
        st.info(f"📖 Processing: {file}")
        displayed_files.add(file)

    text = process_file(full_path)
    if text:
        txt_filename = f"{os.path.splitext(full_path)[0]}.txt"
        if not os.path.exists(txt_filename):
            with open(txt_filename, "w", encoding="utf-8") as f:
                f.write(text)
        processed_files.append(txt_filename)

if processed_files:
    documents = SimpleDirectoryReader(input_files=processed_files).load_data()
    Settings.embed_model = OpenAIEmbedding()
    Settings.llm = OpenAI(model="gpt-4o-mini-2024-07-18")
    st.session_state.index = VectorStoreIndex.from_documents(documents)
    st.session_state.processing_complete = True
    st.success("✅ Documents processed successfully!")

# --- Chat Interface ---
st.title("📚 Document Chatbot")

if st.session_state.processing_complete:
    st.header("Chat with your documents")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Example prompts section
    st.markdown("### 📝 Example Questions You Can Ask:")
    example_prompts = [
        "🇩🇪 German Examples:",
        "• Bitte finde und gib den Originalabschnitt oder das Kapitel aus dem Buch \"Babyjahre Entwicklung und Erziehung in den ersten vier Jahren\" zurück, das das Verhalten eines Kindes erklärt, das Dinge auf den Boden wirft. Bitte fasse nichts zusammen, ich möchte den vollständigen Originaltext.",

        "🇬🇧 English Examples:",
        "• Please find and return the original paragraph or chapter in the book \"xxx\" that explains \"the behavior of a child throwing things\". Please do not summarize - I want the full original wording.",
        "• What are the conclusions drawn in these documents?",
        "• Find any references to specific dates or timelines.",
        "• Explain the methodology described in these documents."
    ]

    with st.expander("Click to see example questions"):
        for prompt in example_prompts:
            st.markdown(prompt)

    if prompt := st.chat_input("Ask a question about your documents"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                query_engine = st.session_state.index.as_query_engine()
                response = query_engine.query(prompt)
                st.markdown(response.response)
                st.session_state.messages.append({"role": "assistant", "content": response.response})
else:
    st.info("📂 Please upload documents into the 'books' folder of your app repository.")
