"""
Flask Application for AI Voice FAQ Bot
Provides REST APIs for Voice/Text Query Answering, Semantic Search, Pipeline X-Ray,
FAQ Management, Document Ingestion, and Real-Time Telemetry.
"""

import os
import sys
import time
import json
import base64

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from flask import Flask, request, jsonify, render_template, send_from_directory
from faq_engine import FAQEngine
from speech import SpeechProcessor
from tts import TTSProcessor

# Initialize Flask app
app = Flask(__name__, template_folder="templates", static_folder="static")

# Core services
engine = FAQEngine()
speech_processor = SpeechProcessor()
tts_processor = TTSProcessor()

# Analytics Store (In-Memory with seed data for rich presentation)
analytics_store = {
    "total_queries": 1420,
    "total_latency_ms": 1420 * 78.4,
    "successful_matches": 1345,
    "domain_counts": {
        "jee_mhtcet": 420,
        "nda": 380,
        "college_admissions": 310,
        "tech_careers": 210,
        "customer_support": 100
    },
    "language_counts": {
        "en": 1090,
        "hi": 210,
        "mr": 120
    },
    "recent_queries": [
        {
            "id": "q_init_1",
            "query": "What is the cutoff for top NIT Computer Science?",
            "domain": "jee_mhtcet",
            "confidence": 94.2,
            "latency_ms": 68.2,
            "timestamp": "Just now",
            "language": "en"
        },
        {
            "id": "q_init_2",
            "query": "How many days is the SSB interview at NDA?",
            "domain": "nda",
            "confidence": 98.1,
            "latency_ms": 74.0,
            "timestamp": "1m ago",
            "language": "en"
        },
        {
            "id": "q_init_3",
            "query": "What documents are required for JoSAA counseling?",
            "domain": "college_admissions",
            "confidence": 91.5,
            "latency_ms": 82.5,
            "timestamp": "3m ago",
            "language": "en"
        }
    ]
}


@app.route("/")
def index():
    """Serves the main application page."""
    # Check if templates/index.html exists, otherwise serve root index.html
    template_path = os.path.join(app.root_path, "templates", "index.html")
    if os.path.exists(template_path):
        return render_template("index.html")
    return send_from_directory(app.root_path, "index.html")


@app.route("/<path:path>")
def static_files(path):
    """Fallback static file server."""
    if os.path.exists(os.path.join(app.root_path, path)):
        return send_from_directory(app.root_path, path)
    return ("Not Found", 404)


