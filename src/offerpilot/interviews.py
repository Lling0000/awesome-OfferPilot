from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from offerpilot.agents import MockAgentProvider
from offerpilot.models import AgentRun, Application, Interview, User


class InterviewIntakeError(ValueError):
    pass


def run_interview_intake(
    session: Session,
    user: User,
    application_id: str,
    stage: str = "technical",
    typed_note: str = "",
    audio_file_name: Optional[str] = None,
) -> Dict[str, str]:
    """Create an interview record from voice/file input or typed notes."""

    application = session.get(Application, application_id)
    if not application or application.user_id != user.id:
        raise InterviewIntakeError("Application not found")

    provider = MockAgentProvider()
    transcript_parts = []
    transcription = None
    clean_note = typed_note.strip()
    clean_file_name = audio_file_name.strip() if audio_file_name else None

    if clean_file_name:
        transcription = provider.transcribe_audio(clean_file_name)
        transcript_parts.append(transcription["transcript"])

    if clean_note:
        transcript_parts.append(clean_note)

    if not transcript_parts:
        raise InterviewIntakeError("Interview intake needs an audio file or typed notes")

    transcript = "\n\n".join(transcript_parts)
    analysis = provider.analyze_interview(transcript)

    run = AgentRun(
        user_id=user.id,
        run_type="interview_analysis",
        status="succeeded",
        input_json={
            "application_id": application.id,
            "stage": stage,
            "audio_file_name": clean_file_name,
            "has_typed_note": bool(clean_note),
        },
        output_json={
            "summary": analysis["summary"],
            "questions": analysis["questions"],
            "next_focus": analysis["next_focus"],
        },
        started_at=datetime.utcnow(),
        ended_at=datetime.utcnow(),
    )
    session.add(run)
    session.flush()

    interview = Interview(
        user_id=user.id,
        application_id=application.id,
        stage=stage,
        status="completed",
        scheduled_at=None,
        location="Uploaded interview artifact" if clean_file_name else "Typed interview notes",
        interviewer=None,
        transcript_text=transcript,
        summary_json={
            **analysis,
            "transcription": transcription,
            "audio_file_name": clean_file_name,
            "typed_note_present": bool(clean_note),
            "agent_run_id": run.id,
        },
        feedback_text=clean_note or None,
    )
    session.add(interview)
    session.flush()

    return {
        "interview_id": interview.id,
        "agent_run_id": run.id,
        "questions_count": str(len(analysis["questions"])),
    }
