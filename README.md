# Inquiry Narrator MVP

Flask web app for extracting selectable text from PDF documents and narrating it with browser-provided speech voices.

## Local
`pip install -r requirements.txt`
`python app.py`

## Render deployment
1. Upload these files to a GitHub repository (root of repo).
2. In Render, create a **Web Service** from the repository.
3. Runtime: Python; plan: Free; region: Frankfurt.
4. Build command: `pip install -r requirements.txt`
5. Start command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`

## Limitations
100 MB request cap, selectable-text PDFs only (no OCR), no permanent upload storage, browser-native speech (quality and available voices depend on device), no audio export, no resume across sessions, no server-side large-document job queue. Very large PDFs may hit free-instance RAM/time limits. Do not upload sensitive personal information to a public demo without appropriate safeguards.
