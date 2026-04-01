import os
import io
import tempfile
import numpy as np
import matplotlib.pyplot as plt
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# Add current path to PYTHONPATH so imports resolve correctly when run deeply
import sys
sys.path.append(os.path.dirname(__file__))

from src.audioprocessing import load_audio, process_audio_pipeline
from src.fingerprinting import extract_peaks

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

@app.post("/api/process")
async def process_audio(file: UploadFile = File(...)):
    # Save the uploaded file temporarily
    suffix = os.path.splitext(file.filename)[1]
    if not suffix:
        suffix = ".wav"
        
    fd, temp_audio_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    
    with open(temp_audio_path, "wb") as f:
        f.write(await file.read())
        
    try:
        # Load audio first to find original SR and length
        test_sr, full_audio = load_audio(temp_audio_path)
        if len(full_audio.shape) > 1 and full_audio.shape[1] > 1:
            full_audio = np.mean(full_audio, axis=1)
            
        t = np.linspace(0, len(full_audio) / test_sr, len(full_audio), endpoint=False)
        
        # Pipeline execution
        frame_size = 1024
        spec, sr = process_audio_pipeline(temp_audio_path, frame_size=frame_size)
        peaks = extract_peaks(spec, coefficient=1.0)
        
        # Plotting
        step_size = int(frame_size * 0.5)
        # We limit the graph to the first 5 seconds to avoid freezing the web server instance
        max_plot_seconds = min(5.0, len(full_audio) / test_sr)
        max_spec_frames = int(max_plot_seconds * sr / step_size)
        
        plot_spec = spec[:, :max_spec_frames]
        plot_peaks = [p for p in peaks if p[0] < max_spec_frames]
        peak_times = [p[0] for p in plot_peaks]
        peak_freqs = [p[1] for p in plot_peaks]
        
        time_bins_in_seconds = [idx * (step_size / sr) for idx in peak_times]
        freq_bins_in_hz = [idx * (sr / frame_size) for idx in peak_freqs]

        # Log scale mapping
        spec_db = 10 * np.log10(plot_spec + 1e-10)
        
        # Object-Oriented Matplotlib plotting (thread-safe for FastAPI)
        fig = plt.figure(figsize=(10, 8))
        gs = fig.add_gridspec(2, 1, height_ratios=[2, 1])
        ax1 = fig.add_subplot(gs[0])
        ax2 = fig.add_subplot(gs[1])
        
        im = ax1.imshow(spec_db, aspect='auto', origin='lower', cmap='viridis', 
                   extent=[0, max_plot_seconds, 0, sr / 2])
        
        if plot_peaks:
            ax1.scatter(time_bins_in_seconds, freq_bins_in_hz, color='red', marker='x', alpha=0.9, label='Extracted Peaks')
            ax1.legend(loc="upper right")
            
        ax1.set_title(f"Constellation Map over Spectrogram (First {max_plot_seconds:.1f}s of Upload)")
        ax1.set_ylabel("Frequency (Hz)")
        fig.colorbar(im, ax=ax1, format='%+2.0f dB')
        
        # Waveform Plot
        max_audio_samples = int(max_plot_seconds * test_sr)
        ax2.plot(t[:max_audio_samples], full_audio[:max_audio_samples], color='blue', alpha=0.8)
        ax2.set_title(f"Original Time Domain Signal (First {max_plot_seconds:.1f}s)")
        ax2.set_xlabel("Time (s)")
        ax2.set_ylabel("Amplitude")
        ax2.set_xlim([0, max_plot_seconds])
        
        plt.tight_layout()
        
        # Dump to memory buffer, prevent saving to disk arbitrarily 
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        
        # Close figure globally to free memory
        plt.close(fig)
        
        return StreamingResponse(buf, media_type="image/png")
        
    finally:
        # Secure cleanup
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

if __name__ == "__main__":
    import uvicorn
    # Execute the default ASGI web server
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
