import re
from io import BytesIO
from pathlib import Path

from docx import Document
from fastapi import HTTPException, UploadFile, status
from pypdf import PdfReader

MAX_RESUME_BYTES = 5 * 1024 * 1024
MAX_CONTEXT_CHARS = 12_000
ALLOWED_SUFFIXES = {".pdf", ".docx"}


async def extract_resume(file: UploadFile) -> tuple[str, str]:
    filename = Path(file.filename or "resume").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Upload a PDF or DOCX resume.")

    content = await file.read(MAX_RESUME_BYTES + 1)
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The resume is empty.")
    if len(content) > MAX_RESUME_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="The resume must be 5 MB or smaller.")

    try:
        text = (
            "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages)
            if suffix == ".pdf"
            else "\n".join(paragraph.text for paragraph in Document(BytesIO(content)).paragraphs)
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The resume could not be read.") from exc

    context = sanitize_resume_text(text)
    if len(context) < 40:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The resume does not contain enough readable text.",
        )
    return filename, context


def sanitize_resume_text(text: str) -> str:
    text = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[email removed]", text)
    text = re.sub(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)", "[phone removed]", text)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", text)).strip()[:MAX_CONTEXT_CHARS]
