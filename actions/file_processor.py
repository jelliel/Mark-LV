"""
file_processor.py — JARVIS Universal File Processor

Supported types:
  image   → describe, ocr, resize, convert, compress, crop
  pdf     → summarize, extract_text, extract_pages, to_word
  docx    → summarize, extract_text, reformat, translate_hint
  txt/md  → summarize, reformat, translate_hint, word_count
  csv     → analyze, filter, sort, convert, stats
  xlsx    → analyze, filter, convert, stats
  json    → validate, format, extract, convert
  code    → explain, review, fix, run, document
  audio   → transcribe, trim, convert, info
  video   → trim, extract_audio, extract_frame, info, compress
  zip     → list, extract
  pptx    → summarize, extract_text, to_pdf
"""

import os
import re
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

# Model choice, timeout and fallback ladder all live in core/gemini.py.
from core import gemini

def _get_api_key() -> str:
    config_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


def _gemini_client(tier: str = gemini.SMART):
    """Summarising documents and reading images — the reasoning tier, with a
    long deadline because the input can be a whole file."""
    class _W:
        def generate_content(self, contents):
            resp = gemini.call(contents, tier=tier, timeout_ms=90000)
            if resp is None:
                raise RuntimeError("every Gemini model on the ladder failed")
            return resp

    return _W()


def _detect_type(path: Path) -> str:
    name = path.name.lower()
    # Handle common double extensions
    if name.endswith('.pdf.docx') or name.endswith('.docx.pdf'):
        return 'docx'   # treat as docx
    if name.endswith('.pdf.txt') or name.endswith('.txt.pdf'):
        return 'txt'
    ext = path.suffix.lower().lstrip(".")
    image_exts = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tiff", "svg", "ico"}
    video_exts = {"mp4", "avi", "mov", "mkv", "wmv", "flv", "webm", "m4v", "3gp"}
    audio_exts = {"mp3", "wav", "ogg", "m4a", "aac", "flac", "wma", "opus"}
    code_exts  = {"py", "js", "ts", "jsx", "tsx", "html", "css", "java", "c",
                  "cpp", "cs", "go", "rs", "rb", "php", "swift", "kt", "sh",
                  "bash", "ps1", "lua", "r", "m", "sql", "yaml", "toml"}
    archive_exts = {"zip", "rar", "tar", "gz", "7z", "bz2", "xz"}

    if ext in image_exts:  return "image"
    if ext in video_exts:  return "video"
    if ext in audio_exts:  return "audio"
    if ext in code_exts:   return "code"
    if ext in archive_exts: return "archive"
    if ext == "pdf":       return "pdf"
    if ext in ("docx", "doc"): return "docx"
    if ext in ("txt", "md", "rst", "log"): return "text"
    if ext in ("csv", "tsv"): return "csv"
    if ext in ("xlsx", "xls", "ods"): return "excel"
    if ext == "json":      return "json"
    if ext == "xml":       return "xml"
    if ext in ("pptx", "ppt"): return "pptx"
    return "unknown"


def _file_size_str(path: Path) -> str:
    size = path.stat().st_size
    if size < 1024:        return f"{size} B"
    if size < 1024**2:     return f"{size/1024:.1f} KB"
    if size < 1024**3:     return f"{size/1024**2:.1f} MB"
    return f"{size/1024**3:.1f} GB"

def _output_path(src: Path, suffix: str, new_ext: str = None) -> Path:
    ext  = new_ext or src.suffix
    name = f"{src.stem}_{suffix}{ext}"
    return src.parent / name

def _process_image(path: Path, action: str, params: dict, speak=None) -> str:
    try:
        from PIL import Image
    except ImportError:
        return "Pillow is not installed. Run: pip install Pillow"

    action = action or "describe"

    if action in ("describe", "ocr", "analyze", "read", "extract_text"):
        try:
            model  = _gemini_client()
            img    = Image.open(path)
            prompt = {
                "describe": "Describe this image in detail.",
                "ocr":      "Extract all text visible in this image. Return only the text, formatted clearly.",
                "analyze":  "Analyze this image thoroughly: objects, colors, composition, any text, context.",
                "read":     "Read all text in this image, preserving structure and formatting.",
                "extract_text": "Extract all text from this image.",
            }.get(action, "Describe this image.")

            if params.get("instruction"):
                prompt = params["instruction"]

            response = model.generate_content([prompt, img])
            result   = response.text.strip()

            if len(result) > 500 and params.get("save", True):
                out = _output_path(path, "result", ".txt")
                out.write_text(result, encoding="utf-8")
                return f"{result[:300]}...\n\nFull result saved to: {out}"
            return result
        except Exception as e:
            return f"AI image analysis failed: {e}"

    if action == "resize":
        width  = int(params.get("width",  0))
        height = int(params.get("height", 0))
        scale  = float(params.get("scale", 0))
        try:
            img = Image.open(path)
            w, h = img.size
            if scale:
                new_size = (int(w * scale), int(h * scale))
            elif width and height:
                new_size = (width, height)
            elif width:
                new_size = (width, int(h * width / w))
            elif height:
                new_size = (int(w * height / h), height)
            else:
                return "Please specify width, height, or scale."
            out = _output_path(path, f"resized_{new_size[0]}x{new_size[1]}")
            img.resize(new_size, Image.LANCZOS).save(out)
            return f"Resized from {w}x{h} to {new_size[0]}x{new_size[1]}. Saved: {out.name}"
        except Exception as e:
            return f"Resize failed: {e}"

    if action == "convert":
        fmt = params.get("format", "png").lower().strip(".")
        fmt_map = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG",
                   "webp": "WEBP", "bmp": "BMP", "tiff": "TIFF"}
        pil_fmt = fmt_map.get(fmt, fmt.upper())
        try:
            img = Image.open(path).convert("RGB") if fmt == "jpg" else Image.open(path)
            out = _output_path(path, "converted", f".{fmt}")
            img.save(out, pil_fmt)
            return f"Converted to {fmt.upper()}. Saved: {out.name}"
        except Exception as e:
            return f"Convert failed: {e}"

    if action == "compress":
        quality = int(params.get("quality", 70))
        try:
            img = Image.open(path).convert("RGB")
            out = _output_path(path, f"compressed_q{quality}", ".jpg")
            img.save(out, "JPEG", quality=quality, optimize=True)
            before = _file_size_str(path)
            after  = _file_size_str(out)
            return f"Compressed: {before} → {after}. Saved: {out.name}"
        except Exception as e:
            return f"Compress failed: {e}"

    if action == "info":
        try:
            img = Image.open(path)
            return (f"Image info: {img.format}, {img.size[0]}x{img.size[1]}px, "
                    f"mode: {img.mode}, size: {_file_size_str(path)}")
        except Exception as e:
            return f"Info failed: {e}"

    return _process_image(path, "describe", {"instruction": f"{action}: {params}"})

