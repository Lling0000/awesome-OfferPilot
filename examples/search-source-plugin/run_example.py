from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main() -> None:
    from example_source import ExampleSearchSource

    from offerpilot.providers import MockSearchProvider

    provider = MockSearchProvider(sources=[ExampleSearchSource()])
    result = provider.search(
        company_name="Example Robotics",
        job_title="Backend Engineer Intern",
        jd_text="Python FastAPI SQL Redis async workflows",
    )
    print(
        json.dumps(
            {
                "sourceUrls": result["source_urls"],
                "searchCoverage": result["search_coverage"],
                "topEvidence": result["evidence"][:2],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
