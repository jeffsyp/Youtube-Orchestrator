"""Writing service — generates outlines, scripts, critiques, and revisions using Claude."""

import json

import structlog

from packages.clients.claude import generate, generate_cheap
from packages.prompts.writing import (
    build_outline_prompt,
    critique_script_prompt,
    revise_script_prompt,
    write_script_prompt,
)
from packages.schemas.writing import IdeaVariant, OutlineDraft, ScriptDraft, ScriptStage

logger = structlog.get_logger()


def _parse_json(text: str) -> dict:
    """Extract JSON from a response that might have markdown fencing or be truncated."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1 if lines[0].startswith("```") else 0
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        fixed = text.rstrip()
        if fixed.count('"') % 2 != 0:
            fixed += '"'
        fixed += "}" * (fixed.count("{") - fixed.count("}"))
        fixed += "]" * (fixed.count("[") - fixed.count("]"))
        return json.loads(fixed)


def build_outline(idea: dict, niche: str) -> OutlineDraft:
    """Generate a structured outline from a video idea."""
    log = logger.bind(service="writing", action="build_outline", idea=idea["title"])
    log.info("generating outline")

    system, user = build_outline_prompt(idea, niche)
    response = generate(user, system=system, max_tokens=2048, temperature=0.7)
    data = _parse_json(response)

    outline = OutlineDraft(**data)
    log.info("outline generated", sections=len(outline.sections))
    return outline


def write_script(outline: dict, niche: str, tone: str) -> ScriptDraft:
    """Write a full script from an outline."""
    log = logger.bind(service="writing", action="write_script", idea=outline["idea_title"])
    log.info("writing script")

    system, user = write_script_prompt(outline, niche, tone)
    content = generate(user, system=system, max_tokens=4096, temperature=0.7)

    word_count = len(content.split())
    script = ScriptDraft(
        idea_title=outline["idea_title"],
        stage=ScriptStage.DRAFT,
        content=content,
        word_count=word_count,
    )
    log.info("script written", word_count=word_count)
    return script


def critique_script(script: dict) -> ScriptDraft:
    """Generate a critique of a script."""
    log = logger.bind(service="writing", action="critique", idea=script["idea_title"])
    log.info("critiquing script")

    system, user = critique_script_prompt(script["content"], script["idea_title"])
    critique = generate(user, system=system, max_tokens=2048, temperature=0.5)

    result = ScriptDraft(
        idea_title=script["idea_title"],
        stage=ScriptStage.CRITIQUE,
        content=script["content"],
        word_count=script["word_count"],
        critique_notes=critique,
    )
    log.info("critique generated")
    return result


def revise_script(critique: dict, tone: str) -> ScriptDraft:
    """Revise a script based on critique notes."""
    log = logger.bind(service="writing", action="revise", idea=critique["idea_title"])
    log.info("revising script")

    system, user = revise_script_prompt(
        critique["content"], critique["critique_notes"], critique["idea_title"], tone
    )
    revised = generate(user, system=system, max_tokens=4096, temperature=0.6)

    word_count = len(revised.split())
    result = ScriptDraft(
        idea_title=critique["idea_title"],
        stage=ScriptStage.FINAL,
        content=revised,
        word_count=word_count,
    )
    log.info("script revised", word_count=word_count)
    return result
