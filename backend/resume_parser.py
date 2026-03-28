import json
import os
from io import BytesIO

from anthropic import Anthropic
from pypdf import PdfReader

from logging_utils import format_fields, get_logger
from models import UserProfile


logger = get_logger("jobswarm.resume_parser")

RESUME_PARSER_SYSTEM_PROMPT = """You are a resume parsing assistant. \
Extract structured information from resume text.

Respond ONLY with valid JSON in this exact format:
{
  "first_name": "string",
  "last_name": "string",
  "email": "string",
  "phone": "string",
  "location": "string",
  "linkedin_url": "string",
  "github_url": "string",
  "current_title": "string",
  "years_of_experience": "string",
  "education": "string",
  "skills": ["string"]
}

Guidelines:
- Extract the most recent job title as current_title
- For years_of_experience, calculate total years from work history
- For education, include degree and institution
- Extract ALL technical skills mentioned
- Leave fields as empty strings "" if not found
- For LinkedIn/GitHub, extract full URLs if present"""


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF bytes using pypdf."""
    logger.info(
        "Starting PDF text extraction %s",
        format_fields(file_size_bytes=len(file_bytes)),
    )

    try:
        reader = PdfReader(BytesIO(file_bytes))
        text_parts = []

        for page_num, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
            logger.info(
                "Extracted text from page %s",
                format_fields(page_num=page_num, text_length=len(page_text)),
            )

        full_text = "\n".join(text_parts)
        logger.info(
            "PDF text extraction complete %s",
            format_fields(
                total_pages=len(reader.pages), total_text_length=len(full_text)
            ),
        )
        return full_text
    except Exception as exc:
        logger.exception("PDF text extraction failed %s", format_fields(error=str(exc)))
        raise


def parse_resume_with_ai(resume_text: str) -> UserProfile:
    """Parse resume text using Claude API to extract structured profile data."""
    logger.info(
        "Starting AI resume parsing %s",
        format_fields(resume_text_length=len(resume_text)),
    )

    api_key_present = bool(os.getenv("ANTHROPIC_API_KEY"))
    logger.info(
        "Claude client initialization %s",
        format_fields(anthropic_api_key_present=api_key_present),
    )

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    try:
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=2000,
            temperature=0.3,
            system=RESUME_PARSER_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": f"Parse this resume:\n\n{resume_text}"}
            ],
        )
        logger.info(
            "AI parsing response received %s",
            format_fields(
                model=response.model,
                stop_reason=response.stop_reason,
            ),
        )

        result = json.loads(response.content[0].text)
        logger.info(
            "Parsed resume data %s",
            format_fields(
                first_name=result.get("first_name", ""),
                last_name=result.get("last_name", ""),
                email=result.get("email", ""),
                current_title=result.get("current_title", ""),
                skills_count=len(result.get("skills", [])),
            ),
        )

        profile = UserProfile(**result)
        logger.info("Resume parsing completed successfully")
        return profile
    except Exception as exc:
        logger.exception("AI resume parsing failed %s", format_fields(error=str(exc)))
        raise
