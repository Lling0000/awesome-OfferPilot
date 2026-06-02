import os
from dataclasses import dataclass
from typing import Callable, Dict, Optional


class TranscriptionProviderError(RuntimeError):
    pass


class TranscriptionProviderNotConfigured(TranscriptionProviderError):
    pass


class TranscriptionProviderResponseError(TranscriptionProviderError):
    pass


TranscriptionTransport = Callable[[str, Dict[str, object], Dict[str, str]], object]


@dataclass
class ExternalTranscriptionProvider:
    name: str = "external-transcription-api"
    api_key_env: str = "TRANSCRIPTION_PROVIDER_API_KEY"
    endpoint_env: str = "TRANSCRIPTION_PROVIDER_ENDPOINT"
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    transport: Optional[TranscriptionTransport] = None

    def transcribe(self, file_path: str) -> dict:
        clean_file_path = str(file_path or "").strip()
        if not clean_file_path:
            raise TranscriptionProviderResponseError(
                f"{self.name} requires a non-empty file_path for transcription."
            )

        api_key = _configured_value(self.api_key, self.api_key_env)
        if not api_key:
            raise TranscriptionProviderNotConfigured(
                f"{self.name} requires {self.api_key_env}. Set it in .env or pass "
                "api_key=...; the adapter will not fabricate transcripts."
            )

        endpoint = _configured_value(self.endpoint, self.endpoint_env)
        if not endpoint:
            raise TranscriptionProviderNotConfigured(
                f"{self.name} requires {self.endpoint_env}. Set the provider endpoint "
                "before enabling live transcription."
            )

        if self.transport is None:
            raise TranscriptionProviderNotConfigured(
                f"{self.name} has credentials but no transport configured. Provide a "
                "callable that performs the provider request and returns transcript text."
            )

        payload = {
            "file_path": clean_file_path,
            "privacy": "private_user_context",
            "sourceUrls": [],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "OfferPilot/0.1 TranscriptionProvider",
        }
        return _normalize_transcription_response(
            self.transport(endpoint, payload, headers),
            file_path=clean_file_path,
            provider_name=self.name,
        )


@dataclass
class UnconfiguredExternalTranscriptionProvider(ExternalTranscriptionProvider):
    name: str = "external-transcription"


def _configured_value(explicit_value: Optional[str], env_name: str) -> str:
    return (explicit_value if explicit_value is not None else os.getenv(env_name, "")).strip()


def _normalize_transcription_response(
    response: object,
    file_path: str,
    provider_name: str,
) -> dict:
    if isinstance(response, str):
        raw = {"transcript": response}
    elif isinstance(response, dict):
        raw = response
    else:
        raise TranscriptionProviderResponseError(
            f"{provider_name} transport returned an unsupported payload shape; expected "
            "a transcript string or dict."
        )

    transcript = str(
        raw.get("transcript") or raw.get("text") or raw.get("content") or ""
    ).strip()
    if not transcript:
        raise TranscriptionProviderResponseError(
            f"{provider_name} transport returned no transcript text."
        )

    result = {
        "file_path": file_path,
        "provider": provider_name,
        "privacy": "private_user_context",
        "sourceUrls": [],
        "transcript": transcript,
    }

    confidence = _float_or_none(raw.get("confidence"))
    if confidence is not None:
        result["confidence"] = confidence
    if raw.get("language"):
        result["language"] = raw["language"]
    duration_seconds = _float_or_none(raw.get("duration_seconds"))
    if duration_seconds is not None:
        result["duration_seconds"] = duration_seconds
    if raw.get("quality_notes"):
        result["quality_notes"] = raw["quality_notes"]
    return result


def _float_or_none(value: object) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
