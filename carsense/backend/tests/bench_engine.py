"""Time InferenceEngine.run and save the numbers to report/logs.

Run from backend/:  python tests/bench_engine.py
"""

import platform
import sys
import time
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from carsense.knowledge.knowledge_base import KnowledgeBase  # noqa: E402
from carsense.reasoning.inference_engine import InferenceEngine  # noqa: E402
from carsense.reasoning.working_memory import WorkingMemory  # noqa: E402

RUNS = 100

SCENARIOS = [
    ("R1 fires, audio agrees",
     {"sound": "squealing", "timing": ["braking"], "location": "wheels"},
     {"sound": "squealing", "similarity": 0.8}),
    ("R5 fires, stop driving",
     {"sound": "knocking", "timing": ["with_engine_speed"], "location": "engine_lower"},
     None),
    ("R7 fires, R8 partial",
     {"sound": "hissing", "location": "engine_bay", "symptom": ["running_hot"]},
     None),
    ("No match, uncertain",
     {"sound": "whining", "timing": ["braking"], "location": "underneath"},
     None),
    ("Empty answers", {}, None),
]


def time_scenario(engine: InferenceEngine, answers: dict, audio: dict | None) -> float:
    start = time.perf_counter()
    for _ in range(RUNS):
        engine.run(WorkingMemory.from_answers(answers, audio))
    return (time.perf_counter() - start) / RUNS * 1000


def main() -> None:
    start = time.perf_counter()
    kb = KnowledgeBase.load(REPO_ROOT / "kb")
    load_ms = (time.perf_counter() - start) * 1000
    engine = InferenceEngine(kb)
    engine.run(WorkingMemory())

    lines = [
        f"CarSense inference engine timing, {datetime.now():%Y-%m-%d %H:%M}",
        f"Python {platform.python_version()}, {platform.system()} {platform.release()}, "
        f"{platform.processor() or platform.machine()}",
        f"{len(kb.rules())} rules, {RUNS} runs per scenario "
        f"(each run builds working memory and calls run())",
        "",
        f"{'Scenario':<28}{'Avg ms per run':>16}",
    ]
    timings = []
    for name, answers, audio in SCENARIOS:
        ms = time_scenario(engine, answers, audio)
        timings.append(ms)
        lines.append(f"{name:<28}{ms:>16.4f}")
    lines += [
        f"{'Average':<28}{sum(timings) / len(timings):>16.4f}",
        "",
        f"Knowledge base load and validate: {load_ms:.2f} ms",
    ]

    report = "\n".join(lines) + "\n"
    print(report)
    out = REPO_ROOT / "report" / "logs" / "engine_timing.txt"
    out.write_text(report, encoding="utf-8")
    print(f"Saved to {out.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
