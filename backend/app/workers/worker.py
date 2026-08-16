"""Background worker entrypoint.

Phase 1 establishes the process boundary. Speech orchestration will be added in
Phase 2; this module intentionally does not claim to process evidence yet.
"""

import time


def main() -> None:
    print("Bayenat worker started; Phase 1 queue consumer is not enabled yet.")
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