def _process_pdf(path: Path, action: str, params: dict, speak=None) -> str:
    action = action or "summarize"

    def _extract_pdf_text(max_chars=50000) -> str:
        text = ""
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    text += (page.extract_text() or "") + "\n"
        except ImportError:
            try:
                import PyPDF2
                with open(path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
            except ImportError:
                return ""
        return text[:max_chars]

    if action in ("summarize", "extract_text", "translate_hint", "analyze", "reformat"):
        text = _extract_pdf_text()
        if not text.strip():
            return "Could not extract text from PDF (may be scanned/image-based)."

        if action == "extract_text":
            out = _output_path(path, "text", ".txt")
            out.write_text(text, encoding="utf-8")
            return f"Text extracted ({len(text)} chars). Saved: {out.name}"

        prompt_map = {
            "summarize":      f"Summarize this PDF document concisely:\n\n{text}",
            "analyze":        f"Analyze this document thoroughly:\n\n{text}",
            "translate_hint": f"What language is this document in and what does it say? Summarize:\n\n{text}",
            "reformat":       f"Reformat this text cleanly with proper structure:\n\n{text}",
        }
        try:
            model    = _gemini_client()
            response = model.generate_content(prompt_map.get(action, f"Analyze:\n\n{text}"))
            result   = response.text.strip()
            if len(result) > 600 and params.get("save", True):
                out = _output_path(path, action, ".txt")
                out.write_text(result, encoding="utf-8")
                return f"{result[:400]}...\n\nFull result saved: {out.name}"
            return result
        except Exception as e:
            return f"AI analysis failed: {e}"

    if action == "info":
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                pages = len(pdf.pages)
            return f"PDF: {pages} pages, size: {_file_size_str(path)}"
        except Exception:
            return f"PDF size: {_file_size_str(path)}"

    if action == "to_word":
        text = _extract_pdf_text()
        if not text:
            return "Could not extract text to convert."
        try:
            from docx import Document
            doc  = Document()
            doc.add_heading(path.stem, 0)
            for para in text.split("\n\n"):
                if para.strip():
                    doc.add_paragraph(para.strip())
            out = _output_path(path, "converted", ".docx")
            doc.save(out)
            return f"Converted to Word document. Saved: {out.name}"
        except ImportError:
            return "python-docx not installed. Run: pip install python-docx"

    return f"Unknown PDF action: '{action}'. Try: summarize, extract_text, info, to_word"

def _process_text_doc(path: Path, file_type: str, action: str,
                       params: dict, speak=None) -> str:
    action = action or "summarize"

    def _read_content() -> str:
        if file_type == "docx":
            try:
                from docx import Document
                doc  = Document(path)
                return "\n".join(p.text for p in doc.paragraphs)
            except ImportError:
                return "python-docx not installed."
            except Exception as e:
                return f"Read failed: {e}"
        else:
            return path.read_text(encoding="utf-8", errors="ignore")

    content = _read_content()
    if not content.strip():
        return "File appears to be empty."

    if action == "word_count":
        words = len(content.split())
        chars = len(content)
        lines = content.count("\n")
        return f"Word count: {words} words, {chars} characters, {lines} lines."

    if action == "extract_text":
        if file_type != "txt":
            out = _output_path(path, "extracted", ".txt")
            out.write_text(content, encoding="utf-8")
            return f"Text extracted. Saved: {out.name}"
        return content[:2000]

    instruction = params.get("instruction", "")
    prompt_map  = {
        "summarize":  f"Summarize this document concisely:\n\n{content[:40000]}",
        "analyze":    f"Analyze this document:\n\n{content[:40000]}",
        "reformat":   f"Reformat this text with clean structure, proper headings and paragraphs:\n\n{content[:40000]}",
        "fix":        f"Fix grammar, spelling and style issues in this text:\n\n{content[:40000]}",
        "translate_hint": f"What language is this and what does it say? Summarize:\n\n{content[:10000]}",
        "to_bullet":  f"Convert this text into a clear bullet-point summary:\n\n{content[:40000]}",
        "custom":     f"{instruction}\n\n{content[:40000]}",
    }

    if action not in prompt_map:

        action  = "custom"
        instruction = action

    try:
        model    = _gemini_client()
        response = model.generate_content(prompt_map[action])
        result   = response.text.strip()
        if len(result) > 600 and params.get("save", True):
            out = _output_path(path, action, ".txt")
            out.write_text(result, encoding="utf-8")
            return f"{result[:400]}...\n\nFull result saved: {out.name}"
        return result
    except Exception as e:
        return f"AI processing failed: {e}"


def _process_data(path: Path, file_type: str, action: str,
                  params: dict, speak=None) -> str:
    try:
        import pandas as pd
    except ImportError:
        return "pandas not installed. Run: pip install pandas openpyxl"

    action = action or "analyze"

    try:
        if file_type == "csv":
            df = pd.read_csv(path, encoding="utf-8", errors="replace")
        else:
            df = pd.read_excel(path)
    except Exception as e:
        return f"Could not read file: {e}"

    if action == "info":
        return (f"Rows: {len(df)}, Columns: {len(df.columns)}\n"
                f"Columns: {', '.join(df.columns.tolist())}\n"
                f"Size: {_file_size_str(path)}")

    if action == "stats":
        try:
            desc = df.describe(include="all").to_string()
            return f"Statistics:\n{desc[:2000]}"
        except Exception as e:
            return f"Stats failed: {e}"

    if action == "analyze":
        preview = df.head(50).to_string()
        prompt  = (f"Analyze this dataset. Columns: {list(df.columns)}\n"
                   f"Rows: {len(df)}\nPreview:\n{preview}\n\n"
                   f"Give insights, patterns, and notable findings.")
        try:
            model    = _gemini_client()
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return f"AI analysis failed: {e}"

    if action in ("convert", "to_csv", "to_excel", "to_json"):
        fmt = {"to_csv": "csv", "to_excel": "xlsx", "to_json": "json",
               "convert": params.get("format", "csv")}.get(action, "csv")
        try:
            if fmt == "csv":
                out = _output_path(path, "converted", ".csv")
                df.to_csv(out, index=False, encoding="utf-8")
            elif fmt == "xlsx":
                out = _output_path(path, "converted", ".xlsx")
                df.to_excel(out, index=False)
            elif fmt == "json":
                out = _output_path(path, "converted", ".json")
                df.to_json(out, orient="records", force_ascii=False, indent=2)
            return f"Converted to {fmt.upper()}. Saved: {out.name}"
        except Exception as e:
            return f"Convert failed: {e}"

    if action == "filter":
        col       = params.get("column", "")
        value     = params.get("value", "")
        condition = params.get("condition", "equals")
        if not col or col not in df.columns:
            return f"Column '{col}' not found. Available: {', '.join(df.columns)}"
        try:
            if condition == "equals":     filtered = df[df[col] == value]
            elif condition == "contains": filtered = df[df[col].astype(str).str.contains(str(value), case=False)]
            elif condition == "gt":       filtered = df[df[col] > float(value)]
            elif condition == "lt":       filtered = df[df[col] < float(value)]
            else:                         filtered = df[df[col] == value]
            out = _output_path(path, "filtered", ".csv")
            filtered.to_csv(out, index=False)
            return f"Filtered: {len(filtered)} rows match. Saved: {out.name}"
        except Exception as e:
            return f"Filter failed: {e}"

    if action == "sort":
        col = params.get("column", df.columns[0])
        asc = params.get("ascending", True)
        try:
            sorted_df = df.sort_values(col, ascending=asc)
            out = _output_path(path, "sorted", path.suffix)
            sorted_df.to_csv(out, index=False)
            return f"Sorted by '{col}'. Saved: {out.name}"
        except Exception as e:
            return f"Sort failed: {e}"

    preview = df.head(30).to_string()
    try:
        model    = _gemini_client()
        response = model.generate_content(
            f"Task: {action}\nDataset ({len(df)} rows, cols: {list(df.columns)}):\n{preview}"
        )
        return response.text.strip()
    except Exception as e:
        return f"Processing failed: {e}"


def _process_json(path: Path, action: str, params: dict, speak=None) -> str:
    action = action or "analyze"
    try:
        content = path.read_text(encoding="utf-8")
        data    = json.loads(content)
    except Exception as e:
        return f"Invalid JSON: {e}"

    if action == "validate":
        return f"Valid JSON. Type: {type(data).__name__}, size: {_file_size_str(path)}"

    if action == "format":
        out = _output_path(path, "formatted", ".json")
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return f"Formatted JSON saved: {out.name}"

    if action in ("analyze", "summarize", "extract"):
        preview = json.dumps(data, indent=2, ensure_ascii=False)[:8000]
        prompt  = f"Task: {action} this JSON data:\n{preview}"
        if params.get("instruction"):
            prompt = f"{params['instruction']}\n\nJSON data:\n{preview}"
        try:
            model    = _gemini_client()
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return f"AI processing failed: {e}"

    if action == "to_csv":
        try:
            import pandas as pd
            if isinstance(data, list):
                df  = pd.DataFrame(data)
                out = _output_path(path, "converted", ".csv")
                df.to_csv(out, index=False)
                return f"Converted to CSV. Saved: {out.name}"
            return "JSON must be an array of objects to convert to CSV."
        except ImportError:
            return "pandas not installed."

    return _process_json(path, "analyze", {"instruction": action})

def _process_code(path: Path, action: str, params: dict, speak=None) -> str:
    action  = action or "explain"
    content = path.read_text(encoding="utf-8", errors="ignore")
    ext     = path.suffix.lstrip(".")

    if action == "run":
        if ext == "py":
            try:
                result = subprocess.run(
                    ["python", str(path)],
                    capture_output=True, text=True, timeout=30
                )
                out = result.stdout or result.stderr
                return f"Output:\n{out[:2000]}" if out else "No output."
            except subprocess.TimeoutExpired:
                return "Execution timed out (30s)."
            except Exception as e:
                return f"Run failed: {e}"
        return f"Direct execution not supported for .{ext} files."

    if action == "info":
        lines = content.count("\n")
        words = len(content.split())
        return f"Code file: {lines} lines, {words} words, {_file_size_str(path)}"

    prompt_map = {
        "explain":   f"Explain this {ext} code clearly:\n\n```{ext}\n{content[:30000]}\n```",
        "review":    f"Review this {ext} code for bugs, issues, and improvements:\n\n```{ext}\n{content[:30000]}\n```",
        "fix":       f"Fix any bugs in this {ext} code and return the corrected version:\n\n```{ext}\n{content[:30000]}\n```",
        "optimize":  f"Optimize this {ext} code for performance and readability:\n\n```{ext}\n{content[:30000]}\n```",
        "document":  f"Add proper documentation/comments to this {ext} code:\n\n```{ext}\n{content[:30000]}\n```",
        "summarize": f"Summarize what this {ext} code does:\n\n```{ext}\n{content[:30000]}\n```",
        "test":      f"Write unit tests for this {ext} code:\n\n```{ext}\n{content[:30000]}\n```",
    }

    instruction = params.get("instruction", "")
    if action not in prompt_map:
        prompt = f"{action}\n\n```{ext}\n{content[:30000]}\n```"
        if instruction:
            prompt = f"{instruction}\n\n```{ext}\n{content[:30000]}\n```"
    else:
        prompt = prompt_map[action]

    try:
        model    = _gemini_client()
        response = model.generate_content(prompt)
        result   = response.text.strip()

        if action in ("fix", "optimize", "document") and params.get("save", True):
            out = _output_path(path, action)
            code_match = re.search(r"```(?:\w+)?\n(.*?)```", result, re.DOTALL)
            code_to_save = code_match.group(1) if code_match else result
            out.write_text(code_to_save, encoding="utf-8")
            return f"{result[:400]}...\n\nSaved: {out.name}"
        return result
    except Exception as e:
        return f"AI processing failed: {e}"

def _process_audio(path: Path, action: str, params: dict, speak=None) -> str:
    action = action or "transcribe"

    if action == "info":
        try:
            from pydub import AudioSegment
            audio    = AudioSegment.from_file(path)
            duration = len(audio) / 1000
            mins, secs = divmod(int(duration), 60)
            return (f"Audio: {mins}m {secs}s, "
                    f"{audio.channels} ch, "
                    f"{audio.frame_rate}Hz, "
                    f"{_file_size_str(path)}")
        except ImportError:
            return f"Audio file: {_file_size_str(path)} (install pydub for more info)"
        except Exception as e:
            return f"Info failed: {e}"

    if action == "transcribe":
        try:
            model   = _gemini_client()
            content = path.read_bytes()
            mime    = {
                "mp3": "audio/mp3", "wav": "audio/wav",
                "ogg": "audio/ogg", "m4a": "audio/mp4",
                "aac": "audio/aac", "flac": "audio/flac",
            }.get(path.suffix.lstrip(".").lower(), "audio/mpeg")
            response = model.generate_content([
                "Transcribe all speech in this audio file accurately.",
                {"mime_type": mime, "data": content}
            ])
            result = response.text.strip()
            if params.get("save", True):
                out = _output_path(path, "transcript", ".txt")
                out.write_text(result, encoding="utf-8")
                return f"Transcription saved: {out.name}\n\nPreview: {result[:300]}"
            return result
        except Exception as e:
            return f"Transcription failed: {e}"

    if action == "convert":
        fmt = params.get("format", "mp3").lstrip(".")
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(path)
            out   = _output_path(path, "converted", f".{fmt}")
            audio.export(out, format=fmt)
            return f"Converted to {fmt.upper()}. Saved: {out.name}"
        except ImportError:
            return "pydub not installed. Run: pip install pydub"
        except Exception as e:
            return f"Convert failed: {e}"

    if action == "trim":
        start = float(params.get("start", 0))
        end   = float(params.get("end",   0))
        try:
            from pydub import AudioSegment
            audio   = AudioSegment.from_file(path)
            end_ms  = int(end * 1000)   if end   else len(audio)
            trimmed = audio[int(start * 1000):end_ms]
            out     = _output_path(path, f"trim_{int(start)}s_{int(end)}s")
            trimmed.export(out, format=path.suffix.lstrip("."))
            return f"Trimmed audio ({int(start)}s–{int(end)}s). Saved: {out.name}"
        except ImportError:
            return "pydub not installed."
        except Exception as e:
            return f"Trim failed: {e}"

    return f"Unknown audio action: '{action}'. Try: transcribe, info, convert, trim"

def _process_video(path: Path, action: str, params: dict, speak=None) -> str:
    action = action or "info"


    def _ffmpeg_available() -> bool:
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=3)
            return True
        except Exception:
            return False

    if action == "info":
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_format", "-show_streams", str(path)],
                capture_output=True, text=True, timeout=10
            )
            data     = json.loads(result.stdout)
            fmt      = data.get("format", {})
            duration = float(fmt.get("duration", 0))
            mins, secs = divmod(int(duration), 60)
            size     = _file_size_str(path)
            streams  = data.get("streams", [])
            video_s  = next((s for s in streams if s["codec_type"] == "video"), {})
            w        = video_s.get("width", "?")
            h        = video_s.get("height", "?")
            fps      = video_s.get("r_frame_rate", "?")
            return f"Video: {mins}m {secs}s, {w}x{h}, {fps} fps, {size}"
        except Exception:
            return f"Video file: {_file_size_str(path)}"

    if action == "extract_audio":
        if not _ffmpeg_available():
            return "ffmpeg not found. Install ffmpeg to extract audio."
        out = _output_path(path, "audio", ".mp3")
        try:
            subprocess.run(
                ["ffmpeg", "-i", str(path), "-q:a", "0", "-map", "a", str(out), "-y"],
                capture_output=True, timeout=300
            )
            return f"Audio extracted. Saved: {out.name}"
        except Exception as e:
            return f"Extract audio failed: {e}"

    if action == "trim":
        start = params.get("start", "00:00:00")
        end   = params.get("end",   "")
        if not _ffmpeg_available():
            return "ffmpeg not found."
        out = _output_path(path, f"trim", path.suffix)
        try:
            cmd = ["ffmpeg", "-i", str(path), "-ss", str(start)]
            if end:
                cmd += ["-to", str(end)]
            cmd += ["-c", "copy", str(out), "-y"]
            subprocess.run(cmd, capture_output=True, timeout=600)
            return f"Trimmed video saved: {out.name}"
        except Exception as e:
            return f"Trim failed: {e}"

    if action == "extract_frame":
        timestamp = params.get("timestamp", "00:00:01")
        if not _ffmpeg_available():
            return "ffmpeg not found."
        out = _output_path(path, f"frame_{timestamp.replace(':', '')}", ".jpg")
        try:
            subprocess.run(
                ["ffmpeg", "-i", str(path), "-ss", timestamp,
                 "-vframes", "1", str(out), "-y"],
                capture_output=True, timeout=30
            )
            return f"Frame extracted at {timestamp}. Saved: {out.name}"
        except Exception as e:
            return f"Extract frame failed: {e}"

    if action == "compress":
        crf = int(params.get("quality", 28))  
        if not _ffmpeg_available():
            return "ffmpeg not found."
        out = _output_path(path, f"compressed_crf{crf}", ".mp4")
        try:
            subprocess.run(
                ["ffmpeg", "-i", str(path),
                 "-c:v", "libx264", "-crf", str(crf),
                 "-preset", "medium", "-c:a", "copy",
                 str(out), "-y"],
                capture_output=True, timeout=1800
            )
            before = _file_size_str(path)
            after  = _file_size_str(out)
            return f"Compressed: {before} → {after}. Saved: {out.name}"
        except Exception as e:
            return f"Compress failed: {e}"

    if action == "transcribe":
        if not _ffmpeg_available():
            return "ffmpeg not found. Needed for video transcription."
        tmp_audio = Path(tempfile.mktemp(suffix=".mp3"))
        try:
            subprocess.run(
                ["ffmpeg", "-i", str(path), "-q:a", "0", "-map", "a",
                 str(tmp_audio), "-y"],
                capture_output=True, timeout=300
            )
            result = _process_audio(tmp_audio, "transcribe", params, speak)
            return result
        except Exception as e:
            return f"Video transcription failed: {e}"
        finally:
            if tmp_audio.exists():
                tmp_audio.unlink()

    if action == "convert":
        fmt = params.get("format", "mp4").lstrip(".")
        if not _ffmpeg_available():
            return "ffmpeg not found."
        out = _output_path(path, "converted", f".{fmt}")
        try:
            subprocess.run(
                ["ffmpeg", "-i", str(path), str(out), "-y"],
                capture_output=True, timeout=1800
            )
            return f"Converted to {fmt.upper()}. Saved: {out.name}"
        except Exception as e:
            return f"Convert failed: {e}"

    return f"Unknown video action: '{action}'. Try: info, trim, extract_audio, extract_frame, compress, transcribe, convert"

