Run from the repository root with Python 3.12 and the dependencies in requirements.txt:

    python -m unittest discover -s tests -v

Install Chromium first: python -m playwright install chromium

The tests use temporary artifacts and controlled API responses; no live model key is required. See the repository README for scope and limits.
