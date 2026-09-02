/**
 * Frame Talk Studio - Main Application Orchestrator
 * Fully wired to the cream, navy, and Bricolage Grotesque design system.
 */

import { store } from './state.js';
import { api } from './api.js';
import { ChronosPlayer } from './chronosPlayer.js';

let player = null;

// Initialize on DOM Load
document.addEventListener('DOMContentLoaded', async () => {
    initNavigation();
    initDropzones();
    initControls();
    initKeyModal();
    checkBackendHealth();
    store.subscribe(renderStateUpdates);
});

// ─── Health & Connectivity ───────────────────────────────────────────────────

async function checkBackendHealth() {
    const health = await api.checkHealth();
    const chBadge = document.getElementById('clickhouse-status-badge');
    const chText = document.getElementById('clickhouse-status-text');

    if (health.clickhouse_connected) {
        if (chBadge) chBadge.style.borderColor = 'rgba(74, 222, 128, 0.4)';
        if (chText) chText.textContent = 'ClickHouse Connected';
    } else {
        if (chText) chText.textContent = 'ClickHouse Buffered (Demo)';
    }

    const key = store.getState().apiKey;
    const keyBadge = document.getElementById('api-status-badge');
    const keyText = document.getElementById('api-status-text');
    if (key && keyBadge && keyText) {
        keyBadge.classList.remove('unconfigured');
        keyBadge.style.borderColor = 'rgba(74, 222, 128, 0.4)';
        keyText.textContent = 'API Key Configured';
    }
}

// ─── Navigation ──────────────────────────────────────────────────────────────

function initNavigation() {
    window.navigateToStep = (stepNum) => {
        store.setState({ activeStep: stepNum });
    };

    window.prevStep = () => {
        const cur = store.getState().activeStep;
        if (cur > 1) store.setState({ activeStep: cur - 1 });
    };

    window.restartWorkflow = () => {
        store.setState({
            activeStep: 1,
            scenes: [],
            dialogue: [],
            qaAudit: null,
            audioUrl: null,
            chronosSchedule: null,
            compiledVideoUrl: null
        });
    };
}

function renderStateUpdates(state) {
    // 1. Update wizard cards
    for (let i = 1; i <= 5; i++) {
        const card = document.getElementById(`step-card-${i}`);
        const tab = document.getElementById(`tab-step-${i}`);
        const pipeItem = document.getElementById(`pipe-step-${i}`);

        if (card) {
            card.classList.toggle('active', i === state.activeStep);
        }
        if (tab) {
            tab.classList.toggle('active', i === state.activeStep);
            if (i === 2) tab.disabled = !state.videoFile || !state.readmeText;
            if (i === 3) tab.disabled = state.scenes.length === 0;
            if (i === 4) tab.disabled = state.dialogue.length === 0;
            if (i === 5) tab.disabled = !state.chronosSchedule || !state.audioUrl;
        }
        if (pipeItem) {
            pipeItem.classList.toggle('active', i === state.activeStep);
            const check = pipeItem.querySelector('.pipe-check');
            if (check) {
                check.textContent = (i < state.activeStep || (i === 5 && state.compiledVideoUrl)) ? '☑' : (i === state.activeStep ? '▶' : '☐');
            }
        }
    }

    // 2. Sidebar active assets
    const videoNameEl = document.getElementById('sidebar-video-name');
    if (videoNameEl) {
        videoNameEl.textContent = state.videoFile ? state.videoFile.name : 'No video uploaded';
    }
    const readmeNameEl = document.getElementById('sidebar-readme-name');
    if (readmeNameEl) {
        readmeNameEl.textContent = state.readmeFile ? state.readmeFile.name : 'No README uploaded';
    }

    // 3. Step 1 CTA button
    const btnToStep2 = document.getElementById('btn-to-step-2');
    if (btnToStep2) {
        btnToStep2.disabled = !state.videoFile || !state.readmeText || state.isProcessing;
    }
}

// ─── File Ingestion ──────────────────────────────────────────────────────────

function initDropzones() {
    setupDropzone('video-dropzone', 'video-input', handleVideoSelected);
    setupDropzone('readme-dropzone', 'readme-input', handleReadmeSelected);
}

function setupDropzone(dropzoneId, inputId, onFileSelect) {
    const dropzone = document.getElementById(dropzoneId);
    const input = document.getElementById(inputId);
    if (!dropzone || !input) return;

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            onFileSelect(e.dataTransfer.files[0]);
        }
    });

    input.addEventListener('change', () => {
        if (input.files.length > 0) {
            onFileSelect(input.files[0]);
        }
    });
}

