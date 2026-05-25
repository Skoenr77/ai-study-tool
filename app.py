from fastapi import FastAPI, Form, Depends, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import requests
import fitz
import docx
import io
import os
from dotenv import load_dotenv

from database import SessionLocal, engine, Base
from models import User
from auth import hash_password, verify_password

load_dotenv()

app = FastAPI()

Base.metadata.create_all(bind=engine)

app.mount("/static", StaticFiles(directory="static"), name="static")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class NotesRequest(BaseModel):
    notes: str
    mode: str
    language: str


@app.get("/")
def home():
    return RedirectResponse("/login")


@app.get("/login")
def login_page():
    return FileResponse("static/login.html")


@app.get("/register")
def register_page():
    return FileResponse("static/register.html")


@app.get("/dashboard")
def dashboard_page():
    return FileResponse("static/dashboard.html")


@app.post("/register")
def register(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    email = email.lower().strip()

    existing_user = db.query(User).filter(User.email == email).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Email already exists")

    new_user = User(
        username=username.strip(),
        email=email,
        password=hash_password(password)
    )

    db.add(new_user)
    db.commit()

    return RedirectResponse("/login", status_code=302)


@app.post("/login")
def login(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    email = email.lower().strip()

    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid email")

    if not verify_password(password, user.password):
        raise HTTPException(status_code=400, detail="Wrong password")

    return RedirectResponse("/dashboard", status_code=302)


def chunk_text(text, size=12000):
    return [text[i:i + size] for i in range(0, len(text), size)]


def extract_text(uploaded_file, content):
    filename = uploaded_file.filename.lower()

    if filename.endswith(".txt"):
        return content.decode("utf-8", errors="ignore")

    elif filename.endswith(".pdf"):
        text = ""
        pdf = fitz.open(stream=content, filetype="pdf")

        for page in pdf:
            text += page.get_text()

        pdf.close()
        return text

    elif filename.endswith(".docx"):
        file_stream = io.BytesIO(content)
        doc = docx.Document(file_stream)

        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")


def ask_groq(prompt):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.8
    }

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=120
    )

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=response.text)

    result = response.json()
    return result["choices"][0]["message"]["content"]


@app.post("/summarize")
def summarize(data: NotesRequest):
    if not data.notes.strip():
        raise HTTPException(status_code=400, detail="Notes are empty")

    if data.language.lower() == "arabic":
        task_map = {
            "summary": "قم بفهم المحتوى ثم اكتب ملخصًا عربيًا واضحًا ومنظمًا بدون ترجمة حرفية.",
            "keypoints": "استخرج النقاط الرئيسية بالعربية.",
            "quiz": "أنشئ اختبارًا بالعربية مع الإجابات.",
            "flashcards": "أنشئ بطاقات تعليمية بالعربية."
        }
    else:
        task_map = {
            "summary": "Summarize in English.",
            "keypoints": "Extract key points in English.",
            "quiz": "Create quiz questions with answers in English.",
            "flashcards": "Create flashcards in English."
        }

    instruction = task_map.get(data.mode, task_map["summary"])
    prompt = f"{instruction}\n\n{data.notes}"

    result = ask_groq(prompt)

    return {"result": result}


@app.post("/upload-process")
async def upload_process(
    file: UploadFile = File(...),
    mode: str = Form(...),
    language: str = Form(...)
):
    content = await file.read()
    text = extract_text(file, content)

    if not text.strip():
        raise HTTPException(status_code=400, detail="Empty file")

    if language.lower() == "arabic":
        task_map = {
            "summary": "لخص المحتوى بالعربية بشكل طبيعي وواضح.",
            "keypoints": "استخرج النقاط الرئيسية بالعربية.",
            "quiz": "أنشئ اختبارًا بالعربية مع الإجابات.",
            "flashcards": "أنشئ بطاقات تعليمية بالعربية."
        }
    else:
        task_map = {
            "summary": "Summarize in English.",
            "keypoints": "Extract key points in English.",
            "quiz": "Create quiz questions with answers in English.",
            "flashcards": "Create flashcards in English."
        }

    instruction = task_map.get(mode, task_map["summary"])
    chunks = chunk_text(text)
    final_result = []

    for chunk in chunks:
        prompt = f"{instruction}\n\n{chunk}"
        result = ask_groq(prompt)
        final_result.append(result)

    return {"result": "\n\n".join(final_result)}