def _process_archive(path: Path, action: str, params: dict, speak=None) -> str:
    action = action or "list"

    if action == "list":
        try:
            import zipfile, tarfile
            ext = path.suffix.lower()
            if ext == ".zip":
                with zipfile.ZipFile(path) as z:
                    names = z.namelist()
            elif ext in (".tar", ".gz", ".bz2", ".xz"):
                with tarfile.open(path) as t:
                    names = t.getnames()
            else:
                return f"Unsupported archive format: {ext}"
            preview = "\n".join(names[:30])
            suffix  = f"\n... and {len(names)-30} more" if len(names) > 30 else ""
            return f"Archive contains {len(names)} files:\n{preview}{suffix}"
        except Exception as e:
            return f"List failed: {e}"

    if action == "extract":
        dest = Path(params.get("destination", str(path.parent / path.stem)))
        dest.mkdir(parents=True, exist_ok=True)
        try:
            shutil.unpack_archive(path, dest)
            return f"Extracted to: {dest}"
        except Exception as e:
            return f"Extract failed: {e}"

    return f"Unknown archive action: '{action}'. Try: list, extract"

def _process_pptx(path: Path, action: str, params: dict, speak=None) -> str:
    action = action or "summarize"

    def _read_pptx_text() -> str:
        try:
            from pptx import Presentation
            prs  = Presentation(path)
            text = []
            for i, slide in enumerate(prs.slides, 1):
                slide_text = f"\n--- Slide {i} ---\n"
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_text += shape.text.strip() + "\n"
                text.append(slide_text)
            return "\n".join(text)
        except ImportError:
            return "python-pptx not installed."

    if action in ("summarize", "extract_text", "analyze"):
        text = _read_pptx_text()
        if action == "extract_text":
            out = _output_path(path, "text", ".txt")
            out.write_text(text, encoding="utf-8")
            return f"Text extracted. Saved: {out.name}"
        try:
            model    = _gemini_client()
            prompt   = f"{'Summarize' if action == 'summarize' else 'Analyze'} this presentation:\n{text[:30000]}"
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return f"AI processing failed: {e}"

    return f"Unknown PPTX action: '{action}'. Try: summarize, extract_text, analyze"

# ── Multi-file ingestion ─────────────────────────────────────────────────────

# Hard ceiling on one ingestion run: a folder drop should not silently turn into
# an unbounded batch of AI calls.
_MAX_INGEST_FILES = 30