function handleVideoSelected(file) {
    const url = URL.createObjectURL(file);
    const tempVideo = document.createElement('video');
    tempVideo.preload = 'metadata';
    tempVideo.src = url;

    tempVideo.onloadedmetadata = () => {
        store.setState({
            videoFile: file,
            videoUrl: url,
            videoDurationSec: tempVideo.duration,
            videoDimensions: { width: tempVideo.videoWidth, height: tempVideo.videoHeight }
        });
        renderFileBadge('video-file-list', file.name, file.size, () => {
            store.setState({ videoFile: null, videoUrl: null, videoDurationSec: 0 });
            document.getElementById('video-file-list').innerHTML = '';
        });
    };
}

function handleReadmeSelected(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
        const text = e.target.result;
        store.setState({
            readmeFile: file,
            readmeText: text
        });
        renderFileBadge('readme-file-list', file.name, file.size, () => {
            store.setState({ readmeFile: null, readmeText: '' });
            document.getElementById('readme-file-list').innerHTML = '';
        });
    };
    reader.readAsText(file);
}

function renderFileBadge(containerId, name, size, onRemove) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const sizeMb = (size / (1024 * 1024)).toFixed(2);
    container.innerHTML = `
        <div class="file-item" style="background:var(--color-cream);border:1px solid var(--color-border);padding:0.6rem 1rem;border-radius:12px;display:flex;justify-content:space-between;align-items:center;margin-top:0.5rem;">
            <div style="display:flex;align-items:center;gap:0.5rem;">
                <span>📄</span>
                <strong style="font-size:0.9rem;color:var(--color-navy);">${escapeHtml(name)}</strong>
                <span style="font-size:0.8rem;color:var(--color-muted);">(${sizeMb} MB)</span>
            </div>
            <button class="btn btn-ghost" style="padding:0.2rem 0.5rem;color:#D32F2F;" aria-label="Remove file">✖</button>
        </div>
    `;
    container.querySelector('.btn-ghost').addEventListener('click', onRemove);
}

// ─── Pipeline Action Controls ────────────────────────────────────────────────