@app.route("/api/transcribe", methods=["POST"])
def api_transcribe():
    """
    Accepts raw audio (base64 WAV) and transcribes it via SpeechProcessor.
    Provides bulletproof fallback for when browser Web Speech API fails.
    """
    data = request.get_json(silent=True) or {}
    audio_b64 = data.get("audio", "")
    language = data.get("language", "en")

    if not audio_b64:
        return jsonify({"success": False, "error": "No audio payload provided"}), 400

    try:
        if "," in audio_b64:
            audio_b64 = audio_b64.split(",", 1)[1]
        audio_bytes = base64.b64decode(audio_b64)
        result = speech_processor.transcribe_audio_payload(
            audio_data=audio_bytes,
            language=language
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/ask", methods=["POST"])
def api_ask():
    """
    Main Voice / Text Ask Endpoint.
    Executes the full AI pipeline: Speech STT -> FAISS Semantic Match -> GPT Verification -> TTS.
    """
    t_start = time.time()
    data = request.get_json(silent=True) or {}

    raw_query = data.get("query", "").strip()
    domain_filter = data.get("domain") or None
    language = data.get("language", "en")
    gender = data.get("gender", "female")
    voice_id = data.get("voice_id", "en-US-JennyNeural")
    speed = float(data.get("speed", 1.0))
    answer_mode = data.get("answer_mode", "detailed")
    fallback_transcript = data.get("transcript", "")
    audio_b64 = data.get("audio", "")

    # If query was empty but audio was provided, transcribe it first
    if not raw_query and audio_b64:
        try:
            if "," in audio_b64:
                audio_b64 = audio_b64.split(",", 1)[1]
            audio_bytes = base64.b64decode(audio_b64)
            stt_res = speech_processor.transcribe_audio_payload(
                audio_data=audio_bytes,
                language=language
            )
            if stt_res.get("success") and stt_res.get("text"):
                raw_query = stt_res["text"].strip()
        except Exception as e:
            print(f"[api_ask] Audio decode error: {e}")

    # If query was empty but transcript was passed
    if not raw_query and fallback_transcript:
        raw_query = fallback_transcript.strip()

    if not raw_query:
        return jsonify({
            "success": False,
            "error": "Query or voice transcript cannot be empty"
        }), 400

    # 1. Speech processing step
    stt_res = speech_processor.transcribe_audio_payload(
        fallback_transcript=raw_query,
        language=language
    )

    # 2. FAQ Semantic & Keyword Pipeline with detailed/concise modes
    pipeline_res = engine.process_query_pipeline(
        query=raw_query,
        domain_filter=domain_filter,
        language=language,
        answer_mode=answer_mode
    )

    # 3. Text to Speech Synthesis (Ultra-Natural Studio Speech)
    tts_res = tts_processor.synthesize(
        text=pipeline_res["answer"],
        voice_id=voice_id,
        gender=gender,
        speed=speed,
        language=language
    )

    total_time_ms = round((time.time() - t_start) * 1000, 1)

    # Update Analytics in memory
    analytics_store["total_queries"] += 1
    analytics_store["total_latency_ms"] += total_time_ms
    if pipeline_res["confidence_score"] >= 40.0:
        analytics_store["successful_matches"] += 1

    dom = pipeline_res["detected_domain"]
    analytics_store["domain_counts"][dom] = analytics_store["domain_counts"].get(dom, 0) + 1
    analytics_store["language_counts"][language] = analytics_store["language_counts"].get(language, 0) + 1

    # Prepend to recent queries log (capped at 20)
    analytics_store["recent_queries"].insert(0, {
        "id": f"q_{int(time.time() * 1000)}",
        "query": raw_query,
        "domain": dom,
        "confidence": pipeline_res["confidence_score"],
        "latency_ms": total_time_ms,
        "timestamp": "Just now",
        "language": language
    })
    analytics_store["recent_queries"] = analytics_store["recent_queries"][:20]

    return jsonify({
        "success": True,
        "query": raw_query,
        "detected_domain": pipeline_res["detected_domain"],
        "detected_language": language,
        "answer": pipeline_res["answer"],
        "detailed_answer": pipeline_res["detailed_answer"],
        "concise_summary": pipeline_res["concise_summary"],
        "answer_mode": pipeline_res["answer_mode"],
        "is_auto_created": pipeline_res.get("is_auto_created", False),
        "confidence_score": pipeline_res["confidence_score"],
        "match_type": pipeline_res["match_type"],
        "best_match": pipeline_res["best_match"],
        "gpt_reasoning": pipeline_res["gpt_reasoning"],
        "candidates": pipeline_res["candidates"],
        "vector_preview": pipeline_res["vector_preview"],
        "vector_dimensions": pipeline_res["vector_dimensions"],
        "stt": stt_res,
        "tts": tts_res,
        "telemetry": {
            **pipeline_res["telemetry"],
            "tts_latency_ms": tts_res["latency_ms"],
            "server_total_latency_ms": total_time_ms
        }
    })


@app.route("/api/faqs", methods=["GET"])
def api_get_faqs():
    """Returns all FAQ items and domains, with optional domain filter."""
    domain = request.args.get("domain")
    search = request.args.get("search", "").strip().lower()

    filtered = engine.faqs
    if domain:
        filtered = [f for f in filtered if f.get("domain") == domain]
    if search:
        filtered = [
            f for f in filtered
            if search in f.get("question", "").lower() or search in f.get("answer", "").lower()
        ]

    return jsonify({
        "domains": engine.domains,
        "count": len(filtered),
        "faqs": filtered
    })


@app.route("/api/faqs", methods=["POST"])
def api_add_faq():
    """Adds a new FAQ item into knowledge base."""
    data = request.get_json(silent=True) or {}
    domain = data.get("domain", "general")
    question = data.get("question", "").strip()
    answer = data.get("answer", "").strip()
    keywords = data.get("keywords", [])
    language = data.get("language", "en")

    if not question or not answer:
        return jsonify({"success": False, "error": "Question and Answer are required"}), 400

    new_faq = engine.add_faq(
        domain=domain,
        question=question,
        answer=answer,
        keywords=keywords,
        language=language
    )

    return jsonify({"success": True, "faq": new_faq})


@app.route("/api/faqs/<faq_id>", methods=["DELETE"])
def api_delete_faq(faq_id):
    """Deletes an FAQ item."""
    success = engine.delete_faq(faq_id)
    if success:
        return jsonify({"success": True, "message": f"FAQ {faq_id} deleted"})
    return jsonify({"success": False, "error": "FAQ not found"}), 404


@app.route("/api/tts", methods=["POST"])
def api_tts():
    """Generates natural studio speech audio for given text."""
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"success": False, "error": "Text is required"}), 400

    gender = data.get("gender", "female")
    language = data.get("language", "en")
    voice_id = data.get("voice_id", "en-US-JennyNeural")
    speed = float(data.get("speed", 1.0))

    tts_res = tts_processor.synthesize(
        text=text,
        voice_id=voice_id,
        gender=gender,
        speed=speed,
        language=language
    )
    return jsonify(tts_res)


