from offerpilot.providers import MockProviderBundle


class MockAgentProvider:
    """Deterministic provider that proves the product flow without external keys."""

    def __init__(self) -> None:
        self.providers = MockProviderBundle()

    def parse_job_link(self, url: str) -> dict:
        return self.providers.job_link_parser.parse(url)

    def forced_search(self, company_name: str, job_title: str, jd_text: str) -> dict:
        return self.providers.search_provider.search(company_name, job_title, jd_text)

    def transcribe_audio(self, file_path: str) -> dict:
        return self.providers.transcription_provider.transcribe(file_path)

    def analyze_interview(self, transcript: str) -> dict:
        return self.providers.interview_analyzer.analyze(transcript)