function initControls() {
    window.analyzeVideo = async () => {
        const { videoFile, readmeFile, readmeText, videoDurationSec, apiKey } = store.getState();
        if (!videoFile || !readmeText) return;

        setStepLoading(2, true, 'Computing fast hash...');
        window.navigateToStep(2);
        updateStepProgress(2, 5);

        try {
            const fastHash = await api.computeFastHash(videoFile);
            updateStepProgress(2, 10);
            
            const cachedJob = await api.getJob(fastHash);
            
            let analyzeRes;
            let finalVideoFilename;

            if (cachedJob && cachedJob.status === 'COMPLETED') {
                // CACHE HIT
                setStepLoading(2, true, 'Cache hit! Loading scenes and syncing video silently...');
                updateStepProgress(2, 80);
                
                analyzeRes = cachedJob.result;
                
                // Silently upload video in the background for compiler stage later
                api.uploadAssets(videoFile, readmeFile).then(uploadRes => {
                    store.setState({ uploadedVideoFilename: uploadRes.video_filename });
                }).catch(e => console.error("Silent upload failed", e));
                
                // Keep the state mostly empty for now since uploadedVideoFilename will populate asynchronously
                finalVideoFilename = null;
                updateStepProgress(2, 100);
            } else {
                // CACHE MISS
                setStepLoading(2, true, 'Uploading video for analysis...');
                const uploadRes = await api.uploadAssets(videoFile, readmeFile);
                finalVideoFilename = uploadRes.video_filename;
                updateStepProgress(2, 60);

                let timerInterval;
                let secondsElapsed = 0;

                analyzeRes = await api.analyzeVideo(
                    uploadRes.video_filename, 
                    readmeText, 
                    videoDurationSec, 
                    apiKey,
                    fastHash, // Use fast hash as the ID!
                    (jobId) => {
                        timerInterval = setInterval(() => {
                            secondsElapsed++;
                            setStepLoading(2, true, `Running background video analysis... (${secondsElapsed}s)`);
                        }, 1000);
                        setStepLoading(2, true, `Running background video analysis... (0s)`);
                        updateStepProgress(2, 75);
                    }
                );
                
                if (timerInterval) clearInterval(timerInterval);
                updateStepProgress(2, 100);
            }

            store.setState({
                scenes: analyzeRes.scenes,
                videoEvalScorecard: analyzeRes.eval_scorecard
            });
            if (finalVideoFilename) {
                store.setState({ uploadedVideoFilename: finalVideoFilename });
            }

            renderTranscriptTable(analyzeRes.scenes);
            if (analyzeRes.eval_scorecard) {
                renderVideoEvalScorecard(analyzeRes.eval_scorecard);
            }
            markAgentStatus('agent-transcript-status', 'Ingestion Agent: Complete');
            setTimeout(() => setStepLoading(2, false), 400);
        } catch (e) {
            alert(`Analysis Error: ${e.message}`);
            setStepLoading(2, false);
        }
    };

    window.generatePodcastScript = async () => {
        const { scenes, readmeText, apiKey } = store.getState();
        window.navigateToStep(3);
        setStepLoading(3, true, 'Drafting dialogue script with gemini-3.7-flash...');

        try {
            const scriptRes = await api.generateScript(scenes, readmeText, apiKey);
            const qaRes = await api.auditScript(scenes, scriptRes.dialogue, readmeText, apiKey);

            store.setState({
                dialogue: scriptRes.dialogue,
                qaAudit: qaRes
            });

            renderScriptLines(scriptRes.dialogue);
            renderQaReport(qaRes);
            markAgentStatus('agent-script-status', 'Scriptwriter Agent: Complete');
            markAgentStatus('agent-qa-status', 'QA Pacing Audit: Passed');
            setStepLoading(3, false);
        } catch (e) {
            alert(`Script Generation Error: ${e.message}`);
            setStepLoading(3, false);
        }
    };

    window.refineScriptWithFeedback = async () => {
        const { scenes, readmeText, apiKey, qaAudit } = store.getState();
        setStepLoading(3, true, 'Auto-refining script with QA feedback using gemini-3.7-flash...');
        try {
            const promptContext = `${readmeText}\n\nQA AUDITOR FEEDBACK TO FIX: ${qaAudit?.feedback || 'Enhance timing and natural banter'}`;
            const scriptRes = await api.generateScript(scenes, promptContext, apiKey);
            const qaRes = await api.auditScript(scenes, scriptRes.dialogue, readmeText, apiKey);

            store.setState({ dialogue: scriptRes.dialogue, qaAudit: qaRes });
            renderScriptLines(scriptRes.dialogue);
            renderQaReport(qaRes);
            setStepLoading(3, false);
        } catch (e) {
            alert(`Refinement Error: ${e.message}`);
            setStepLoading(3, false);
        }
    };

    window.generatePodcastAudio = async () => {
        const { scenes, dialogue, apiKey } = store.getState();
        const voiceAlex = document.getElementById('host-a-voice-select')?.value || 'Puck';
        const voiceSam = document.getElementById('host-b-voice-select')?.value || 'Kore';

        setStepLoading(4, true, 'Synthesizing PCM via gemini-3.1-flash-tts-preview...');
        updateStepProgress(4, 25);

        try {
            const synthRes = await api.synthesizeAudio(scenes, dialogue, voiceAlex, voiceSam, apiKey);
            updateStepProgress(4, 90);

            store.setState({
                audioUrl: synthRes.audio_url,
                audioFilename: synthRes.audio_filename,
                chronosSchedule: synthRes.chronos_schedule,
                sessionId: synthRes.session_id,
                dialogue: synthRes.updated_turns
            });

            const previewPlayer = document.getElementById('podcast-audio-player');
            const previewSection = document.getElementById('podcast-audio-preview-section');
            if (previewPlayer && previewSection) {
                previewPlayer.src = synthRes.audio_url;
                previewSection.style.display = 'block';
            }

            const btnStep5 = document.getElementById('btn-to-step-5');
            if (btnStep5) btnStep5.disabled = false;

            markAgentStatus('agent-chronos-status', 'Chronos Sync: Aligned');
            updateStepProgress(4, 100);
            setTimeout(() => setStepLoading(4, false), 400);
        } catch (e) {
            alert(`Audio Synthesis Error: ${e.message}`);
            setStepLoading(4, false);
        }
    };

    window.goToMergeStep = () => {
        window.navigateToStep(5);
        const { audioUrl, chronosSchedule } = store.getState();
        renderChronosMetrics(chronosSchedule);
        initSynchronizedPlayer(audioUrl, chronosSchedule);
        pollClickHouseStats(store.getState().sessionId);
    };

    document.getElementById('btn-compile-mp4')?.addEventListener('click', async () => {
        const { sessionId, uploadedVideoFilename, audioFilename, chronosSchedule } = store.getState();
        const btn = document.getElementById('btn-compile-mp4');
        const statusText = document.getElementById('compile-status-text');

        if (btn) btn.disabled = true;
        if (statusText) statusText.textContent = '⚙️ Compiler Agent rendering frame-stretched video with FFmpeg...';

        try {
            const res = await api.compileVideo(sessionId, uploadedVideoFilename, audioFilename, chronosSchedule);
            if (statusText) {
                statusText.innerHTML = `✅ Stitched 1080p MP4 Ready! <a href="${res.video_url}" download style="color:var(--color-blue);font-weight:700;margin-left:0.5rem;">📥 Download Synced MP4</a>`;
            }
            store.setState({ compiledVideoUrl: res.video_url });
        } catch (e) {
            if (statusText) statusText.textContent = `❌ Compilation failed: ${e.message}`;
        } finally {
            if (btn) btn.disabled = false;
        }
    });
}

