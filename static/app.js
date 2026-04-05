document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const loaderContainer = document.getElementById('loader-container');
    const resultsSection = document.getElementById('results-section');
    const resultImage = document.getElementById('result-image');
    const interactiveSpectrogram = document.getElementById('interactive-spectrogram');
    const hashList = document.getElementById('hash-list');
    const selectedHashDetails = document.getElementById('selected-hash-details');
    const hashLine = document.getElementById('hash-line');
    const hashAnchor = document.getElementById('hash-anchor');
    const hashTarget = document.getElementById('hash-target');
    const resetBtn = document.getElementById('reset-btn');
    let lastHashes = [];
    let selectedHashId = null;
    let trackMeta = {};

    // --- Event Listeners for Drag and Drop ---
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // Highlight drop zone
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('dragover');
        }, false);
    });

    // Handle dropped files
    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }, false);

    // Handle click to browse
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    // Handle selected files
    fileInput.addEventListener('change', function() {
        handleFiles(this.files);
    });

    function handleFiles(files) {
        if (files.length === 0) return;
        
        const file = files[0];
        
        // Basic validation
        if (!file.type.startsWith('audio/') && !file.name.match(/\.(wav|m4a|mp3)$/i)) {
            alert('Please upload an audio file (.wav, .m4a, .mp3)');
            return;
        }

        uploadAndProcessFile(file);
    }

    async function uploadAndProcessFile(file) {
        // UI State: Uploading / Processing
        dropZone.classList.add('hidden');
        resultsSection.classList.add('hidden');
        loaderContainer.classList.remove('hidden');

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/process', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`Server returned status: ${response.status}`);
            }

            // Parse API response
            const data = await response.json();

            // Display Results
            resultImage.src = data.image;
            
            // Hydrate Tracking Telemetry
            document.getElementById('stat-duration').textContent = data.duration.toFixed(2) + 's';
            document.getElementById('stat-peaks').textContent = data.peaks.toLocaleString();
            document.getElementById('stat-hashes').textContent = data.num_hashes.toLocaleString();
            document.getElementById('stat-frames').textContent = data.num_frames.toLocaleString();
            document.getElementById('stat-frame-size').textContent = data.frame_size.toLocaleString();
            document.getElementById('stat-hop-size').textContent = data.hop_size.toLocaleString();
            document.getElementById('stat-lowest-hz').textContent = data.lowest_hz + ' Hz';
            document.getElementById('stat-highest-hz').textContent = data.highest_hz.toFixed(1) + ' Hz';
            trackMeta = {
                duration: data.duration,
                lowestHz: data.lowest_hz,
                highestHz: data.highest_hz,
                numFrames: data.num_frames,
                numFreqBins: data.num_freq_bins,
            };

            lastHashes = data.hashes || [];
            selectedHashId = null;
            renderHashList(lastHashes, data.num_frames, data.num_freq_bins);

            // Render axes once the spectrogram image has loaded
            interactiveSpectrogram.onload = () => {
                renderFreqAxis();
                renderTimeAxis();
            };
            interactiveSpectrogram.src = data.spectrogram_image;

            // UI State: Complete
            loaderContainer.classList.add('hidden');
            resultsSection.classList.remove('hidden');
            
            // Scroll to results smoothly if needed
            resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

        } catch (error) {
            console.error('Error processing audio:', error);
            alert('Failed to process the audio file. Please ensure the backend is running and the file is valid.');
            
            // Revert State on error
            loaderContainer.classList.add('hidden');
            dropZone.classList.remove('hidden');
            fileInput.value = ''; // clear input
        }
    }

    function renderHashList(hashes, numFrames, numFreqBins) {
        hashList.innerHTML = '';
        clearHashOverlay();

        if (!hashes.length) {
            selectedHashDetails.textContent = 'No hashes generated for this track.';
            return;
        }

        selectedHashDetails.textContent = `Select one of ${hashes.length.toLocaleString()} hashes to show its location.`;

        const fragment = document.createDocumentFragment();
        hashes.forEach(hashRow => {
            const btn = document.createElement('button');
            btn.className = 'hash-item';
            btn.type = 'button';
            btn.dataset.hashId = String(hashRow.id);

            const main = document.createElement('span');
            main.className = 'hash-main';
            main.textContent = hashRow.hash_hex;

            const sub = document.createElement('span');
            sub.className = 'hash-sub';
            sub.textContent = `[${hashRow.anchor_time_frame},${hashRow.anchor_freq_bin}] → [${hashRow.target_time_frame},${hashRow.target_freq_bin}]`;

            btn.appendChild(main);
            btn.appendChild(sub);

            btn.addEventListener('click', () => {
                selectedHashId = hashRow.id;
                highlightSelectedRow();
                drawHashOverlay(hashRow, numFrames, numFreqBins);
            });

            fragment.appendChild(btn);
        });

        hashList.appendChild(fragment);
    }

    function highlightSelectedRow() {
        const rows = hashList.querySelectorAll('.hash-item');
        rows.forEach(row => {
            const isActive = Number(row.dataset.hashId) === selectedHashId;
            row.classList.toggle('active', isActive);
        });
    }

    function syncOverlaySize() {
        const img = interactiveSpectrogram;
        const svg = document.getElementById('hash-overlay');
        const w = img.clientWidth;
        const h = img.clientHeight;
        svg.setAttribute('width', w);
        svg.setAttribute('height', h);
        svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
    }

    function drawHashOverlay(hashRow, numFrames, numFreqBins) {
        syncOverlaySize();
        const img = interactiveSpectrogram;
        const w = img.clientWidth;
        const h = img.clientHeight;

        const x1 = normalizeX(hashRow.anchor_time_frame, numFrames, w);
        const y1 = normalizeY(hashRow.anchor_freq_bin, numFreqBins, h);
        const x2 = normalizeX(hashRow.target_time_frame, numFrames, w);
        const y2 = normalizeY(hashRow.target_freq_bin, numFreqBins, h);

        hashLine.setAttribute('x1', x1);
        hashLine.setAttribute('y1', y1);
        hashLine.setAttribute('x2', x2);
        hashLine.setAttribute('y2', y2);
        hashAnchor.setAttribute('cx', x1);
        hashAnchor.setAttribute('cy', y1);
        hashTarget.setAttribute('cx', x2);
        hashTarget.setAttribute('cy', y2);

        selectedHashDetails.textContent =
            `${hashRow.hash_hex} | anchor ${hashRow.anchor_time_s.toFixed(3)}s @ ${hashRow.anchor_freq_hz.toFixed(1)}Hz -> target ${hashRow.target_time_s.toFixed(3)}s @ ${hashRow.target_freq_hz.toFixed(1)}Hz (Δt=${hashRow.delta_time_frames} frames)`;
    }

    function clearHashOverlay() {
        hashLine.setAttribute('x1', 0);
        hashLine.setAttribute('y1', 0);
        hashLine.setAttribute('x2', 0);
        hashLine.setAttribute('y2', 0);
        hashAnchor.setAttribute('cx', 0);
        hashAnchor.setAttribute('cy', 0);
        hashTarget.setAttribute('cx', 0);
        hashTarget.setAttribute('cy', 0);
    }

    function normalizeX(frameIdx, numFrames, width) {
        if (numFrames <= 1) return 0;
        return (frameIdx / (numFrames - 1)) * width;
    }

    function normalizeY(freqBin, numFreqBins, height) {
        if (numFreqBins <= 1) return height;
        return (1 - (freqBin / (numFreqBins - 1))) * height;
    }

    function renderFreqAxis() {
        const container = document.getElementById('freq-axis');
        container.innerHTML = '';
        const imgH = interactiveSpectrogram.clientHeight;
        container.style.height = imgH + 'px';
        const lo = trackMeta.lowestHz || 0;
        const hi = trackMeta.highestHz || 22050;
        const numTicks = 8;
        for (let i = 0; i <= numTicks; i++) {
            const frac = i / numTicks;
            const hz = lo + frac * (hi - lo);
            const y = (1 - frac) * imgH;
            const tick = document.createElement('span');
            tick.className = 'freq-tick';
            tick.style.top = y + 'px';
            tick.textContent = hz >= 1000 ? (hz / 1000).toFixed(1) + 'k' : Math.round(hz);
            container.appendChild(tick);
        }
    }

    function renderTimeAxis() {
        const container = document.getElementById('time-axis');
        container.innerHTML = '';
        const imgW = interactiveSpectrogram.clientWidth;
        container.style.width = imgW + 'px';
        const dur = trackMeta.duration || 1;
        const numTicks = Math.min(20, Math.floor(dur));
        const step = dur / numTicks;
        for (let i = 0; i <= numTicks; i++) {
            const t = i * step;
            const x = (t / dur) * imgW;
            const tick = document.createElement('span');
            tick.className = 'time-tick';
            tick.style.left = x + 'px';
            tick.textContent = t.toFixed(1) + 's';
            container.appendChild(tick);
        }
    }

    // Re-sync overlay when window resizes
    window.addEventListener('resize', () => {
        if (selectedHashId !== null && lastHashes.length) {
            const h = lastHashes.find(r => r.id === selectedHashId);
            if (h) syncOverlaySize();
        }
    });

    // Reset workflow
    resetBtn.addEventListener('click', () => {
        resultImage.src = '';
        interactiveSpectrogram.src = '';
        fileInput.value = '';
        hashList.innerHTML = '';
        selectedHashDetails.textContent = 'Select a hash to locate it on the spectrogram.';
        lastHashes = [];
        selectedHashId = null;
        clearHashOverlay();
        
        // Go back to drop zone
        resultsSection.classList.add('hidden');
        dropZone.classList.remove('hidden');
        
        // Scroll back to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
});
