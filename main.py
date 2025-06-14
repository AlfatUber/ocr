from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pytesseract
from PIL import Image
import io
import uuid
import os
from typing import Dict
import pdf2image
from langdetect import detect
from googletrans import Translator
import logging
from pydantic import BaseModel

app = FastAPI()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

tasks: Dict[str, dict] = {}

def process_ocr(file_bytes: bytes, content_type: str):
    try:
        pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

        if content_type.startswith("image/"):
            image = Image.open(io.BytesIO(file_bytes))
            return pytesseract.image_to_string(image)
        elif content_type == "application/pdf":
            images = pdf2image.convert_from_bytes(file_bytes)
            return "\n".join(pytesseract.image_to_string(img) for img in images)
        raise ValueError("Type de fichier non supporté")
    except Exception as e:
        logging.error(f"Erreur de traitement OCR: {str(e)}")
        raise

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    file_bytes = await file.read()
    task_id = str(uuid.uuid4())

    tasks[task_id] = {
        "status": "processing",
        "progress": 0,
        "filename": file.filename,
        "text": "",
        "lang": "fr"
    }

    try:
        text = process_ocr(file_bytes, file.content_type)
        lang = detect(text) if text else "fr"

        tasks[task_id] = {
            "status": "done",
            "progress": 100,
            "filename": file.filename,
            "text": text,
            "lang": lang
        }

        return {"task_id": task_id}
    except Exception as e:
        tasks[task_id]["status"] = "error"
        tasks[task_id]["message"] = str(e)
        raise HTTPException(500, str(e))

@app.get("/progress/{task_id}")
async def get_progress(task_id: str):
    if task_id not in tasks:
        raise HTTPException(404, "Tâche introuvable")
    return tasks[task_id]

class TranslateRequest(BaseModel):
    text: str
    target_lang: str

@app.post("/translate")
async def translate_text_post(req: TranslateRequest):
    translator = Translator()
    translation = translator.translate(req.text, dest=req.target_lang)
    return {"translation": translation.text}