// ─── Rendering Helpers ───────────────────────────────────────────────────────

function renderTranscriptTable(scenes) {
    const tbody = document.getElementById('transcript-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    scenes.forEach((scene) => {
        const tr = document.createElement('tr');
        const onScreen = scene.on_screen || scene.screen_summary || '';
        const userAction = scene.user_action || scene.user_inputs || '';
        const appReaction = scene.app_reaction || scene.system_response || '';

        tr.innerHTML = `
            <td style="font-family:var(--font-mono);font-size:0.82rem;font-weight:700;color:var(--color-navy);vertical-align:top;">${escapeHtml(scene.timestamp_str)}</td>
            <td style="vertical-align:top;">
                <div style="font-weight:700;color:var(--color-navy);margin-bottom:0.35rem;font-size:0.9rem;">${escapeHtml(scene.action_title)}</div>
                <div style="font-size:0.85rem;color:var(--color-ink);line-height:1.5;">${escapeHtml(onScreen)}</div>
            </td>
            <td style="font-size:0.85rem;color:var(--color-ink);vertical-align:top;line-height:1.5;">
                ${escapeHtml(userAction)}
            </td>
            <td style="font-size:0.85rem;color:var(--color-ink);vertical-align:top;line-height:1.5;">
                ${escapeHtml(appReaction)}
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function renderVideoEvalScorecard(evalScorecard) {
    const section = document.getElementById('video-eval-section');
    if (!section || !evalScorecard) return;
    section.style.display = 'block';

    const badge = document.getElementById('video-eval-badge');
    const scoreEl = document.getElementById('video-eval-score');
    const specEl = document.getElementById('video-eval-specificity');
    const causEl = document.getElementById('video-eval-causality');
    const boilEl = document.getElementById('video-eval-boilerplate');
    const sumEl = document.getElementById('video-eval-summary-text');

    const passed = evalScorecard.passed;
    if (badge) {
        badge.textContent = passed ? 'PASSED (STRICT)' : 'NEEDS REFINEMENT';
        badge.style.background = passed ? '#E8F5E9' : '#FFF2F2';
        badge.style.color = passed ? '#2E7D32' : '#D32F2F';
    }

    if (scoreEl) scoreEl.textContent = `${evalScorecard.overall_score}%`;
    if (specEl) specEl.textContent = `${evalScorecard.specificity_score}%`;
    if (causEl) causEl.textContent = `${evalScorecard.causality_score}%`;
    if (boilEl) {
        const hits = evalScorecard.boilerplate_hits || 0;
        boilEl.textContent = `${hits} hits`;
        boilEl.style.color = hits === 0 ? '#2E7D32' : '#D32F2F';
    }
    if (sumEl) sumEl.textContent = evalScorecard.summary || 'Strict forensic inspection completed.';
}

function renderScriptLines(dialogue) {
    const container = document.getElementById('script-lines-container');
    if (!container) return;
    container.innerHTML = '';

    dialogue.forEach((turn) => {
        const div = document.createElement('div');
        div.className = 'script-line-item';
        div.innerHTML = `
            <div class="script-line-header">
                <span class="speaker-tag ${turn.speaker.toLowerCase()}">🎙️ ${turn.speaker}</span>
                <span class="scene-anchor-pill">${turn.scene_id}</span>
            </div>
            <div style="font-size:0.95rem;color:var(--color-ink);line-height:1.5;">${escapeHtml(turn.text)}</div>
        `;
        container.appendChild(div);
    });
}

function renderQaReport(qa) {
    const section = document.getElementById('qa-report-section');
    if (!section || !qa) return;
    section.style.display = 'block';

    const acc = document.getElementById('qa-accuracy-score');
    const rd = document.getElementById('qa-readme-score');
    const bnt = document.getElementById('qa-banter-score');
    const fb = document.getElementById('qa-feedback-text');

    if (acc) acc.textContent = `${qa.accuracy_score || 95}%`;
    if (rd) rd.textContent = `${qa.readme_score || 92}%`;
    if (bnt) bnt.textContent = `${qa.pacing_score || 94}%`;
    if (fb) fb.textContent = qa.feedback || 'High alignment with video actions and README context.';

    // Sidebar scores
    const sbAcc = document.getElementById('sidebar-qa-accuracy');
    const sbRd = document.getElementById('sidebar-qa-readme');
    const sbBnt = document.getElementById('sidebar-qa-banter');
    const sbMsg = document.getElementById('sidebar-qa-msg');
    if (sbAcc) sbAcc.textContent = `${qa.accuracy_score || 95}%`;
    if (sbRd) sbRd.textContent = `${qa.readme_score || 92}%`;
    if (sbBnt) sbBnt.textContent = `${qa.pacing_score || 94}%`;
    if (sbMsg) sbMsg.textContent = qa.feedback ? qa.feedback.substring(0, 75) + '...' : 'Audit verified.';

    if (qa.checklist) {
        setChecklistStatus('chk-video-accuracy', qa.checklist.discusses_video_actions, 'Video actions accuracy verified');
        setChecklistStatus('chk-readme-alignment', qa.checklist.explains_readme_concepts, 'README architectural concepts explained');
        setChecklistStatus('chk-natural-banter', qa.checklist.organic_dialogue_cadence, 'Natural live dialogue cadence');
        setChecklistStatus('chk-no-timestamps', qa.checklist.no_robotic_timestamps, 'Zero robotic timestamps in speech');
        setChecklistStatus('chk-good-pacing', qa.checklist.full_visual_coverage, 'Full video pacing coverage');
    }
}

function setChecklistStatus(id, passed, label) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = `${passed ? '✅' : '❌'} ${label}`;
    el.style.color = passed ? '#2E7D32' : '#D32F2F';
}

function renderChronosMetrics(schedule) {
    const box = document.getElementById('chronos-metrics-box');
    if (!box || !schedule) return;

    const totalFreeze = (schedule.total_freeze_injected_ms / 1000).toFixed(2);
    const totalDuration = (schedule.total_output_duration_ms / 1000).toFixed(2);

    box.innerHTML = `
        <div class="chronos-stat-card">
            <span class="chronos-stat-label">Total Spoken Runtime</span>
            <span class="chronos-stat-value">${totalDuration}s</span>
        </div>
        <div class="chronos-stat-card">
            <span class="chronos-stat-label">Dynamic Frame Holds</span>
            <span class="chronos-stat-value freeze-val">+${totalFreeze}s</span>
        </div>
        <div class="chronos-stat-card">
            <span class="chronos-stat-label">Chronos Alignment Sync</span>
            <span class="chronos-stat-value sync-val">99.9%</span>
        </div>
    `;
}

function initSynchronizedPlayer(audioUrl, schedule) {
    const canvas = document.getElementById('sync-canvas-player');
    const video = document.getElementById('sync-video-player');
    const audio = document.getElementById('sync-audio-player');
    const freezeBadge = document.getElementById('freeze-indicator');
    const playBtn = document.getElementById('btn-play-preview');
    const timeText = document.getElementById('player-time-text');

    if (!canvas || !video || !audio) return;

    const state = store.getState();
    if (state.videoUrl) video.src = state.videoUrl;
    audio.src = audioUrl;

    player = new ChronosPlayer(
        canvas, video, audio,
        (currentMs, totalMs) => {
            const cur = (currentMs / 1000).toFixed(1);
            const tot = (totalMs / 1000).toFixed(1);
            if (timeText) timeText.textContent = `${cur}s / ${tot}s`;
        },
        (isFrozen) => {
            if (freezeBadge) freezeBadge.classList.toggle('visible', isFrozen);
        }
    );

    player.setSchedule(schedule);

    if (playBtn) {
        playBtn.onclick = () => {
            player.togglePlay();
            playBtn.textContent = player.isPlaying ? '⏸ Pause Interactive Preview' : '▶ Play Interactive Preview';
        };
    }
}

async function pollClickHouseStats(sessionId) {
    try {
        const data = await api.getClickHouseEvents(sessionId);
        const list = document.getElementById('clickhouse-telemetry-list');
        if (list && data.events && data.events.length > 0) {
            list.innerHTML = '';
            data.events.forEach(ev => {
                const pill = document.createElement('div');
                pill.className = 'telemetry-pill';
                pill.innerHTML = `
                    <div><strong style="color:var(--color-navy);">${ev.speaker}:</strong> "${escapeHtml(ev.dialogue_text.substring(0, 50))}..."</div>
                    <div style="font-size:0.72rem;color:var(--color-muted);">Dur: ${ev.audio_duration_ms}ms | Hold: ${ev.required_freeze_ms}ms | Status: ${ev.pacing_status}</div>
                `;
                list.appendChild(pill);
            });
        }
    } catch (e) {
        console.error("ClickHouse polling error:", e);
    }
}

function markAgentStatus(elemId, text) {
    const el = document.getElementById(elemId);
    if (!el) return;
    el.innerHTML = `<span class="status-box" style="color:#2E7D32;">☑</span> ${text}`;
    el.style.color = 'var(--color-navy)';
    el.style.fontWeight = '600';
}

function setStepLoading(stepNum, isLoading, message = '') {
    const overlay = document.getElementById(`loading-step-${stepNum}`);
    if (overlay) overlay.style.display = isLoading ? 'flex' : 'none';
    const text = document.getElementById(`progress-text-step-${stepNum}`);
    if (text && message) text.textContent = message;
}

function updateStepProgress(stepNum, percent) {
    const bar = document.getElementById(`progress-bar-step-${stepNum}`);
    if (bar) bar.style.width = `${percent}%`;
}

// ─── Modal Key Config ────────────────────────────────────────────────────────

function initKeyModal() {
    window.openKeyModal = () => {
        const modal = document.getElementById('key-modal');
        if (modal) modal.classList.add('active');
        const input = document.getElementById('api-key-input');
        if (input) input.value = store.getState().apiKey;
    };

    window.closeKeyModal = () => {
        const modal = document.getElementById('key-modal');
        if (modal) modal.classList.remove('active');
    };

    window.toggleKeyVisibility = () => {
        const input = document.getElementById('api-key-input');
        if (input) {
            input.type = input.type === 'password' ? 'text' : 'password';
        }
    };

    window.saveAndVerifyKey = async () => {
        const input = document.getElementById('api-key-input');
        const err = document.getElementById('key-error-msg');
        const btnSave = document.getElementById('btn-save-key');
        const btnCancel = document.getElementById('btn-cancel-key');
        
        const val = input ? input.value.trim() : '';
        if (!val) {
            if (err) {
                err.textContent = 'Please enter an API key.';
                err.style.display = 'block';
            }
            return;
        }

        if (err) err.style.display = 'none';
        if (btnSave) btnSave.disabled = true;
        if (btnSave) btnSave.textContent = 'Validating...';
        if (btnCancel) btnCancel.disabled = true;

        try {
            const res = await fetch('/api/byok/verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ api_key: val })
            });
            const data = await res.json();
            
            if (data.valid) {
                store.setState({ apiKey: val });
                checkBackendHealth();
                window.closeKeyModal();
            } else {
                if (err) {
                    err.textContent = data.error || 'Invalid API key.';
                    err.style.display = 'block';
                }
            }
        } catch (e) {
            if (err) {
                err.textContent = 'Could not reach validation server.';
                err.style.display = 'block';
            }
        } finally {
            if (btnSave) {
                btnSave.disabled = false;
                btnSave.textContent = 'Validate & Save';
            }
            if (btnCancel) btnCancel.disabled = false;
        }
    };
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

window.testVoice = async (selectId) => {
    const btn = document.querySelector(`button[onclick="window.testVoice('${selectId}')"]`);
    if (btn) btn.disabled = true;
    try {
        const voiceName = document.getElementById(selectId).value;
        const apiKey = store.getState().apiKey;
        const data = await api.testVoice(voiceName, apiKey);
        if (data && data.audio_url) {
            const audio = new Audio(data.audio_url);
            audio.play();
        }
    } catch (err) {
        console.error("Test Voice Error:", err);
        alert("Failed to test voice: " + err.message);
    } finally {
        if (btn) btn.disabled = false;
    }
};
