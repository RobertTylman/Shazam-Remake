import os
import io
import tempfile
import numpy as np
import matplotlib.pyplot as plt
import base64
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Add current path to PYTHONPATH so imports resolve correctly when run deeply
import sys
sys.path.append(os.path.dirname(__file__))

from src.audioprocessing import load_audio, process_audio_pipeline
from src.fingerprinting import extract_peaks
from src.hashing import hashingAlgorithm
from src.identify import identify_audio
from src.database import Database

# Force Matplotlib to not try and pop up X11 windows in threaded environment
import matplotlib
matplotlib.use('Agg')

app = FastAPI(title="Shazam Web Interface")

# Mount the static directory
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    with open("static/index.html", "r") as f:
        return f.read()

def _process_audio_file(audio_path: str) -> dict:
    """Core processing logic shared by upload and path-based endpoints."""
    test_sr, full_audio = load_audio(audio_path)
    if len(full_audio.shape) > 1 and full_audio.shape[1] > 1:
        full_audio = np.mean(full_audio, axis=1)

    t = np.linspace(0, len(full_audio) / test_sr, len(full_audio), endpoint=False)

    frame_size = 1024
    spec, sr = process_audio_pipeline(audio_path, frame_size=frame_size)
    peaks = extract_peaks(spec, coefficient=1.0)

    step_size = int(frame_size * 0.5)
    max_plot_seconds = len(full_audio) / test_sr

    peak_times = [p[0] for p in peaks]
    peak_freqs = [p[1] for p in peaks]

    time_bins_in_seconds = [idx * (step_size / sr) for idx in peak_times]
    freq_bins_in_hz = [idx * (sr / frame_size) for idx in peak_freqs]

    spec_db = 10 * np.log10(spec + 1e-10)

    hash_records = hashingAlgorithm(
        peaks,
        target_zone_time=50,
        target_zone_freq=80,
        max_targets_per_anchor=5,
        include_metadata=True
    )

    fig = plt.figure(figsize=(24, 12))
    gs = fig.add_gridspec(2, 1, height_ratios=[2, 1])
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])

    im = ax1.imshow(spec_db, aspect='auto', origin='lower', cmap='viridis',
               extent=[0, max_plot_seconds, 0, sr / 2])

    if peaks:
        ax1.scatter(time_bins_in_seconds, freq_bins_in_hz, color='red', marker='x', alpha=0.9, label='Extracted Peaks')
        ax1.legend(loc="upper right")

    ax1.set_title(f"Constellation Map over Spectrogram (Full Track: {max_plot_seconds:.1f}s)")
    ax1.set_ylabel("Frequency (Hz)")
    fig.colorbar(im, ax=ax1, format='%+2.0f dB')

    ax2.plot(t, full_audio, color='blue', alpha=0.8)
    ax2.set_title(f"Original Time Domain Signal (Full Track: {max_plot_seconds:.1f}s)")
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Amplitude")
    ax2.set_xlim([0, max_plot_seconds])

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    buf.seek(0)
    plt.close(fig)

    img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    spec_db_flipped = np.flipud(spec_db)
    spec_min = np.min(spec_db_flipped)
    spec_max = np.max(spec_db_flipped)
    spec_norm = (spec_db_flipped - spec_min) / (spec_max - spec_min + 1e-10)
    rgba = (plt.get_cmap("viridis")(spec_norm) * 255).astype(np.uint8)

    spec_buf = io.BytesIO()
    plt.imsave(spec_buf, rgba)
    spec_buf.seek(0)
    spec_img_b64 = base64.b64encode(spec_buf.getvalue()).decode("utf-8")

    time_per_frame = step_size / sr
    hz_per_bin = sr / frame_size
    hashes_for_ui = []
    for idx, row in enumerate(hash_records):
        anchor_time = int(row["anchor_time"])
        anchor_freq = int(row["anchor_freq"])
        target_time = int(row["target_time"])
        target_freq = int(row["target_freq"])
        delta_time = int(row["delta_time"])
        hash_val = int(row["hash"])

        hashes_for_ui.append({
            "id": idx,
            "hash_int": hash_val,
            "hash_hex": f"0x{hash_val:08x}",
            "anchor_time_frame": anchor_time,
            "anchor_freq_bin": anchor_freq,
            "target_time_frame": target_time,
            "target_freq_bin": target_freq,
            "delta_time_frames": delta_time,
            "anchor_time_s": float(anchor_time * time_per_frame),
            "target_time_s": float(target_time * time_per_frame),
            "anchor_freq_hz": float(anchor_freq * hz_per_bin),
            "target_freq_hz": float(target_freq * hz_per_bin)
        })

    return {
        "image": f"data:image/png;base64,{img_b64}",
        "spectrogram_image": f"data:image/png;base64,{spec_img_b64}",
        "duration": float(max_plot_seconds),
        "peaks": len(peaks),
        "hashes": hashes_for_ui,
        "num_hashes": len(hashes_for_ui),
        "num_frames": int(spec.shape[1]),
        "num_freq_bins": int(spec.shape[0]),
        "frame_size": int(frame_size),
        "hop_size": int(step_size),
        "lowest_hz": 0,
        "highest_hz": float(sr / 2)
    }


@app.post("/api/process")
async def process_audio(file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename)[1]
    if not suffix:
        suffix = ".wav"

    fd, temp_audio_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)

    with open(temp_audio_path, "wb") as f:
        f.write(await file.read())

    try:
        result = _process_audio_file(temp_audio_path)
        return JSONResponse(content=result)
    finally:
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)


@app.post("/api/process-path")
async def process_audio_by_path(request: Request):
    """Process an audio file already on disk (e.g. from the library)."""
    body = await request.json()
    filepath = body.get("path", "")
    if not filepath or not os.path.isfile(filepath):
        return JSONResponse(status_code=400, content={"status": "error", "message": "File not found."})

    result = _process_audio_file(filepath)
    return JSONResponse(content=result)

@app.get("/api/library")
async def get_library():
    try:
        db = Database()
        songs = db.get_all_songs_with_stats()
        
        # Calculate totals from the row data to avoid re-scanning the 6M row table
        total_songs = len(songs)
        total_fingerprints = sum(s["fingerprints"] for s in songs)
        
        stats = {
            "total_songs": total_songs,
            "total_fingerprints": total_fingerprints,
            "db_size_mb": db.get_db_size_mb()
        }
        return JSONResponse(content={
            "status": "success",
            "songs": songs,
            "stats": stats
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.post("/api/identify")
async def identify_song(file: UploadFile = File(...)):
    # Save the uploaded file temporarily
    suffix = os.path.splitext(file.filename)[1]
    if not suffix:
        suffix = ".wav"
        
    fd, temp_audio_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    
    with open(temp_audio_path, "wb") as f:
        f.write(await file.read())
        
    try:
        result = identify_audio(temp_audio_path)
        if result:
            return JSONResponse(content={
                "status": "success",
                "match": True,
                "song": result["name"],
                "confidence": result["confidence"],
                "match_density": result["match_density"],
                "dominance": result["dominance"],
                "offset": result["offset_s"],
                "score": result["score"],
                "query_fingerprints": result["query_fingerprints"],
                "query_peaks": result["query_peaks"],
                "db_hits": result["db_hits"],
                "songs_matched": result["songs_matched"],
                "second_score": result["second_score"]
            })
        else:
            return JSONResponse(content={
                "status": "success",
                "match": False,
                "message": "No match found in library."
            })
            
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
    finally:
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

if __name__ == "__main__":
    import uvicorn
    # Execute the default ASGI web server
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
