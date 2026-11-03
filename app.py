import os, re
from flask import Flask, render_template, request, jsonify
import fitz

app = Flask(__name__, template_folder=".")
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/extract")
def extract():
    f = request.files.get("pdf")
    if not f or not f.filename.lower().endswith(".pdf"):
        return jsonify(error="Please upload a PDF file."), 400
    try:
        doc = fitz.open(stream=f.read(), filetype="pdf")
        if doc.needs_pass:
            return jsonify(error="Password-protected PDFs are not supported."), 400
        pages = []
        for i, page in enumerate(doc):
            content = re.sub(r"\s+", " ", page.get_text("text")).strip()
            if content:
                pages.append({"number": i + 1, "text": content})
        if not pages:
            return jsonify(error="No selectable text found. Scanned PDFs require OCR, which is not yet supported."), 422
        return jsonify(title=f.filename, page_count=len(doc), pages=pages)
    except Exception:
        return jsonify(error="Could not read this PDF."), 422

@app.errorhandler(413)
def too_large(_):
    return jsonify(error="PDF exceeds the 100 MB upload limit."), 413

if __name__ == "__main__":
    app.run(debug=True)
