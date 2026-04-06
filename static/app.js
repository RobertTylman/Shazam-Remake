document.addEventListener('DOMContentLoaded', () => {
    const themeToggle = document.getElementById('theme-toggle');
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const loaderContainer = document.getElementById('loader-container');
    const resultsSection = document.getElementById('results-section');
    const resultImage = document.getElementById('result-image');
    const interactiveSpectrogram = document.getElementById('interactive-spectrogram');
    const spectrogramWrap = document.getElementById('spectrogram-wrap');
    const hashOverlay = document.getElementById('hash-overlay');
    const hashList = document.getElementById('hash-list');
    const selectedHashDetails = document.getElementById('selected-hash-details');
    const resetBtn = document.getElementById('reset-btn');
    const modeAnalyze = document.getElementById('mode-analyze');
    const modeIdentify = document.getElementById('mode-identify');
    const analyzeSection = document.getElementById('analyze-section');
    const identifySection = document.getElementById('identify-section');
    const recordBtn = document.getElementById('record-btn');
    const recordStatus = document.getElementById('record-status');
    const identifyResults = document.getElementById('identify-results');
    const noMatchView = document.getElementById('no-match-view');
    const matchSongName = document.getElementById('match-song-name');
    const matchConfidence = document.getElementById('match-confidence');
    const matchOffset = document.getElementById('match-offset');
    const resetIdBtn = document.getElementById('reset-id-btn');
    const resetNoMatchBtn = document.getElementById('reset-no-match-btn');
    const modeLibrary = document.getElementById('mode-library');
    const librarySection = document.getElementById('library-section');
    const libraryTbody = document.getElementById('library-tbody');
    const librarySearch = document.getElementById('library-search');
    const libStatSongs = document.getElementById('lib-stat-songs');
    const libStatHashes = document.getElementById('lib-stat-hashes');
    const libStatSize = document.getElementById('lib-stat-size');

    let libraryData = [];
    let lastHashes = [];
    let selectedHashId = null;
    let trackMeta = {};
    let mediaRecorder = null;
    let audioChunks = [];
    let isRecording = false;
    let currentMode = 'identify'; // 'analyze', 'identify', or 'library'
    const THEME_STORAGE_KEY = 'shazam-theme';

    initTheme();

    themeToggle.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme') || 'dark';
        const next = current === 'dark' ? 'light' : 'dark';
        applyTheme(next);
        localStorage.setItem(THEME_STORAGE_KEY, next);
    });

    // --- Event Listeners for Drag and Drop ---
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function initTheme() {
        const saved = localStorage.getItem(THEME_STORAGE_KEY);
        const initial = saved || 'dark';
        applyTheme(initial);
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        themeToggle.textContent = theme === 'light' ? 'Dark mode' : 'Light mode';
    }

    function getFullscreenElement() {
        return document.fullscreenElement || document.webkitFullscreenElement || null;
    }

    function requestFullscreen(el) {
        if (el.requestFullscreen) return el.requestFullscreen();
        if (el.webkitRequestFullscreen) return el.webkitRequestFullscreen();
        return Promise.resolve();
    }

    function exitFullscreen() {
        if (document.exitFullscreen) return document.exitFullscreen();
        if (document.webkitExitFullscreen) return document.webkitExitFullscreen();
        return Promise.resolve();
    }

    function updateFullscreenState() {
        const isFullscreen = getFullscreenElement() === spectrogramWrap;
        spectrogramWrap.classList.toggle('is-fullscreen', isFullscreen);
        if (isFullscreen || selectedHashId !== null) {
            refreshSpectrogramLayout();
        }
    }

    async function toggleSpectrogramFullscreen() {
        if (!interactiveSpectrogram.src) return;
        const isFullscreen = getFullscreenElement() === spectrogramWrap;
        try {
            if (isFullscreen) {
                await exitFullscreen();
            } else {
                await requestFullscreen(spectrogramWrap);
            }
        } catch (error) {
            console.error('Fullscreen toggle failed:', error);
        }
    }

    async function toggleResultImageFullscreen() {
        if (!resultImage.src) return;
        const isFullscreen = getFullscreenElement() === resultImage;
        try {
            if (isFullscreen) {
                await exitFullscreen();
            } else {
                await requestFullscreen(resultImage);
            }
        } catch (error) {
            console.error('Result image fullscreen toggle failed:', error);
        }
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
        if (currentMode === 'analyze') {
            handleFiles(this.files);
        } else {
            identifyFile(this.files[0]);
        }
    });

    modeAnalyze.addEventListener('click', () => {
        currentMode = 'analyze';
        setActiveMode(modeAnalyze);
        analyzeSection.classList.remove('hidden');
        identifySection.classList.add('hidden');
        librarySection.classList.add('hidden');
        resultsSection.classList.add('hidden');
        dropZone.classList.remove('hidden');
    });

    modeIdentify.addEventListener('click', () => {
        currentMode = 'identify';
        setActiveMode(modeIdentify);
        identifySection.classList.remove('hidden');
        analyzeSection.classList.add('hidden');
        librarySection.classList.add('hidden');
        resultsSection.classList.add('hidden');
        
        // Ensure initial state
        identifyResults.classList.add('hidden');
        noMatchView.classList.add('hidden');
        recordBtn.parentElement.classList.remove('hidden');
        recordStatus.textContent = 'Tap to Identify';
    });

    modeLibrary.addEventListener('click', () => {
        currentMode = 'library';
        setActiveMode(modeLibrary);
        librarySection.classList.remove('hidden');
        analyzeSection.classList.add('hidden');
        identifySection.classList.add('hidden');
        resultsSection.classList.add('hidden');
        
        fetchLibrary();
    });

    function setActiveMode(activeBtn) {
        [modeAnalyze, modeIdentify, modeLibrary].forEach(btn => {
            btn.classList.toggle('active', btn === activeBtn);
        });
    }

    // --- Recording Logic ---
    recordBtn.addEventListener('click', async () => {
        if (isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    });

    let _recStream = null;
    let _recAudioCtx = null;
    let _animId = null;
    let _identifyTimer = null;
    let _matchFound = false;
    let _attemptNum = 0;
    const ATTEMPT_INTERVAL = 5000;  // try every 5 seconds
    const MAX_LISTEN_TIME = 30000;  // give up after 30 seconds

    async function startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            _recStream = stream;
            _matchFound = false;
            _attemptNum = 0;

            // Wire up Web Audio for real-time waveform visualization
            const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            _recAudioCtx = audioCtx;
            if (audioCtx.state === 'suspended') await audioCtx.resume();

            const source = audioCtx.createMediaStreamSource(stream);
            const analyser = audioCtx.createAnalyser();
            analyser.fftSize = 2048;
            analyser.smoothingTimeConstant = 0;
            source.connect(analyser);

            const waveform = new Float32Array(analyser.fftSize);

            function pulse() {
                if (!isRecording) return;

                analyser.getFloatTimeDomainData(waveform);

                let peak = 0;
                for (let i = 0; i < waveform.length; i++) {
                    const abs = Math.abs(waveform[i]);
                    if (abs > peak) peak = abs;
                }

                const n = Math.min(Math.pow(peak, 0.4) * 1.5, 1);
                const scale = 1 + n * 0.55;
                const glow = Math.round(n * 45);

                recordBtn.style.transform = `scale(${scale})`;
                recordBtn.style.boxShadow = glow > 1
                    ? `0 0 ${glow}px ${Math.round(glow * 0.4)}px rgba(255,255,255,${(n * 0.55).toFixed(2)})`
                    : 'none';
                recordBtn.style.borderColor = `rgba(255,255,255,${(0.15 + n * 0.85).toFixed(2)})`;

                _animId = requestAnimationFrame(pulse);
            }

            // Start visual + state
            isRecording = true;
            recordBtn.classList.add('recording');
            recordStatus.textContent = 'Listening...';
            pulse();

            // MediaRecorder — accumulate all chunks for progressively longer attempts
            const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                ? 'audio/webm;codecs=opus'
                : 'audio/webm';
            mediaRecorder = new MediaRecorder(stream, { mimeType });
            audioChunks = [];

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) audioChunks.push(event.data);
            };

            // Request data every second so chunks accumulate
            mediaRecorder.start(1000);

            // Periodically attempt identification with accumulated audio
            async function tryIdentify() {
                if (!isRecording || _matchFound) return;
                if (audioChunks.length === 0) return;

                _attemptNum++;
                const elapsed = _attemptNum * (ATTEMPT_INTERVAL / 1000);
                recordStatus.textContent = `Listening... ${elapsed}s`;

                // Build blob from ALL chunks so far (progressively longer sample)
                const audioBlob = new Blob([...audioChunks], { type: mimeType });
                const audioFile = new File([audioBlob], "recording.webm", { type: mimeType });

                const formData = new FormData();
                formData.append('file', audioFile);

                try {
                    const response = await fetch('/api/identify', {
                        method: 'POST',
                        body: formData
                    });

                    if (!response.ok || !isRecording || _matchFound) return;

                    const data = await response.json();
                    if (data.match) {
                        _matchFound = true;
                        cleanupRecording();

                        // Show result
                        loaderContainer.classList.add('hidden');
                        populateMatchResults(data);
                        identifyResults.classList.remove('hidden');
                    }
                } catch (e) {
                    console.error('Identify attempt failed:', e);
                }
            }

            // First attempt after 5s, then every 5s
            _identifyTimer = setInterval(tryIdentify, ATTEMPT_INTERVAL);

            // Hard stop after max time
            setTimeout(() => {
                if (isRecording && !_matchFound) {
                    stopRecording();
                }
            }, MAX_LISTEN_TIME);

        } catch (err) {
            console.error('Recording Error:', err);
            alert('Cannot access microphone. Please check permissions.');
            recordStatus.textContent = 'Tap to Identify';
        }
    }

    function cleanupRecording() {
        isRecording = false;
        if (_animId) { cancelAnimationFrame(_animId); _animId = null; }
        if (_identifyTimer) { clearInterval(_identifyTimer); _identifyTimer = null; }
        recordBtn.classList.remove('recording');
        recordBtn.style.transform = '';
        recordBtn.style.boxShadow = '';
        recordBtn.style.borderColor = '';
        if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
        if (_recAudioCtx) { _recAudioCtx.close(); _recAudioCtx = null; }
        if (_recStream) { _recStream.getTracks().forEach(t => t.stop()); _recStream = null; }
    }

    function stopRecording() {
        if (!isRecording) return;

        if (_matchFound) {
            cleanupRecording();
            return;
        }

        // No match found yet — do one final attempt with all audio
        cleanupRecording();
        recordStatus.textContent = 'Processing...';

        if (audioChunks.length === 0) {
            recordBtn.parentElement.classList.remove('hidden');
            recordStatus.textContent = 'Tap to Identify';
            return;
        }

        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
            ? 'audio/webm;codecs=opus'
            : 'audio/webm';
        const audioBlob = new Blob(audioChunks, { type: mimeType });
        const audioFile = new File([audioBlob], "recording.webm", { type: mimeType });
        identifyFile(audioFile);
    }

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
                refreshSpectrogramLayout();
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

    function populateMatchResults(data) {
        matchSongName.textContent = data.song;
        document.getElementById('match-score').textContent = data.score.toLocaleString();
        matchConfidence.textContent = data.match_density.toFixed(1) + '%';
        document.getElementById('match-dominance').textContent = data.dominance >= 999 ? 'INF' : data.dominance.toFixed(1) + 'x';
        matchOffset.textContent = data.offset.toFixed(1) + 's';
        document.getElementById('match-query-fps').textContent = data.query_fingerprints.toLocaleString();
        document.getElementById('match-db-hits').textContent = data.db_hits.toLocaleString();
    }

    async function identifyFile(file) {
        if (!file) return;

        // UI State
        recordBtn.parentElement.classList.add('hidden');
        identifyResults.classList.add('hidden');
        noMatchView.classList.add('hidden');
        loaderContainer.classList.remove('hidden');

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/identify', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('Identification failed');

            const data = await response.json();
            loaderContainer.classList.add('hidden');

            if (data.match) {
                populateMatchResults(data);
                identifyResults.classList.remove('hidden');
            } else {
                noMatchView.classList.remove('hidden');
            }
            recordStatus.textContent = 'Tap to Identify';

        } catch (error) {
            console.error('Identify Error:', error);
            alert('Error identifying audio.');
            loaderContainer.classList.add('hidden');
            recordBtn.parentElement.classList.remove('hidden');
            recordStatus.textContent = 'Tap to Identify';
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
        const w = img.clientWidth;
        const h = img.clientHeight;
        hashOverlay.setAttribute('width', w);
        hashOverlay.setAttribute('height', h);
        hashOverlay.setAttribute('viewBox', `0 0 ${w} ${h}`);
    }

    function getAnchorGroup(hashRow) {
        return lastHashes
            .filter(row =>
                row.anchor_time_frame === hashRow.anchor_time_frame &&
                row.anchor_freq_bin === hashRow.anchor_freq_bin
            )
            .sort((a, b) => a.id - b.id)
            .slice(0, 5);
    }

    function drawHashOverlay(hashRow, numFrames, numFreqBins) {
        syncOverlaySize();
        const img = interactiveSpectrogram;
        const w = img.clientWidth;
        const h = img.clientHeight;
        const svgNS = 'http://www.w3.org/2000/svg';

        clearHashOverlay();

        const x1 = normalizeX(hashRow.anchor_time_frame, numFrames, w);
        const y1 = normalizeY(hashRow.anchor_freq_bin, numFreqBins, h);
        const relatedPairs = getAnchorGroup(hashRow);

        relatedPairs.forEach(pair => {
            const x2 = normalizeX(pair.target_time_frame, numFrames, w);
            const y2 = normalizeY(pair.target_freq_bin, numFreqBins, h);
            const isSelected = pair.id === hashRow.id;

            const line = document.createElementNS(svgNS, 'line');
            line.setAttribute('x1', x1);
            line.setAttribute('y1', y1);
            line.setAttribute('x2', x2);
            line.setAttribute('y2', y2);
            line.setAttribute('class', `hash-line-item${isSelected ? ' is-selected' : ''}`);
            hashOverlay.appendChild(line);

            const target = document.createElementNS(svgNS, 'circle');
            target.setAttribute('cx', x2);
            target.setAttribute('cy', y2);
            target.setAttribute('r', isSelected ? '3' : '2');
            target.setAttribute('class', `hash-target-item${isSelected ? ' is-selected' : ''}`);
            hashOverlay.appendChild(target);
        });

        const anchor = document.createElementNS(svgNS, 'circle');
        anchor.setAttribute('cx', x1);
        anchor.setAttribute('cy', y1);
        anchor.setAttribute('r', '3.5');
        anchor.setAttribute('class', 'hash-anchor-item');
        hashOverlay.appendChild(anchor);

        selectedHashDetails.textContent =
            `${hashRow.hash_hex} | anchor ${hashRow.anchor_time_s.toFixed(3)}s @ ${hashRow.anchor_freq_hz.toFixed(1)}Hz -> target ${hashRow.target_time_s.toFixed(3)}s @ ${hashRow.target_freq_hz.toFixed(1)}Hz (Δt=${hashRow.delta_time_frames} frames) | showing ${relatedPairs.length} pair(s) for this source anchor`;
    }

    function clearHashOverlay() {
        hashOverlay.innerHTML = '';
    }

    function normalizeX(frameIdx, numFrames, width) {
        if (numFrames <= 1) return 0;
        return (frameIdx / (numFrames - 1)) * width;
    }

    function normalizeY(freqBin, numFreqBins, height) {
        if (numFreqBins <= 1) return height;
        return (1 - (freqBin / (numFreqBins - 1))) * height;
    }

    function refreshSpectrogramLayout() {
        if (!interactiveSpectrogram.src) return;
        syncOverlaySize();
        renderFreqAxis();
        renderTimeAxis();

        if (selectedHashId !== null && lastHashes.length) {
            const selected = lastHashes.find(row => row.id === selectedHashId);
            if (selected) {
                drawHashOverlay(selected, trackMeta.numFrames || 1, trackMeta.numFreqBins || 1);
            }
        }
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
        const numTicks = Math.max(1, Math.min(20, Math.floor(dur)));
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

    resultImage.classList.add('can-fullscreen');
    resultImage.addEventListener('click', () => {
        if (getFullscreenElement() !== resultImage) {
            toggleResultImageFullscreen();
        }
    });

    spectrogramWrap.classList.add('can-fullscreen');
    interactiveSpectrogram.addEventListener('click', () => {
        if (getFullscreenElement() !== spectrogramWrap) {
            toggleSpectrogramFullscreen();
        }
    });
    document.addEventListener('fullscreenchange', updateFullscreenState);
    document.addEventListener('webkitfullscreenchange', updateFullscreenState);

    // Re-sync overlay when window resizes
    window.addEventListener('resize', () => {
        refreshSpectrogramLayout();
    });

    // Reset workflow
    resetBtn.addEventListener('click', () => {
        resetAnalyze();
    });

    [resetIdBtn, resetNoMatchBtn].forEach(btn => {
        btn.addEventListener('click', () => {
            resetIdentify();
        });
    });

    function resetAnalyze() {
        if (getFullscreenElement()) {
            exitFullscreen();
        }
        resultImage.src = '';
        interactiveSpectrogram.src = '';
        fileInput.value = '';
        hashList.innerHTML = '';
        selectedHashDetails.textContent = 'Select a hash to locate it on the spectrogram.';
        lastHashes = [];
        selectedHashId = null;
        clearHashOverlay();
        resultsSection.classList.add('hidden');
        dropZone.classList.remove('hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function resetIdentify() {
        identifyResults.classList.add('hidden');
        noMatchView.classList.add('hidden');
        recordBtn.parentElement.classList.remove('hidden');
        recordStatus.textContent = 'Tap to Identify';
        fileInput.value = '';
    }

    // --- Library Fetching & Rendering ---
    async function fetchLibrary() {
        try {
            const response = await fetch('/api/library');
            if (!response.ok) throw new Error('Failed to fetch library');
            
            const data = await response.json();
            libraryData = data.songs;
            
            // Update Stats
            libStatSongs.textContent = data.stats.total_songs;
            libStatHashes.textContent = data.stats.total_fingerprints.toLocaleString();
            libStatSize.textContent = data.stats.db_size_mb + ' MB';
            
            renderLibrary(libraryData);
        } catch (err) {
            console.error('Library Load Error:', err);
            libraryTbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--fg-dim);">Failed to load library data.</td></tr>';
        }
    }

    function renderLibrary(songs) {
        libraryTbody.innerHTML = '';

        songs.forEach(song => {
            const tr = document.createElement('tr');
            tr.style.cursor = 'pointer';

            tr.innerHTML = `
                <td>${song.id}</td>
                <td>
                    ${song.name}
                    <span class="song-path">${song.path}</span>
                </td>
                <td>${song.duration.toFixed(2)}s</td>
                <td>${song.fingerprints.toLocaleString()}</td>
            `;

            tr.addEventListener('click', () => analyzeByPath(song.path));

            libraryTbody.appendChild(tr);
        });

        if (songs.length === 0) {
            libraryTbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--fg-dim);">No songs found.</td></tr>';
        }
    }

    async function analyzeByPath(filepath) {
        // Switch to analyze mode
        currentMode = 'analyze';
        setActiveMode(modeAnalyze);
        analyzeSection.classList.remove('hidden');
        identifySection.classList.add('hidden');
        librarySection.classList.add('hidden');

        // Show loader
        dropZone.classList.add('hidden');
        resultsSection.classList.add('hidden');
        loaderContainer.classList.remove('hidden');

        try {
            const response = await fetch('/api/process-path', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: filepath })
            });

            if (!response.ok) throw new Error(`Server returned status: ${response.status}`);

            const data = await response.json();

            resultImage.src = data.image;

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

            interactiveSpectrogram.onload = () => {
                refreshSpectrogramLayout();
            };
            interactiveSpectrogram.src = data.spectrogram_image;

            loaderContainer.classList.add('hidden');
            resultsSection.classList.remove('hidden');
            resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

        } catch (error) {
            console.error('Error processing track:', error);
            alert('Failed to process the track.');
            loaderContainer.classList.add('hidden');
            dropZone.classList.remove('hidden');
        }
    }

    // Search Filtering
    librarySearch.addEventListener('input', (e) => {
        const term = e.target.value.toLowerCase();
        const filtered = libraryData.filter(s => 
            s.name.toLowerCase().includes(term) || 
            s.path.toLowerCase().includes(term)
        );
        renderLibrary(filtered);
    });
});
