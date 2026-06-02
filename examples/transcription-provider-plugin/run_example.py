from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main() -> None:
    from example_transport import fixture_transcription_transport

    from offerpilot.providers import ExternalTranscriptionProvider

    provider = ExternalTranscriptionProvider(
        api_key="fixture-api-key",
        endpoint="https://stt.example.test/v1/transcriptions",
        transport=fixture_transcription_transport,
    )
    result = provider.transcribe("example-technical-round.m4a")
    print(
        json.dumps(
            {
                "provider": result["provider"],
                "file_path": result["file_path"],
                "privacy": result["privacy"],
                "sourceUrls": result["sourceUrls"],
                "confidence": result.get("confidence"),
                "language": result.get("language"),
                "duration_seconds": result.get("duration_seconds"),
                "transcriptPreview": result["transcript"][:120],
                "quality_notes": result.get("quality_notes", []),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