@app.route("/api/upload", methods=["POST"])
def api_upload_faq():
    """
    Ingests and parses document text or CSV/JSON content into new FAQ entries.
    Supports smart Q&A pair extraction.
    """
    data = request.get_json(silent=True) or {}
    text_content = data.get("content", "")
    file_format = data.get("format", "text")  # 'json', 'csv', 'text'
    target_domain = data.get("domain", "college_admissions")

    added_count = 0

    if file_format == "json":
        try:
            parsed = json.loads(text_content)
            if isinstance(parsed, list):
                for item in parsed:
                    if "question" in item and "answer" in item:
                        engine.add_faq(
                            domain=item.get("domain", target_domain),
                            question=item["question"],
                            answer=item["answer"],
                            keywords=item.get("keywords", [])
                        )
                        added_count += 1
            elif isinstance(parsed, dict):
                for q, a in parsed.items():
                    if isinstance(a, str):
                        engine.add_faq(
                            domain=target_domain,
                            question=q,
                            answer=a
                        )
                        added_count += 1
        except Exception as e:
            return jsonify({"success": False, "error": f"Invalid JSON format: {str(e)}"}), 400

    elif file_format == "csv":
        import csv
        import io
        try:
            reader = csv.reader(io.StringIO(text_content))
            for row in reader:
                if len(row) >= 2 and row[0].strip().lower() != "question":
                    engine.add_faq(
                        domain=target_domain,
                        question=row[0].strip(),
                        answer=row[1].strip()
                    )
                    added_count += 1
        except Exception as e:
            return jsonify({"success": False, "error": f"CSV parse error: {str(e)}"}), 400

    else:
        # Plain text with Q: / A: pattern
        lines = text_content.split("\n")
        curr_q = ""
        curr_a = ""
        for line in lines:
            line_str = line.strip()
            if line_str.lower().startswith("q:") or line_str.lower().startswith("question:"):
                if curr_q and curr_a:
                    engine.add_faq(domain=target_domain, question=curr_q, answer=curr_a)
                    added_count += 1
                curr_q = line_str.split(":", 1)[1].strip()
                curr_a = ""
            elif line_str.lower().startswith("a:") or line_str.lower().startswith("answer:"):
                curr_a = line_str.split(":", 1)[1].strip()
            elif curr_a:
                curr_a += " " + line_str

        if curr_q and curr_a:
            engine.add_faq(domain=target_domain, question=curr_q, answer=curr_a)
            added_count += 1

    return jsonify({
        "success": True,
        "added_count": added_count,
        "total_faqs": len(engine.faqs)
    })


@app.route("/api/analytics", methods=["GET"])
def api_analytics():
    """Returns analytics telemetry, accuracy metrics, and query logs."""
    total_q = max(analytics_store["total_queries"], 1)
    avg_latency = round(analytics_store["total_latency_ms"] / total_q, 1)
    accuracy_pct = round((analytics_store["successful_matches"] / total_q) * 100, 1)

    # Top FAQs by hit count
    sorted_faqs = sorted(engine.faqs, key=lambda x: x.get("hit_count", 0), reverse=True)
    top_faqs = [
        {
            "id": f["id"],
            "question": f["question"],
            "domain": f["domain"],
            "hit_count": f.get("hit_count", 0)
        }
        for f in sorted_faqs[:6]
    ]

    return jsonify({
        "total_queries": analytics_store["total_queries"],
        "avg_latency_ms": avg_latency,
        "accuracy_pct": accuracy_pct,
        "total_faqs": len(engine.faqs),
        "domain_counts": analytics_store["domain_counts"],
        "language_counts": analytics_store["language_counts"],
        "recent_queries": analytics_store["recent_queries"],
        "top_faqs": top_faqs
    })


@app.route("/api/voices", methods=["GET"])
def api_voices():
    """Returns available TTS voices."""
    return jsonify({
        "voices": tts_processor.get_voices()
    })


@app.route("/api/presets", methods=["GET"])
def api_presets():
    """Returns preset questions for quick one-click voice testing."""
    presets = [
        {
            "domain": "jee_mhtcet",
            "question": "What is the difference between JEE Main and JEE Advanced?",
            "language": "en"
        },
        {
            "domain": "jee_mhtcet",
            "question": "What percentile is required in JEE Main for top NIT Computer Science?",
            "language": "en"
        },
        {
            "domain": "nda",
            "question": "What is NDA and what are the primary eligibility criteria?",
            "language": "en"
        },
        {
            "domain": "nda",
            "question": "What happens during the 5-day SSB interview?",
            "language": "en"
        },
        {
            "domain": "college_admissions",
            "question": "How does JoSAA and CSAB counseling work for engineering colleges?",
            "language": "en"
        },
        {
            "domain": "tech_careers",
            "question": "How should I prepare for product company coding interviews in college?",
            "language": "en"
        },
        {
            "domain": "customer_support",
            "question": "How do I regenerate my production API key and what happens to active tokens?",
            "language": "en"
        },
        {
            "domain": "jee_mhtcet",
            "question": "जेईई मेन परीक्षा क्या है और इसकी तैयारी कैसे करें?",
            "language": "hi"
        },
        {
            "domain": "jee_mhtcet",
            "question": "एमएचटी-सीईटी द्वारे सीओईपी किंवा व्हीजेटीआय मध्ये प्रवेश कसा मिळवावा?",
            "language": "mr"
        }
    ]
    return jsonify({"presets": presets})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🎙️ AI Voice FAQ Bot server starting on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
