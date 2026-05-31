from __future__ import annotations

import json
import sys
from pathlib import Path


THRESHOLDS = {
    "app/core.py": 90.0,
    "app/gamer.py": 90.0,
    "app/utils.py": 90.0,
    "app/tasks.py": 90.0,
    "app/handlers.py": 70.0,
}


def main(path: str) -> int:
    report_path = Path(path)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    files = payload.get("files", {})

    failures = []
    for relative_path, threshold in THRESHOLDS.items():
        normalized_target = relative_path.replace("\\", "/")
        match = None
        for filename, data in files.items():
            if filename.replace("\\", "/").endswith(normalized_target):
                match = data
                break

        if match is None:
            failures.append(f"Missing coverage data for {relative_path}")
            continue

        actual = match["summary"]["percent_covered"]
        if actual < threshold:
            failures.append(
                f"{relative_path}: {actual:.2f}% < required {threshold:.2f}%"
            )

    if failures:
        print("Coverage threshold check failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Coverage thresholds satisfied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