def _as_bool(value, default: bool = True) -> bool:
    """Gemini may hand a boolean as the string 'true'/'false'; read both."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in ("false", "0", "no", "non", "off", "")


def _split_paths(raw) -> list[str]:
    """One or many paths, given as a list or as newline/comma/semicolon text."""
    if isinstance(raw, (list, tuple)):
        parts = [str(item) for item in raw]
    else:
        parts = re.split(r"[\r\n;,]+", str(raw or ""))
    return [p.strip().strip('"').strip("'") for p in parts if p and p.strip()]


def _collect_paths(parameters: dict) -> tuple[list[Path], list[str]]:
    """Resolve every requested file. Returns (files, problems).

    Accepts several paths at once ('file_paths'/'files'), a single 'file_path'
    for backward compatibility, and a folder (every file inside, recursively).
    Multi-support is simply a consequence: each file is typed on its own.
    """
    items = _split_paths(parameters.get("file_paths") or parameters.get("files"))
    if not items:
        single = str(parameters.get("file_path") or "").strip().strip('"').strip("'")
        if single:
            items = [single]

    files: list[Path] = []
    problems: list[str] = []
    for item in items:
        path = Path(item).expanduser()
        if path.is_dir():
            found = [c for c in sorted(path.rglob("*"))
                     if c.is_file() and not c.name.startswith(".")]
            if not found:
                problems.append(f"dossier vide: {item}")
            for child in found[:_MAX_INGEST_FILES]:
                files.append(child)
            if len(found) > _MAX_INGEST_FILES:
                problems.append(f"{item}: seuls les {_MAX_INGEST_FILES} premiers fichiers sont pris")
        elif path.is_file():
            files.append(path)
        else:
            problems.append(f"introuvable: {item}")

    seen: set[str] = set()
    unique: list[Path] = []
    for path in files:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    if len(unique) > _MAX_INGEST_FILES:
        problems.append(f"seuls les {_MAX_INGEST_FILES} premiers fichiers sont pris")
        unique = unique[:_MAX_INGEST_FILES]
    return unique, problems


# ── Ingestion window: labels, language, progress ─────────────────────────────

_LANGUAGE_CODES = {
    "english": "en", "french": "fr", "francais": "fr", "français": "fr",
    "spanish": "es", "espanol": "es", "español": "es", "german": "de",
    "deutsch": "de", "italian": "it", "italiano": "it", "portuguese": "pt",
    "portugues": "pt", "português": "pt", "turkish": "tr", "turkce": "tr",
    "türkçe": "tr", "russian": "ru", "dutch": "nl", "polish": "pl",
    "arabic": "ar", "chinese": "zh", "japanese": "ja", "korean": "ko",
    "hindi": "hi",
}

_UI_STRINGS = {
    "en": {
        "title": "Mark-LIV — Ingestion",
        "ingested": "{n} file(s) ingested.",
        "what": "What should happen to them?",
        "more": "\n… and {n} more",
        "analyze": "Analyse",
        "learn": "Learning (theology agents)",
        "cancel": "Cancel",
        "processing": "Working…",
        "cancelled": "Ingestion cancelled.",
        "error": "Processing failed: {err}",
        "step_analyze": "{name} — analysing",
        "step_reading": "{name} — reading",
        "step_structuring": "{name} — structuring",
        "step_writing": "{name} — writing",
        "step_done": "{name} — done",
        "agents_heading": "Theology agents ready",
        "agents_hint": "Check the agents that should read and learn from these files:",
        "agents_all": "Check all",
        "agents_none": "Uncheck all",
        "agents_back": "Back",
        "agents_launch": "Start learning",
        "agents_none_found": "No agent profile found in:\n{path}",
        "agents_direct": "Learn without agents",
    },
    "fr": {
        "title": "Mark-LIV — Ingestion",
        "ingested": "{n} fichier(s) ingéré(s).",
        "what": "Que veux-tu en faire ?",
        "more": "\n… et {n} autre(s)",
        "analyze": "Analyse",
        "learn": "Apprentissage (agents théologie)",
        "cancel": "Annuler",
        "processing": "Traitement…",
        "cancelled": "Ingestion annulée.",
        "error": "Échec du traitement : {err}",
        "step_analyze": "{name} — analyse",
        "step_reading": "{name} — lecture",
        "step_structuring": "{name} — structuration",
        "step_writing": "{name} — écriture",
        "step_done": "{name} — terminé",
        "agents_heading": "Agents théologie prêts",
        "agents_hint": "Coche les agents qui doivent lire et apprendre ces fichiers :",
        "agents_all": "Tout cocher",
        "agents_none": "Tout décocher",
        "agents_back": "Retour",
        "agents_launch": "Lancer l'apprentissage",
        "agents_none_found": "Aucun profil d'agent trouvé dans :\n{path}",
        "agents_direct": "Apprendre sans agents",
    },
    "es": {
        "title": "Mark-LIV — Ingesta",
        "ingested": "{n} archivo(s) ingerido(s).",
        "what": "¿Qué quieres hacer con ellos?",
        "more": "\n… y {n} más",
        "analyze": "Análisis",
        "learn": "Aprendizaje (agentes de teología)",
        "cancel": "Cancelar",
        "processing": "Procesando…",
        "cancelled": "Ingesta cancelada.",
        "error": "Error de procesamiento: {err}",
        "step_analyze": "{name} — análisis",
        "step_reading": "{name} — lectura",
        "step_structuring": "{name} — estructuración",
        "step_writing": "{name} — escritura",
        "step_done": "{name} — hecho",
        "agents_heading": "Agentes de teología listos",
        "agents_hint": "Marca los agentes que deben leer y aprender de estos archivos:",
        "agents_all": "Marcar todo",
        "agents_none": "Desmarcar todo",
        "agents_back": "Volver",
        "agents_launch": "Iniciar aprendizaje",
        "agents_none_found": "No se encontró ningún agente en:\n{path}",
        "agents_direct": "Aprender sin agentes",
    },
    "de": {
        "title": "Mark-LIV — Import",
        "ingested": "{n} Datei(en) importiert.",
        "what": "Was soll damit geschehen?",
        "more": "\n… und {n} weitere",
        "analyze": "Analyse",
        "learn": "Lernen (Theologie-Agenten)",
        "cancel": "Abbrechen",
        "processing": "Verarbeitung…",
        "cancelled": "Import abgebrochen.",
        "error": "Verarbeitung fehlgeschlagen: {err}",
        "step_analyze": "{name} — Analyse",
        "step_reading": "{name} — Lesen",
        "step_structuring": "{name} — Strukturierung",
        "step_writing": "{name} — Schreiben",
        "step_done": "{name} — fertig",
        "agents_heading": "Theologie-Agenten bereit",
        "agents_hint": "Wähle die Agenten, die diese Dateien lesen und daraus lernen sollen:",
        "agents_all": "Alle auswählen",
        "agents_none": "Auswahl aufheben",
        "agents_back": "Zurück",
        "agents_launch": "Lernen starten",
        "agents_none_found": "Kein Agentenprofil gefunden in:\n{path}",
        "agents_direct": "Ohne Agenten lernen",
    },
    "it": {
        "title": "Mark-LIV — Importazione",
        "ingested": "{n} file acquisiti.",
        "what": "Cosa vuoi farne?",
        "more": "\n… e altri {n}",
        "analyze": "Analisi",
        "learn": "Apprendimento (agenti teologia)",
        "cancel": "Annulla",
        "processing": "Elaborazione…",
        "cancelled": "Acquisizione annullata.",
        "error": "Elaborazione non riuscita: {err}",
        "step_analyze": "{name} — analisi",
        "step_reading": "{name} — lettura",
        "step_structuring": "{name} — strutturazione",
        "step_writing": "{name} — scrittura",
        "step_done": "{name} — fatto",
        "agents_heading": "Agenti di teologia pronti",
        "agents_hint": "Seleziona gli agenti che devono leggere e imparare da questi file:",
        "agents_all": "Seleziona tutto",
        "agents_none": "Deseleziona tutto",
        "agents_back": "Indietro",
        "agents_launch": "Avvia l'apprendimento",
        "agents_none_found": "Nessun profilo agente trovato in:\n{path}",
        "agents_direct": "Impara senza agenti",
    },
    "pt": {
        "title": "Mark-LIV — Ingestão",
        "ingested": "{n} arquivo(s) ingerido(s).",
        "what": "O que queres fazer com eles?",
        "more": "\n… e mais {n}",
        "analyze": "Análise",
        "learn": "Aprendizagem (agentes de teologia)",
        "cancel": "Cancelar",
        "processing": "Processando…",
        "cancelled": "Ingestão cancelada.",
        "error": "Falha no processamento: {err}",
        "step_analyze": "{name} — análise",
        "step_reading": "{name} — leitura",
        "step_structuring": "{name} — estruturação",
        "step_writing": "{name} — scrittura",
        "step_done": "{name} — fatto",
        "agents_heading": "Agentes de teologia prontos",
        "agents_hint": "Marque os agentes que devem ler e aprender com estes arquivos:",
        "agents_all": "Marcar todos",
        "agents_none": "Desmarcar todos",
        "agents_back": "Voltar",
        "agents_launch": "Iniciar aprendizado",
        "agents_none_found": "Nenhum perfil de agente encontrado em:\n{path}",
        "agents_direct": "Aprender sem agentes",
    },
    "tr": {
        "title": "Mark-LIV — İçe Aktarma",
        "ingested": "{n} dosya alındı.",
        "what": "Ne yapmak istersin?",
        "more": "\n… ve {n} tane daha",
        "analyze": "Analiz",
        "learn": "Öğrenme (teoloji ajanları)",
        "cancel": "İptal",
        "processing": "İşleniyor…",
        "cancelled": "İçe aktarma iptal edildi.",
        "error": "İşleme başarısız: {err}",
        "step_analyze": "{name} — analiz",
        "step_reading": "{name} — okuma",
        "step_structuring": "{name} — yapılandırma",
        "step_writing": "{name} — yazma",
        "step_done": "{name} — tamam",
    },
}


def _user_language() -> str:
    """Best effort: the language the person uses — memory first, then the OS."""
    try:
        memory = Path(__file__).resolve().parent.parent / "memory" / "long_term.json"
        data = json.loads(memory.read_text(encoding="utf-8"))
        for section in ("identity", "preferences"):
            entry = (data.get(section) or {}).get("language") or {}
            name = str(entry.get("value") or "").strip().lower()
            if name in _LANGUAGE_CODES:
                return _LANGUAGE_CODES[name]
    except Exception:
        pass
    try:
        import locale
        code = (locale.getlocale()[0] or os.environ.get("LANG", "") or "")[:2].lower()
        if code:
            return code
    except Exception:
        pass
    return "en"


def _ui_strings() -> dict:
    """Labels for the ingestion window, in the user's language (English falls back)."""
    strings = dict(_UI_STRINGS["en"])
    strings.update(_UI_STRINGS.get(_user_language(), {}))
    return strings


