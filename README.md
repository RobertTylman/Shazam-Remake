# Shazam
> A recreation of the Shazam music recognition algorithm.

## Overview
This project aims to recreate the core algorithm behind Shazam's audio acoustic recognition capabilities, utilizing audio fingerprinting and fast database lookups. 

## Technical Architecture

The following diagram maps out the data pipeline from registering tracks into the main database, to how user devices capture audio snippets and match them against the huge reference database.

```mermaid
flowchart TD
    subgraph Shazam [SHAZAM INFRASTRUCTURE]
        direction LR
        
        subgraph TopRow [ ]
            style TopRow fill:none,stroke:none
            DB1[(Very large<br>music database<br>millions)]
            DB2[(Very large<br>fingerprint<br>database)]
            DB1 -- fingerprinting<br>algorithm --> DB2
        end

        Frontal[Frontal servers]
        Frontal -- checks if the fingerprint exists<br>and return the associated music --> DB2
    end
    
    subgraph User [USER APPLICATION - User phone via Shazam apps]
        direction LR
        Record[records X seconds of<br>the current music]
        RecordFP[fingerprint of<br>the record]
        
        Record -- fingerprinting<br>algorithm --> RecordFP
    end
    
    RecordFP -- Ask for the music<br>associated with<br>the fingerprint ---> Frontal
```

## How It Works

The core of the algorithm is based on creating robust identifiers for audio clips that can survive noise, distortion, and compression.

1. **Ingestion & Spectrogram Generation:**
   Audio files act as raw inputs, which are mixed down to a neutral mono-signal. Background interference is purged via a tight 20Hz-5kHz mathematical bandpass filter, before safely decimating the sample stream down to an optimized 11,025Hz. An overlapping segmented frame pass computes a localized Hamming-Windowed Fast Fourier Transform (FFT) turning the waveform into a dense 2D magnitude spectrogram array.

2. **Constellation Map Extraction (Peak Finding):**
   To parse the dense spectrogram, the algorithm slices the vertical frequency axis into 6 specific logarithmic bins (mimicking human hearing prioritization):
   * *Very Low* `[0-10]`
   * *Low* `[10-20]`
   * *Low-Mid* `[20-40]`
   * *Mid* `[40-80]`
   * *Mid-High* `[80-160]`
   * *High* `[160-511]`
      The algorithm hunts across every timeframe, finding the single loudest peak frequency exclusively within each of these 6 segregated sub-bands. A global mean threshold filters against background fuzz by averaging these localized acoustic power events across the entire track. Finally, any data points breaching this threshold survive as confirmed targets, reducing millions of data points into a hyper-sparse, robust coordinate map known as a "Constellation Map".

![Fingerprint Peaks](./peaks.png)
*Visualizing the high-intensity peaks (dots) across the frequency spectrum over time.*

3. **Target Zones & Hashing:**
   These scattered constellation peaks are grouped into localized structural pairings (target zones) mapping time displacements between robust fundamentals to create highly unique collision-resistant integer hashes that fundamentally define the structural identity of the audio independent of ambient room distortions.

4. **Database Generation (Infrastructure):**
   A massive catalog of original music is processed by the fingerprinting algorithm. The result is stored in a highly optimized SQLite database containing millions of hashes mapped to their associated songs and relative timestamps (using B-Tree indexing for O(log N) lookup).

5. **User Query (Application):**
   When a user wants to identify a song, the application records a 10-second audio sample via the browser's `MediaRecorder` API or processes an uploaded file. This sample undergoes the exact same fingerprinting algorithm to produce a set of query hashes.

6. **Matching & Retrieval (Time Coherence Scoring):**
   These query hashes are sent to the backend, which looks them up in the fingerprint database. The engine performs **Time Coherence Scoring**: it calculates the time-offset between every matched hash in the snippet vs the original track. By finding the most frequent offset (the "mode"), the algorithm can identify the song even if the sample starts halfway through, with high certainty despite background noise.

## Features
- **Acoustic Fingerprinting:** Fast and scalable audio hashing mechanisms.
- **Audio Identification:** Real-time matching using time-coherence scoring across millions of fingerprints.
- **Microphone Support:** Shazam-style "Listen" mode with real-time volume visualization.
- **Large Dataset Support:** Optimized SQLite storage designed to handle massive libraries with high-speed B-Tree indexing.
- **Visual Diagnostics:** Full spectrograms and constellation peak overlays for every analyzed track.
- **Library Browser:** Browse your entire indexed collection and view real-time database statistics.

## Usage
### 1) Install dependencies
```bash
python3 -m pip install -r requirements.txt
```

### 2) Run the web app
```bash
python3 app.py
```

Open: `http://127.0.0.1:8000`

### 3) Navigation Modes
The web UI provides three distinct modes:
*   **Analyze (Default):** Upload full-length tracks to generate and visualize fingerprints.
*   **Identify:** Identify a song by recording a 10-second snippet (Microphone) or uploading a short audio file.
*   **Library:** Browse your indexed collection, search by track name, and view database stats (Total Songs, Hashes, and DB size).

### 3) Run the CLI pipeline directly (optional)

Run against a file:

```bash
export PYTHONPATH=$PYTHONPATH:.
python3 src/audioprocessing.py "/path/to/your/audio_file.wav"
```

If no arguments are provided, a built-in dummy signal test is generated:

```bash
python3 src/audioprocessing.py
```

The CLI output plot is written to: `/tmp/spectrogram_test.png`
