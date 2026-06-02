def fixture_transcription_transport(endpoint: str, payload: dict, headers: dict) -> dict:
    """Deterministic transport for ExternalTranscriptionProvider examples."""
    if payload.get("privacy") != "private_user_context":
        raise ValueError("Transcription payload must stay private user context.")
    if payload.get("sourceUrls") != []:
        raise ValueError("Transcription payload must not carry public source URLs.")
    if not headers.get("Authorization", "").startswith("Bearer "):
        raise ValueError("Transcription transport expected a bearer token header.")

    file_path = payload.get("file_path", "interview.m4a")
    return {
        "transcript": (
            f"Fixture transcript for {file_path}. The interviewer asked about SQL indexes, "
            "project depth, and how I would prepare a clearer backend story."
        ),
        "confidence": 0.86,
        "language": "en",
        "duration_seconds": 92,
        "quality_notes": [
            "Fictional fixture output.",
            "No audio bytes were read and no network request was made.",
        ],
        "sourceUrls": ["https://example.com/provider-returned-url-that-will-be-dropped"],
    }
