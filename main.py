import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field, ValidationError

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set. Copy .env.example to .env and add your key.")

client = genai.Client(api_key=API_KEY)


class MatchResult(BaseModel):
    match_score: int = Field(ge=0, le=100)
    top_strengths: list[str]
    missing_skills: list[str]
    summary: str


SYSTEM_PROMPT = Path("system_prompt.txt").read_text(encoding="utf-8")


def analyze_resume(resume_text: str, job_description: str, retries: int = 3):
    prompt = f"""{SYSTEM_PROMPT}

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description}
"""

    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": MatchResult,
                    "temperature": 0.1,
                },
            )

            result = MatchResult.model_validate_json(response.text)
            return result.model_dump()

        except ValidationError as exc:
            return {
                "error": "Schema validation failed",
                "details": str(exc),
            }

        except Exception as exc:
            message = str(exc).lower()
            transient = "429" in message or "rate" in message or "timeout" in message

            if transient and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue

            return {
                "error": "AI request failed",
                "details": str(exc),
            }

    return {"error": "Maximum retry attempts exceeded"}


def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


if __name__ == "__main__":
    resume = read_text("samples/resume.txt")
    jd = read_text("samples/job_description.txt")

    output = analyze_resume(resume, jd)
    print(json.dumps(output, indent=2, ensure_ascii=False))
