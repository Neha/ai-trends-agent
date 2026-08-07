"""Run the full pipeline: fetch -> analyze -> render.

Usage:
    python run.py
"""

import analyze
import fetch
import render


def main() -> None:
    fetch.main()
    analyze.main()
    render.main()
    print("\nDone. Open index.html to view the digest.")


if __name__ == "__main__":
    main()
