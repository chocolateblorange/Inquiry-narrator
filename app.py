import os, re, html, urllib.request, urllib.error
from flask import Response
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


# Expressive synthesis is strictly opt-in. No cloud requests occur without credentials
# and the user explicitly selecting the expressive engine.
EXPRESSIVE_STYLES = {
    "neutral": "general", "sombre": "sad", "empathetic": "friendly",
    "serious": "newscast", "urgent": "newscast", "reflective": "general",
    "uplifting": "hopeful",
}

@app.get("/speech-capabilities")
def speech_capabilities():
    enabled = bool(os.environ.get("AZURE_SPEECH_KEY") and os.environ.get("AZURE_SPEECH_REGION"))
    return jsonify(expressive_available=enabled, provider="Azure Speech" if enabled else None)

@app.post("/synthesize")
def synthesize():
    if not (os.environ.get("AZURE_SPEECH_KEY") and os.environ.get("AZURE_SPEECH_REGION")):
        return jsonify(error="Expressive narration is not configured."), 503
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    tone = data.get("tone", "serious")
    if not isinstance(text, str) or not text.strip() or len(text) > 900:
        return jsonify(error="Invalid speech segment."), 400
    if tone not in EXPRESSIVE_STYLES:
        return jsonify(error="Invalid tone."), 400
    try:
        intensity = max(0, min(100, int(data.get("intensity", 35))))
        rate = max(.7, min(1.4, float(data.get("rate", 1))))
    except (ValueError, TypeError):
        return jsonify(error="Invalid speech settings."), 400
    # British male neural narration. Ryan does not support every Azure express-as
    # style, so use broadly supported SSML prosody rather than unsupported styles.
    # Keep contextual instructions and the author's words intact.
    strength = intensity / 100.0
    tone_adjustments = {
        "neutral": (0, 0), "sombre": (-9, -3),
        "empathetic": (-4, 0), "serious": (-3, -2),
        "urgent": (5, 1), "reflective": (-6, -1),
        "uplifting": (2, 1),
    }
    rate_shift, pitch_shift = tone_adjustments[tone]
    effective_rate = max(0.78, min(1.2, rate * (1 + rate_shift * strength / 100)))
    effective_pitch = pitch_shift * strength
    escaped = html.escape(text, quote=False)
    content = (f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-GB">'
               f'<voice name="en-GB-RyanNeural">'
               f'<prosody rate="{(effective_rate-1)*100:+.0f}%" pitch="{effective_pitch:+.1f}%">'
               f'{escaped}</prosody></voice></speak>')
    region = os.environ["AZURE_SPEECH_REGION"]
    if not re.fullmatch(r"[a-z0-9-]{2,40}", region):
        return jsonify(error="Speech region configuration is invalid."), 503
    req = urllib.request.Request(
        f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
        data=content.encode("utf-8"),
        headers={"Ocp-Apim-Subscription-Key": os.environ["AZURE_SPEECH_KEY"],
                 "Content-Type": "application/ssml+xml",
                 "X-Microsoft-OutputFormat": "audio-24khz-96kbitrate-mono-mp3",
                 "User-Agent": "ACCESSIRATE"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            audio = response.read()
        return Response(audio, mimetype="audio/mpeg", headers={"Cache-Control": "no-store"})
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return jsonify(error="Expressive speech service unavailable. Switch to device voice."), 502

def narration_text(page):
    """Conservatively omit small bottom-of-page notes, keeping the PDF unchanged."""
    height = page.rect.height
    body = []
    skipped = 0
    for block in page.get_text("dict").get("blocks", []):
        if "lines" not in block:
            continue
        lines = block["lines"]
        text = " ".join(span.get("text", "") for line in lines for span in line.get("spans", [])).strip()
        if not text:
            continue
        sizes = [span.get("size", 12) for line in lines for span in line.get("spans", []) if span.get("text", "").strip()]
        avg_size = sum(sizes) / len(sizes) if sizes else 12
        y = block["bbox"][1]
        # Only remove plausible footnote material in the lower page margin.
        if y > height * .78 and avg_size <= 9.5 and re.match(
            r"^(?:\[?\d+\]?|\d+[.)]|[*†‡]|https?://|www\.|ibid\b|op\.\s*cit\.)", text, re.I
        ):
            skipped += 1
            continue
        body.append(text)
    return "\n\n".join(body), skipped


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
        skipped_notes = 0
        skip_references = request.form.get("skip_references", "true") == "true"
        for i, page in enumerate(doc):
            content = re.sub(r"\s+", " ", page.get_text("text")).strip()
            if content:
                pages.append({"number": i + 1, "text": content})
        if not pages:
            return jsonify(error="No selectable text found. Scanned PDFs require OCR, which is not yet supported."), 422
        return jsonify(title=f.filename, page_count=len(doc), pages=pages, skipped_notes=skipped_notes)
    except Exception:
        return jsonify(error="Could not read this PDF."), 422

@app.errorhandler(413)
def too_large(_):
    return jsonify(error="PDF exceeds the 100 MB upload limit."), 413

if __name__ == "__main__":
    app.run(debug=True)