def _run_ingest(paths, mode, action, params, speak, player, report=None,
                learn_profiles=None):
    """Do the ingesting work, reporting progress as report(done, total, label).

    mode='learn' with `learn_profiles` (AgentProfile list, possibly empty) runs
    once per agent through theology_agents; with None it is the generic
    single-pass structuring. `learn_profiles=[]` means the picker was offered
    and the user chose none (direct learning)."""
    labels = _ui_strings()
    total = len(paths)

    def step(done, label):
        """Generic progress sink: callers pass (done, label)."""
        print(f"[FileProcessor] {done}/{total} {label}")
        if report:
            try:
                report(done, total, label)
            except Exception:
                pass

    if mode == "learn" and learn_profiles is not None:
        agents = _load_theology_agents()
        if agents is None:
            return ("Module theology_agents introuvable — "
                    "apprentissage par agents impossible.")

        def agent_step(done, total_units, label):
            """The agents pipeline's own sink — its contract is
            (done, total, label), unlike the generic one above."""
            print(f"[FileProcessor] {done}/{total_units} {label}")
            if report:
                try:
                    report(done, total_units, label)
                except Exception:
                    pass

        return agents.learn_with_agents(paths, learn_profiles,
                                        player=player, step=agent_step)

    if mode == "learn":
        return _theology_learn(paths, params, player, step,
                               profiles=learn_profiles)

    results = []
    for index, path in enumerate(paths):
        step(index, labels["step_analyze"].format(name=path.name))
        results.append(_process_one(path, action, params, speak, player))
        step(index + 1, labels["step_done"].format(name=path.name))
    if total == 1:
        return results[0]
    return "\n\n".join(f"— {p.name} —\n{r}" for p, r in zip(paths, results))


def _ingest_log(line: str) -> None:
    """One line per ingestion run, under <install>/logs/file_processor.log.

    The window is the only part of this tool the user can see, so when it does
    not appear this file is the only record of whether the tool ran at all and
    which branch it went down. Counts only — never file names or paths.
    """
    try:
        root = Path(__file__).resolve().parent
        if root.name == "actions":
            root = root.parent
        logs = root / "logs"
        logs.mkdir(exist_ok=True)
        with open(logs / "file_processor.log", "a", encoding="utf-8") as handle:
            handle.write(f"{datetime.now().isoformat(timespec='seconds')} {line}\n")
    except Exception as e:
        print(f"[FileProcessor] could not write the ingestion log: {e}")


def _ingestion_window(paths, action, params, speak, player, preselect=None):
    """Ask what to do with the ingested files, then show progress while it runs.

    Qt first: the packaged app ships PyQt6 and no tkinter at all, so a window
    built on tkinter could never open inside it — which, seen from the user's
    side, is the same thing as no window. `_tk_ingestion_window` stays as the
    fallback for a source checkout that has tkinter but no Qt.

    Returns the result text, the localised 'cancelled' message when the person
    backs out, or None when neither toolkit can show a window — the caller then
    processes directly rather than failing.
    """
    result = _qt_ingestion_window(paths, action, params, speak, player, preselect)
    if result is not None:
        return result
    result = _tk_ingestion_window(paths, action, params, speak, player, preselect)
    if result is None:
        _ingest_log("window: neither Qt nor tkinter could draw it — processing directly")
    return result


def _qt_ingestion_window(paths, action, params, speak, player, preselect=None):
    """The ingestion window, drawn with the toolkit the app itself is built on.

    Nothing here may assume it runs on the GUI thread: a tool can be invoked
    from a worker, and a widget built outside the GUI thread is a widget nobody
    ever sees. So the window is always built *in* the GUI thread — inline when
    that is where we already are, and queued to it when we are not.
    """
    try:
        import queue
        import threading
        from PyQt6.QtCore import QMetaObject, QObject, QThread, QTimer, Qt, pyqtSlot
        from PyQt6.QtWidgets import (QApplication, QCheckBox, QDialog, QHBoxLayout,
                                     QLabel, QPlainTextEdit, QProgressBar,
                                     QPushButton, QScrollArea, QStackedWidget,
                                     QVBoxLayout, QWidget)
    except Exception as e:
        print(f"[FileProcessor] Qt window unavailable: {e}")
        return None

    app = QApplication.instance()
    if app is None:                     # no window to draw in: let the caller decide
        print("[FileProcessor] no Qt application running for the ingestion window")
        _ingest_log("window: no Qt application running")
        return None

    labels = _ui_strings()
    count = len(paths)
    state = {"result": None, "cancelled": False, "running": False}
    results: "queue.Queue" = queue.Queue()
    finished = threading.Event()        # the window is closed
    opened = threading.Event()          # the GUI thread has built it
    keep_alive = []                     # wrappers crossing the thread boundary
    _agents_module = _load_theology_agents()   # agents folder → picker
    _agents_profiles = _agents_module.discover_agents() if _agents_module else []

    def report(done, total, label):
        results.put(("progress", done, total, label))

    class IngestWindow(QDialog):
        """The question, then progress while the work runs in the background."""

        def __init__(self):
            super().__init__()
            self.setWindowTitle(labels["title"])
            self.setModal(True)
            self.setMinimumWidth(470)
            try:
                self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            except Exception:
                pass
            outer = QVBoxLayout(self)
            self.pages = QStackedWidget(self)
            outer.addWidget(self.pages)
            self.pages.addWidget(self._choice_page())
            self.pages.addWidget(self._progress_page())
            self.pages.addWidget(self._agents_page())
            self._profiles     = _agents_profiles
            self._agents_built = False
            if preselect == "analyze":
                self.analyze_button.setDefault(True)
                self.analyze_button.setFocus()
            elif preselect == "learn":
                self.learn_button.setDefault(True)
                self.learn_button.setFocus()

        def _choice_page(self):
            page = QWidget()
            box = QVBoxLayout(page)
            heading = QLabel(labels["ingested"].format(n=count))
            heading.setStyleSheet("font-size: 14px; font-weight: bold;")
            box.addWidget(heading)
            box.addWidget(QLabel(labels["what"]))
            listing = "\n".join(f"\u2022 {p.name}" for p in paths[:6])
            if count > 6:
                listing += labels["more"].format(n=count - 6)
            files = QLabel(listing)
            files.setStyleSheet("color: #666666;")
            box.addWidget(files)
            box.addSpacing(8)
            row = QHBoxLayout()
            self.analyze_button = QPushButton(labels["analyze"])
            self.learn_button = QPushButton(labels["learn"])
            self.analyze_button.clicked.connect(lambda: self.start("analyze"))
            # Learning goes through the agent picker first: the user decides
            # WHICH agents read the files, not just that learning happens.
            self.learn_button.clicked.connect(lambda: self.show_agents())
            row.addWidget(self.analyze_button)
            row.addWidget(self.learn_button)
            row.addStretch(1)
            box.addLayout(row)
            below = QHBoxLayout()
            below.addStretch(1)
            cancel_button = QPushButton(labels["cancel"])
            cancel_button.clicked.connect(self.reject)
            below.addWidget(cancel_button)
            box.addLayout(below)
            box.addStretch(1)
            return page

        def _agents_page(self):
            """The agent picker: one checkbox per Desktop/Agents profile."""
            page = QWidget()
            box = QVBoxLayout(page)
            self._agents_heading = QLabel("")
            self._agents_heading.setStyleSheet("font-size: 14px; font-weight: bold;")
            self._agents_heading.setWordWrap(True)
            box.addWidget(self._agents_heading)
            box.addWidget(QLabel(labels["agents_hint"]))
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            container = QWidget()
            self._agents_layout = QVBoxLayout(container)
            scroll.setWidget(container)
            box.addWidget(scroll, 1)
            row = QHBoxLayout()
            for text, checked in ((labels["agents_all"], True),
                                  (labels["agents_none"], False)):
                button = QPushButton(text)
                button.clicked.connect(lambda _, c=checked: self._set_agents(c))
                row.addWidget(button)
            row.addStretch(1)
            box.addLayout(row)
            row2 = QHBoxLayout()
            back = QPushButton(labels["agents_back"])
            back.clicked.connect(lambda: self.pages.setCurrentIndex(0))
            self.launch_button = QPushButton(labels["agents_launch"])
            self.launch_button.clicked.connect(self._launch_learning)
            row2.addWidget(back)
            row2.addStretch(1)
            row2.addWidget(self.launch_button)
            box.addLayout(row2)
            return page

        def show_agents(self):
            """Fill the picker with the current profiles and show it.

            Re-discovered every time the picker is shown, so agents added to
            the folder mid-session appear the next time it opens.
            """
            self._profiles = (_agents_module.discover_agents()
                              if _agents_module else [])
            while self._agents_layout.count():
                item = self._agents_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
            self._agents_checks = []
            if self._profiles:
                self._agents_heading.setText(labels["agents_heading"])
                for profile in self._profiles:
                    brief = " ".join((profile.description or "").split())[:80]
                    box = QCheckBox(f"{profile.name}  —  {brief}…")
                    box.setChecked(True)
                    self._agents_layout.addWidget(box)
                    self._agents_checks.append(box)
                self.launch_button.setText(labels["agents_launch"])
            else:
                folder = (_agents_module.get_agents_dir()
                          if _agents_module else "?")
                self._agents_heading.setText(
                    labels["agents_none_found"].format(path=folder))
                self.launch_button.setText(labels["agents_direct"])
            self._agents_layout.addStretch(1)
            self.pages.setCurrentIndex(2)
            self.adjustSize()
            self.launch_button.setDefault(True)
            self.launch_button.setFocus()

        def _set_agents(self, checked: bool):
            for box in self._agents_checks:
                box.setChecked(checked)

        def _launch_learning(self):
            # Nothing checked: the generic single pass — learning, no agents.
            checked = [p for p, cb in
                       zip(self._profiles, self._agents_checks)
                       if cb.isChecked()]
            self.start("learn", checked)

        def _progress_page(self):
            page = QWidget()
            box = QVBoxLayout(page)
            self.bar = QProgressBar()
            self.bar.setRange(0, max(count, 1))
            self.bar.setValue(0)
            box.addWidget(self.bar)
            self.status = QLabel(labels["processing"])
            self.status.setStyleSheet("font-weight: bold;")
            box.addWidget(self.status)
            self.log = QPlainTextEdit()
            self.log.setReadOnly(True)
            self.log.setMinimumHeight(150)
            box.addWidget(self.log)
            return page

        def start(self, mode, profiles=None):
            """Swap the question for the progress view and run the work."""
            if state["running"]:
                return            # double-clic / re-entry: one run at a time
            state["running"] = True
            self.pages.setCurrentIndex(1)
            self.adjustSize()

            def work():
                try:
                    text = _run_ingest(paths, mode, action, params, speak,
                                       player, report,
                                       learn_profiles=profiles if mode == "learn"
                                       else None)
                except Exception as e:
                    text = labels["error"].format(err=e)
                results.put(("done", text))

            threading.Thread(target=work, daemon=True).start()
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.poll)
            self.timer.start(80)

        def poll(self):
            while True:
                try:
                    message = results.get_nowait()
                except queue.Empty:
                    break
                if message[0] == "progress":
                    _, done, total, label = message
                    self.bar.setRange(0, max(total, 1))
                    self.bar.setValue(done)
                    if label:
                        self.log.appendPlainText(label)
                else:
                    state["result"] = message[1]
                    self.timer.stop()
                    finished.set()
                    self.accept()
                    return

        def reject(self):
            state["cancelled"] = True
            finished.set()
            super().reject()

        def closeEvent(self, event):
            # Closing mid-run would throw the work away, so it waits — the same
            # rule the tkinter window follows.
            if state["running"]:
                event.ignore()
                return
            state["cancelled"] = True
            finished.set()
            event.accept()

    def show_window():
        window = IngestWindow()
        window.raise_()
        window.activateWindow()
        _ingest_log(f"window: shown with Qt (preselect={preselect})")
        opened.set()
        window.exec()

    try:
        if QThread.currentThread() == app.thread():
            show_window()                      # already on the GUI thread
        else:
            # A widget may only be built in the GUI thread, and PyQt6 has no
            # QTimer.singleShot(context, functor) to post the call with: it goes
            # through a QObject that lives in the GUI thread instead.
            class _OnGuiThread(QObject):
                @pyqtSlot()
                def run(self):
                    show_window()

            caller = _OnGuiThread()
            keep_alive.append(caller)          # the wrapper must outlive the call
            caller.moveToThread(app.thread())
            QMetaObject.invokeMethod(caller, "run", Qt.ConnectionType.QueuedConnection)
            if not opened.wait(10):
                print("[FileProcessor] the Qt thread never picked the window up")
                return None
            finished.wait()
    except Exception as e:
        print(f"[FileProcessor] Qt window failed: {e}")
        _ingest_log(f"window: Qt failed — {e}")
        return None

    if state["cancelled"]:
        _ingest_log("window: cancelled by the user")
        return labels["cancelled"]
    _ingest_log("window: choice made, work finished")
    return state["result"]


