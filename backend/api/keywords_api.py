"""Keyword detection API endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/keywords", tags=["keywords"])


class KeywordMappingResponse(BaseModel):
    keywords: list[str]
    action: str
    description: str
    skill: Optional[str]


@router.get("/mappings")
async def get_keyword_mappings() -> list[KeywordMappingResponse]:
    """Get all keyword mappings."""
    from backend.core.keyword_detection import KeywordDetector

    detector = KeywordDetector()
    return [
        KeywordMappingResponse(
            keywords=m.keywords,
            action=m.action,
            description=m.description,
            skill=m.skill,
        )
        for m in detector.MAPPINGS
    ]


class DetectRequest(BaseModel):
    text: str


class DetectResponse(BaseModel):
    matches: list[KeywordMappingResponse]
    primary_action: Optional[str]
    extracted_task: str


@router.post("/detect")
async def detect_keywords(request: DetectRequest) -> DetectResponse:
    """Detect keywords in text."""
    from backend.core.keyword_detection import keyword_detector

    matches = keyword_detector.detect(request.text)
    primary = keyword_detector.get_triggered_action(request.text)
    task = keyword_detector.extract_task(request.text, primary) if primary else request.text

    return DetectResponse(
        matches=[
            KeywordMappingResponse(
                keywords=m.keywords,
                action=m.action,
                description=m.description,
                skill=m.skill,
            )
            for m in matches
        ],
        primary_action=primary.action if primary else None,
        extracted_task=task,
    )