def _tk_ingestion_window(paths, action, params, speak, player, preselect=None):
    """Pick Analyse or Learning, then show progress while the work runs.

    The fallback for a checkout with tkinter and no Qt — same approach as
    actions/youtube_video.py.
    """
    try:
        import queue
        import threading
        import tkinter as tk
        from tkinter import ttk
    except Exception as e:
        print(f"[FileProcessor] ingestion window unavailable: {e}")
        _ingest_log(f"window: tkinter unavailable — {e}")
        return None

    labels = _ui_strings()
    state = {"result": None, "cancelled": False}

    try:
        root = tk._default_root
        owns_root = root is None
        win = tk.Tk() if owns_root else tk.Toplevel(root)
        win.title(labels["title"])
        win.resizable(False, False)
        try:
            win.attributes("-topmost", True)
        except Exception:
            pass

        container = ttk.Frame(win, padding=18)
        container.pack(fill="both", expand=True)

        result_queue: "queue.Queue" = queue.Queue()
        progress_view = ttk.Frame(container)

        # --- the question -------------------------------------------------
        choice_view = ttk.Frame(container)
        choice_view.pack(fill="both", expand=True)
        count = len(paths)
        ttk.Label(choice_view, text=labels["ingested"].format(n=count),
                  font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(choice_view, text=labels["what"]).pack(anchor="w", pady=(2, 10))
        listing = "\n".join(f"• {p.name}" for p in paths[:6])
        if count > 6:
            listing += labels["more"].format(n=count - 6)
        ttk.Label(choice_view, text=listing, justify="left",
                  foreground="#666666").pack(anchor="w", pady=(0, 14))
        buttons = ttk.Frame(choice_view)
        buttons.pack(fill="x")
        analyze_button = ttk.Button(buttons, text=labels["analyze"], width=16,
                                    command=lambda: start("analyze"))
        analyze_button.pack(side="left")
        learn_button = ttk.Button(buttons, text=labels["learn"], width=34,
                                  command=lambda: show_agents_tk())
        learn_button.pack(side="left", padx=(8, 0))
        if preselect == "analyze":
            analyze_button.focus_set()
        elif preselect == "learn":
            learn_button.focus_set()

        def cancel():
            state["cancelled"] = True
            win.destroy()

        ttk.Button(choice_view, text=labels["cancel"],
                   command=cancel).pack(anchor="e", pady=(12, 0))

        # --- the progress view --------------------------------------------
        def start(mode, profiles=None):
            choice_view.pack_forget()
            progress_view.pack(fill="both", expand=True)
            win.protocol("WM_DELETE_WINDOW", lambda: None)  # let the work finish

            bar = ttk.Progressbar(progress_view, mode="determinate",
                                  maximum=max(count, 1), length=380)
            bar.pack(fill="x", pady=(0, 8))
            status = ttk.Label(progress_view, text=labels["processing"],
                               font=("Segoe UI", 10, "bold"))
            status.pack(anchor="w", pady=(0, 6))
            logbox = tk.Text(progress_view, height=9, width=56, wrap="word",
                             state="disabled", relief="solid", borderwidth=1)
            logbox.pack(fill="both", expand=True)

            def append_log(text):
                logbox.configure(state="normal")
                logbox.insert("end", text + "\n")
                logbox.see("end")
                logbox.configure(state="disabled")

            def report(done, total, label):
                result_queue.put(("progress", done, total, label))

            def work():
                try:
                    text = _run_ingest(paths, mode, action, params, speak,
                                       player, report,
                                       learn_profiles=profiles if mode == "learn"
                                       else None)
                except Exception as e:
                    text = labels["error"].format(err=e)
                result_queue.put(("done", text))

            threading.Thread(target=work, daemon=True).start()

            def poll():
                try:
                    while True:
                        msg = result_queue.get_nowait()
                        if msg[0] == "progress":
                            _, done, total, label = msg
                            bar.configure(maximum=max(total, 1), value=done)
                            if label:
                                append_log(label)
                        else:
                            state["result"] = msg[1]
                            win.destroy()
                            return
                except queue.Empty:
                    pass
                if win.winfo_exists():
                    win.after(80, poll)

            win.after(80, poll)

        # --- the agent picker (Learning) -----------------------------------
        agents_mod = _load_theology_agents()

        def show_agents_tk():
            profiles = agents_mod.discover_agents() if agents_mod else []
            picker = tk.Toplevel(win)
            picker.title(labels["agents_heading"])
            picker.resizable(True, True)
            try:
                picker.attributes("-topmost", True)
            except Exception:
                pass
            ttk.Label(picker, text=labels["agents_hint"],
                      wraplength=420).pack(anchor="w", padx=10, pady=(10, 6))
            if profiles:
                canvas = tk.Canvas(picker, width=460, height=280, highlightthickness=0)
                vsb = ttk.Scrollbar(picker, orient="vertical", command=canvas.yview)
                canvas.configure(yscrollcommand=vsb.set)
                canvas.pack(side="left", fill="both", expand=True, padx=(10, 0))
                vsb.pack(side="left", fill="y")
                rows = ttk.Frame(canvas)
                canvas.create_window((0, 0), window=rows, anchor="nw")
                selections = []
                for profile in profiles:
                    brief = " ".join((profile.description or "").split())[:70]
                    var = tk.BooleanVar(value=True)
                    tk.Checkbutton(rows, text=f"{profile.name} — {brief}…",
                                   variable=var, anchor="w", wraplength=420,
                                   justify="left").pack(fill="x")
                    selections.append((profile, var))
                rows.update_idletasks()
                canvas.configure(scrollregion=canvas.bbox("all"))
                canvas.bind("<MouseWheel>", lambda event: canvas.yview_scroll(
                    -1 * int(event.delta / 120), "units"))
                bottom = ttk.Frame(picker)
                bottom.pack(fill="x", padx=10, pady=(0, 10))
                def set_all(c):
                    for _profile, var in selections:
                        var.set(c)
                ttk.Button(bottom, text=labels["agents_all"],
                           command=lambda: set_all(True)).pack(side="left")
                ttk.Button(bottom, text=labels["agents_none"],
                           command=lambda: set_all(False)).pack(side="left", padx=(6, 0))
                ttk.Button(bottom, text=labels["agents_back"],
                           command=picker.destroy).pack(side="right")
                def launch():
                    checked = [p for p, var in selections if var.get()]
                    picker.grab_release()
                    picker.destroy()
                    start("learn", checked)
                ttk.Button(bottom, text=labels["agents_launch"],
                           command=launch).pack(side="right", padx=(6, 0))
            else:
                folder = agents_mod.get_agents_dir() if agents_mod else "?"
                ttk.Label(picker, text=labels["agents_none_found"].format(path=folder),
                          foreground="#a03030", wraplength=420).pack(
                    anchor="w", padx=10, pady=8)
                def direct():
                    picker.grab_release()
                    picker.destroy()
                    start("learn", None)     # no selection → generic pass
                ttk.Button(picker, text=labels["agents_direct"],
                           command=direct).pack(pady=(0, 10))
            picker.grab_set()   # modal, like the parent window

        win.protocol("WM_DELETE_WINDOW", cancel)
        win.grab_set()
        win.update_idletasks()
        width, height = win.winfo_width(), win.winfo_height()
        x = (win.winfo_screenwidth() - width) // 2
        y = (win.winfo_screenheight() - height) // 3
        win.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        win.focus_force()
        _ingest_log(f"window: shown with tkinter (preselect={preselect})")

        if owns_root:
            win.mainloop()   # ends when the window is destroyed
        else:
            win.wait_window()

        if state["cancelled"]:
            return labels["cancelled"]
        return state["result"]
    except Exception as e:
        print(f"[FileProcessor] ingestion window failed: {e}")
        return None


def _load_theology_agents():
    """Load actions/theology_agents.py by path (actions/ is not a package)."""
    try:
        import importlib.util
        path = Path(__file__).resolve().with_name("theology_agents.py")
        if not path.is_file():
            return None
        spec = importlib.util.spec_from_file_location("markliv_theology_agents", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"[FileProcessor] could not load theology_agents: {e}")
        return None


def _theology_brain_module():
    """Load actions/theology_brain.py by path (actions/ is not a package)."""
    try:
        import importlib.util
        path = Path(__file__).resolve().with_name("theology_brain.py")
        if not path.is_file():
            return None
        spec = importlib.util.spec_from_file_location("markliv_theology_brain", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"[FileProcessor] could not load theology_brain: {e}")
        return None


_MAX_LEARN_CHARS = 24000      # text handed to the structuring model
_MAX_ENTITIES = 6             # pages written per kind, per source
_MAX_CONCEPTS = 6

_STRUCTURE_PROMPT = """{team}Read the source below and structure it into wiki pages for a personal theological vault.

Return ONLY a JSON object — no prose and no code fence — with exactly this shape:
{{
  "source": {{"title": "...", "tags": "comma,separated",
             "body": "Markdown page for the source itself"}},
  "entities": [{{"title": "...", "tags": "comma,separated",
               "body": "Markdown page"}}],
  "concepts": [{{"title": "...", "tags": "comma,separated",
               "body": "Markdown page"}}]
}}

Rules:
- "source": the page for this document — a 2-3 sentence summary, its main points, and any notable quotes.
- 2 to {entities} "entities" (people, councils, orders, works, places) and 2 to {concepts} "concepts" (doctrines, terms, movements) that actually appear.
- Write in the language of the source text.
- Every body starts with a one-line summary, then the details.
- Cross-link pages with [[Title]] using the exact titles you output.
- Never invent a scripture, council, date, author or quote. If the source does not state it, leave it out.
- Titles are short, unique and usable as file names.

{ctx}Source file: {name}
--- SOURCE TEXT ---
{text}
"""


def _extract_source_text(path: Path) -> str:
    """Plain text of an ingested file, whatever its format."""
    file_type = _detect_type(path)
    try:
        if file_type in ("text", "code", "json", "xml"):
            return path.read_text(encoding="utf-8", errors="ignore")[:_MAX_LEARN_CHARS]
        if file_type == "docx":
            from docx import Document
            return "\n".join(p.text for p in Document(path).paragraphs)[:_MAX_LEARN_CHARS]
        if file_type == "pdf":
            text = ""
            try:
                import pdfplumber
                with pdfplumber.open(path) as pdf:
                    for page in pdf.pages:
                        text += (page.extract_text() or "") + "\n"
            except ImportError:
                import PyPDF2
                with open(path, "rb") as fh:
                    for page in PyPDF2.PdfReader(fh).pages:
                        text += (page.extract_text() or "") + "\n"
            return text[:_MAX_LEARN_CHARS]
        if file_type in ("csv", "excel"):
            import pandas as pd
            frame = pd.read_csv(path) if file_type == "csv" else pd.read_excel(path)
            return frame.head(100).to_string()[:_MAX_LEARN_CHARS]
        if file_type == "pptx":
            from pptx import Presentation
            parts = []
            for index, slide in enumerate(Presentation(path).slides, 1):
                parts.append(f"\n--- Slide {index} ---")
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        parts.append(shape.text.strip())
            return "\n".join(parts)[:_MAX_LEARN_CHARS]
    except Exception as e:
        print(f"[FileProcessor] text extraction failed for {path.name}: {e}")
        return ""

    # image / audio / video / unknown — the model reads the file itself
    try:
        if file_type == "image":
            return _process_image(path, "describe", {"save": False}, None)
        if file_type == "audio":
            return _process_audio(path, "transcribe", {"save": False}, None)
        if file_type == "video":
            return _process_video(path, "transcribe", {"save": False}, None)
    except Exception as e:
        print(f"[FileProcessor] AI read failed for {path.name}: {e}")
    return ""


def _parse_json_object(raw: str):
    """Pull the JSON object out of a model answer, fences and prose included."""
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return None
    return None


def _theology_structure(text: str, source_name: str, persona=None,
                        vault_context: str = ""):
    """Outline one source as vault pages. Returns a dict, or None on failure.

    `persona` is theology_agents.AgentProfile: it replaces the generic team
    line and the sub-agent works strictly within its own specialty. This is
    how one can read the same source in 49 different ways in one pass.
    `vault_context` is the brain's own state snapshot (existing page titles);
    it turns every ingestion into self-improvement: agents link to pages
    that already exist instead of inventing near-duplicates."""
    try:
        if persona is not None:
            team = (f"You are the specialist theology agent '{persona.name}'.\n"
                    f"YOUR BRIEF:\n{persona.description}\n\n"
                    "You are one of MARK-LIV's theology team processing a source. "
                    "Structure it strictly through your own specialty, but fill "
                    "the SAME JSON shape below.\n")
        else:
            team = "You are MARK-LIV's theology team. "
        if vault_context:
            ctx = ("PAGES ALREADY IN THE VAULT (cross-link with [[Exact Title]] "
                   "when relevant; if a page already covers a topic, treat yours "
                   "as an extension of it rather than a near-duplicate):\n"
                   + vault_context + "\n\n")
        else:
            ctx = ""
        prompt = _STRUCTURE_PROMPT.format(
            team=team, ctx=ctx,
            name=source_name, text=text[:_MAX_LEARN_CHARS],
            entities=_MAX_ENTITIES, concepts=_MAX_CONCEPTS)
        response = _gemini_client().generate_content(prompt)
        return _parse_json_object(getattr(response, "text", "") or "")
    except Exception as e:
        print(f"[FileProcessor] theology structuring failed for {source_name}: {e}")
        return None


def _write_structure(bridge, data: dict, source_name: str, totals: dict,
                     agent_name: str | None = None) -> int:
    """Write the source page plus its entities and concepts. Returns page count.

    With `agent_name` set (per-agent learning), every body carries an 'Agent:'
    attribution line and every page is tagged with the agent's name, so the
    vault can hold different agents' readings of the same source on one page.
    """
    written = 0
    prefix = f"Agent: {agent_name}\n\n" if agent_name else ""
    agent_tag = f",{agent_name}" if agent_name else ""
    source = data.get("source")
    if isinstance(source, dict):
        title = str(source.get("title") or Path(source_name).stem).strip()
        body = str(source.get("body") or source.get("summary") or "").strip()
        if title and body:
            bridge.run({"action": "write", "kind": "source", "title": title,
                        "text": prefix + body,
                        "tags": str(source.get("tags") or "source") + agent_tag,
                        "sources": source_name})
            totals["source"] += 1
            written += 1

    for kind, key, limit in (("entity", "entities", _MAX_ENTITIES),
                             ("concept", "concepts", _MAX_CONCEPTS)):
        items = data.get(key)
        if not isinstance(items, list):
            continue
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            body = str(item.get("body") or "").strip()
            if not (title and body):
                continue
            bridge.run({"action": "write", "kind": kind, "title": title,
                        "text": prefix + body,
                        "tags": str(item.get("tags") or kind) + agent_tag,
                        "sources": source_name})
            totals[kind] += 1
            written += 1
    return written


def _theology_learn(paths: list[Path], params: dict, player=None, step=None,
                    profiles=None) -> str:
    """Structure ingested sources into theology vault pages.

    For each file: capture it into raw/, read it (any format), have the model
    outline the source page plus its entities and concepts, then write them via
    theology_brain — which updates the vault index and log. `step(done, label)`
    reports progress to the window when one is open.

    `profiles` (theology_agents.AgentProfile list) routes the pipeline through
    the agents: every selected agent reads every source through its own
    specialty and writes its own pages. None keeps the generic single pass.
    """
    labels = _ui_strings()
    # profiles None (no picker) or [] (picker shown, nothing checked):
    # both mean the generic single pass.
    if profiles:
        agents = _load_theology_agents()
        if agents is None:
            return ("Module theology_agents introuvable — "
                    "apprentissage par agents impossible.")

        def agent_step(done, total_units, label):
            """Adapt (done, total, label) — the agents' contract — to this
            function's step(done, label); totals only matter on a window."""
            if step:
                try:
                    step(done, label)
                except Exception:
                    pass

        return agents.learn_with_agents(paths, profiles, player=player,
                                        step=agent_step)

    bridge = _theology_brain_module()
    if bridge is None:
        return ("Apprentissage par les agents théologie : theology_brain "
                "introuvable — impossible d'écrire dans le vault.")
    try:
        bridge.run({"action": "init"})
    except Exception as e:
        print(f"[FileProcessor] vault init failed: {e}")

    def report(done: int, key: str, name: str) -> None:
        if step:
            try:
                step(done, labels[key].format(name=name))
            except Exception:
                pass

    total = len(paths)
    totals = {"source": 0, "entity": 0, "concept": 0}
    processed, failed = [], []
    new_titles: list[str] = []

    # Same self-improvement as the agents path: the snapshot of what the
    # vault already knows goes into every structuring call.
    vault_context = ""
    try:
        vault_context = bridge.vault_context() if hasattr(bridge, "vault_context") else ""
    except Exception as e:
        print(f"[FileProcessor] vault context unavailable: {e}")

    for index, path in enumerate(paths):
        report(index, "step_reading", path.name)
        try:
            bridge.run({"action": "capture", "path": str(path)})
        except Exception as e:
            print(f"[FileProcessor] theology capture failed for {path.name}: {e}")

        text = _extract_source_text(path)
        if not text.strip():
            failed.append(path.name)
            report(index + 1, "step_done", path.name)
            continue

        report(index, "step_structuring", path.name)
        data = _theology_structure(text, path.name, vault_context=vault_context)
        if isinstance(data, dict) and isinstance(data.get("source"), dict) \
                and str(data["source"].get("title") or "").strip():
            new_titles.append(str(data["source"]["title"]).strip())
        if not isinstance(data, dict) or not data:
            failed.append(path.name)
            report(index + 1, "step_done", path.name)
            continue

        report(index, "step_writing", path.name)
        written = _write_structure(bridge, data, path.name, totals)
        processed.append(f"{path.name} → {written}")
        if player:
            try:
                player.write_log(f"[FileProcessor] théologie: {path.name} → {written} page(s)")
            except Exception:
                pass
        report(index + 1, "step_done", path.name)

    pages = totals["source"] + totals["entity"] + totals["concept"]

    # Batch end: refresh the team's self-knowledge doc (no agent profiles to
    # report here) and teach the prompt mirror what the brain just learned.
    self_doc, mirror = "", ""
    try:
        _agents_mod = _load_theology_agents()
        if _agents_mod is not None:
            self_doc = _agents_mod.refresh_self_knowledge(bridge, [])
            mirror = _agents_mod.refresh_context_mirror(
                bridge, pages, new_titles, len(paths))
    except Exception as e:
        print(f"[FileProcessor] self-knowledge refresh failed: {e}")

    summary = (f"Apprentissage théologie : {pages} page(s) écrite(s) — "
               f"{totals['source']} source(s), {totals['entity']} entité(s), "
               f"{totals['concept']} concept(s) depuis {len(processed)}/{total} fichier(s).")
    if processed:
        summary += " " + " | ".join(processed) + "."
    if failed:
        summary += " Sans texte exploitable : " + ", ".join(failed) + "."
    if self_doc:
        summary += f" Self-knowledge mise à jour ({self_doc}) ; {mirror}."
    return summary


def _process_one(path: Path, action: str, params: dict, speak, player=None) -> str:
    """Type-detect and process a single file (the original file_processor body)."""
    file_type = _detect_type(path)
    log_msg = f"[FileProcessor] {file_type.upper()} | {path.name} | action={action or 'auto'}"
    print(log_msg)
    if player:
        try:
            player.write_log(log_msg)
        except Exception:
            pass

    if file_type == "unknown":
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")[:10000]
            model   = _gemini_client()
            task    = action or params.get("instruction", "") or \
                      "Describe what this file contains and what can be done with it."
            prompt  = f"File: {path.name}\nContent preview:\n{content}\n\nTask: {task}"
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return f"Unknown file type ({path.suffix}). Could not process: {e}"

    dispatch = {
        "image":   _process_image,
        "pdf":     _process_pdf,
        "docx":    lambda p, a, pm, s: _process_text_doc(p, "docx", a, pm, s),
        "text":    lambda p, a, pm, s: _process_text_doc(p, "text", a, pm, s),
        "csv":     lambda p, a, pm, s: _process_data(p, "csv",   a, pm, s),
        "excel":   lambda p, a, pm, s: _process_data(p, "excel", a, pm, s),
        "json":    _process_json,
        "xml":     lambda p, a, pm, s: _process_json(p, a, pm, s),
        "code":    _process_code,
        "audio":   _process_audio,
        "video":   _process_video,
        "archive": _process_archive,
        "pptx":    _process_pptx,
    }

    handler = dispatch.get(file_type)
    if not handler:
        return f"Unsupported file type: {file_type}"

    try:
        result = handler(path, action, params, speak)
        return result or "Done."
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Processing failed: {e}"


def file_processor(parameters: dict, player=None, speak=None) -> str:
    """Ingest one or many files (any mix of types) and process them.

    With no explicit 'action', the ingestion window asks whether to ANALYSE the
    files (the existing behaviour) or hand them to the theology agents, and
    shows progress while the work runs. A 'mode' already set preselects that
    branch in the window instead of skipping the question.
    """
    parameters = parameters or {}
    paths, problems = _collect_paths(parameters)
    if not paths:
        if problems:
            return "Aucun fichier exploitable — " + " ; ".join(problems)
        return "No file path provided."

    action      = (parameters.get("action") or "").lower().strip()
    instruction = parameters.get("instruction", "")
    params      = {**parameters, "instruction": instruction}

    mode = (parameters.get("mode") or "").strip().lower()
    mode = {"analyse": "analyze", "analysis": "analyze", "analyze": "analyze",
            "apprentissage": "learn", "theology": "learn",
            "theologie": "learn", "théologie": "learn", "learn": "learn"}.get(mode, mode)

    chosen = mode if mode in ("analyze", "learn") else None

    # An explicit command needs no question. Otherwise the window is where the
    # choice is made: a branch the model already read out of the user's words is
    # preselected in it rather than silently applied, so the question still gets
    # asked. 'popup': false is the explicit way to skip it.
    _ingest_log(f"call: files={len(paths)} action={action or '-'} mode={chosen or '-'} "
                f"popup={parameters.get('popup')} problems={len(problems)}")

    if not action and _as_bool(parameters.get("popup"), default=True):
        result = _ingestion_window(paths, action, params, speak, player, chosen)
        if result is None:            # no window available: process directly
            _ingest_log(f"done: no window — ran {chosen or 'analyze'} directly")
            result = _run_ingest(paths, chosen or "analyze", action, params, speak, player)
        if problems:
            result += "\n\n" + " ; ".join(problems)
        return result

    _ingest_log(f"done: {chosen or 'analyze'} skipped the window "
                f"(action={action or '-'}, popup={parameters.get('popup')})")
    result = _run_ingest(paths, chosen or "analyze", action, params, speak, player)
    if problems:
        result += "\n\n" + " ; ".join(problems)
    return result


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "file_processor",
    "description": "Ingests and processes files the user has uploaded, dropped onto the interface, or named by path — one file or many at once, any mix of types (multi-support). Supports: images (describe/ocr/resize/compress/convert), PDFs (summarize/extract_text/to_word), Word docs & text files (summarize/fix/reformat/translate), CSV/Excel (analyze/stats/filter/sort/convert), JSON/XML (validate/format/analyze), code files (explain/review/fix/optimize/run/document/test), audio (transcribe/trim/convert/info), video (trim/extract_audio/extract_frame/compress/transcribe/info), archives (list/extract), presentations (summarize/extract_text). Pass several paths in 'file_paths' (newline- or comma-separated) to ingest a batch, or a folder to ingest everything inside it. When the user just wants to INGEST files with no specific command, leave 'action' empty: the tool opens a small window asking whether to ANALYSE the files or send them to the theology agents for LEARNING (a background pipeline that reads each source and writes structured vault pages: sources, entities, concepts) — do not ask that question yourself in chat, and do not set 'mode' to answer it for them; the window then shows progress while it works. If the user gives an explicit command (summarize, ocr, transcribe…), set 'action' and no window is shown. In LEARN mode the window then lists the agent profiles of the user's agents folder (default Desktop\\Agents, override with 'theology_agents_dir' in config/api_keys.json) so the user picks WHICH agents read the files; each selected agent streams its own reading of the source into the theology vault.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "STRING",
                "description": "Full path to a single uploaded file. Leave empty to use the currently uploaded file."
            },
            "file_paths": {
                "type": "STRING",
                "description": "One or more files to ingest at once, newline- or comma-separated. A folder path is also accepted (every file inside it). Use this instead of 'file_path' for multi-file / multi-support ingestion."
            },
            "mode": {
                "type": "STRING",
                "description": "Which branch the ingestion window opens on: 'analyze' or 'learn' (theology agents). It only preselects it — the window still asks, unless 'popup' is false, in which case the branch is forced with no window at all. In 'learn' the window also lists the agent profiles (Desktop\\Agents) so the user chooses which agents study the files."
            },
            "popup": {
                "type": "BOOLEAN",
                "description": "Show the ingestion window when no action is given (default: true). Set false only when the user asks to ingest without a window."
            },
            "action": {
                "type": "STRING",
                "description": "What to do with the file. Examples by type:\nimage: describe | ocr | resize | compress | convert | info\npdf: summarize | extract_text | to_word | info\ndocx/txt: summarize | fix | reformat | translate_hint | word_count | to_bullet\ncsv/excel: analyze | stats | filter | sort | convert | info\njson: validate | format | analyze | to_csv\ncode: explain | review | fix | optimize | run | document | test\naudio: transcribe | trim | convert | info\nvideo: trim | extract_audio | extract_frame | compress | transcribe | info | convert\narchive: list | extract\npptx: summarize | extract_text | analyze"
            },
            "instruction": {
                "type": "STRING",
                "description": "Free-form instruction if action doesn't cover it. E.g. 'translate this to Turkish', 'find all email addresses'"
            },
            "format": {
                "type": "STRING",
                "description": "Target format for conversion. E.g. 'mp3', 'pdf', 'csv', 'png'"
            },
            "width": {
                "type": "INTEGER",
                "description": "Target width for image resize"
            },
            "height": {
                "type": "INTEGER",
                "description": "Target height for image resize"
            },
            "scale": {
                "type": "NUMBER",
                "description": "Scale factor for image resize (e.g. 0.5)"
            },
            "quality": {
                "type": "INTEGER",
                "description": "Quality 1-100 for image/video compress"
            },
            "start": {
                "type": "STRING",
                "description": "Start time for trim: seconds or HH:MM:SS"
            },
            "end": {
                "type": "STRING",
                "description": "End time for trim: seconds or HH:MM:SS"
            },
            "timestamp": {
                "type": "STRING",
                "description": "Timestamp for video frame extraction HH:MM:SS"
            },
            "column": {
                "type": "STRING",
                "description": "Column name for CSV filter/sort"
            },
            "value": {
                "type": "STRING",
                "description": "Filter value for CSV filter"
            },
            "condition": {
                "type": "STRING",
                "description": "Filter condition: equals|contains|gt|lt"
            },
            "ascending": {
                "type": "BOOLEAN",
                "description": "Sort order for CSV sort (default: true)"
            },
            "save": {
                "type": "BOOLEAN",
                "description": "Save result to file (default: true)"
            },
            "destination": {
                "type": "STRING",
                "description": "Output folder for archive extract"
            }
        },
        "required": []
    },
    "handler": file_processor,
}
