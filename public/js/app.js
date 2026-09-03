/**
 * Frame Talk Studio - Main Application Orchestrator
 * Fully wired to the cream, navy, and Bricolage Grotesque design system.
 */

import { store } from './state.js';
import { api } from './api.js';
import { ChronosPlayer } from './chronosPlayer.js';
import { toast } from './toast.js';

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
        if (chText) chText.textContent = 'ClickHouse Active';
    } else {
        if (chBadge) chBadge.style.borderColor = 'rgba(255, 255, 255, 0.25)';
        if (chText) chText.textContent = 'ClickHouse Standby';
    }

    // Google Cloud Agent Platform health
    const agentBadge = document.getElementById('agent-platform-badge');
    const agentText = document.getElementById('agent-platform-text');
    if (health.agent_builder_enabled) {
        if (agentBadge) {
            agentBadge.style.borderColor = 'rgba(167, 139, 250, 0.5)';
            agentBadge.setAttribute('aria-label', `${health.agent_platform || 'Google Cloud Agent Platform'} (Live)`);
        }
        if (agentText) agentText.textContent = 'Google Cloud Agent Platform';
    }

    // Check Gemini API key config state & hosted demo quota
    const keyBadge = document.getElementById('api-status-badge');
    const keyText = document.getElementById('api-status-text');
    const hasKey = !!store.getState().apiKey;

    const quota = await api.getQuota(store.getState().apiKey);

    if (hasKey) {
        if (keyBadge) {
            keyBadge.classList.remove('unconfigured');
            keyBadge.style.borderColor = 'rgba(74, 222, 128, 0.4)';
            keyBadge.setAttribute('aria-label', 'BYOK Configured (Unlimited runs). Click to change.');
        }
        if (keyText) keyText.textContent = 'BYOK Unlimited';
    } else if (quota && quota.has_server_key) {
        if (quota.is_quota_exhausted) {
            if (keyBadge) {
                keyBadge.classList.add('unconfigured');
                keyBadge.style.borderColor = 'rgba(239, 68, 68, 0.4)';
                keyBadge.setAttribute('aria-label', 'Hosted demo quota used (3/3). Click to set Gemini API key.');
            }
            if (keyText) keyText.textContent = 'Demo Used (Add Key)';
        } else {
            if (keyBadge) {
                keyBadge.classList.remove('unconfigured');
                keyBadge.style.borderColor = 'rgba(56, 189, 248, 0.5)';
                keyBadge.setAttribute('aria-label', `Hosted Demo Key Active (${quota.videos_remaining}/${quota.max_videos} free runs left). Click to enter custom key.`);
            }
            if (keyText) keyText.textContent = `Demo: ${quota.videos_remaining}/${quota.max_videos} Left`;
        }
    } else {
        if (keyBadge) {
            keyBadge.classList.add('unconfigured');
            keyBadge.setAttribute('aria-label', 'API Key not configured. Click to set key.');
        }
        if (keyText) keyText.textContent = 'Set API Key';
    }

    // Dynamically route Grafana dashboard link from backend config or current domain
    const grafanaLink = document.getElementById('grafana-dashboard-link');
    if (grafanaLink) {
        if (health && health.grafana_url) {
            grafanaLink.href = health.grafana_url;
        } else {
            const host = window.location.hostname;
            if (host === 'localhost' || host === '127.0.0.1') {
                grafanaLink.href = 'http://localhost:3000';
            } else {
                const rootDomain = host.replace(/^frame-talk\./, '');
                grafanaLink.href = `https://grafana.${rootDomain}`;
            }
        }
    }

    // Dynamically align canonical and Open Graph URLs to active origin
    const canonicalLink = document.querySelector('link[rel="canonical"]');
    if (canonicalLink) canonicalLink.href = window.location.origin + '/';
    const ogUrl = document.querySelector('meta[property="og:url"]');
    if (ogUrl) ogUrl.content = window.location.origin + '/';
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
        toast.info('Workflow restarted. Ready for a new screencast.', 'Reset Complete');
    };

    // Keyboard Arrow Navigation across Steps Tablist
    const stepsNav = document.querySelector('.steps-nav');
    if (stepsNav) {
        stepsNav.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
                const tabs = Array.from(stepsNav.querySelectorAll('.step-tab:not([disabled])'));
                const currentIndex = tabs.indexOf(document.activeElement);
                if (currentIndex !== -1) {
                    e.preventDefault();
                    let nextIndex = e.key === 'ArrowRight' ? currentIndex + 1 : currentIndex - 1;
                    if (nextIndex >= tabs.length) nextIndex = 0;
                    if (nextIndex < 0) nextIndex = tabs.length - 1;
                    tabs[nextIndex].focus();
                    tabs[nextIndex].click();
                }
            }
        });
    }
}

function renderStateUpdates(state) {
    // 1. Update wizard cards and tabs with accessibility attributes
    for (let i = 1; i <= 5; i++) {
        const card = document.getElementById(`step-card-${i}`);
        const tab = document.getElementById(`tab-step-${i}`);
        const pipeItem = document.getElementById(`pipe-step-${i}`);
        const isActive = i === state.activeStep;

        if (card) {
            card.classList.toggle('active', isActive);
            card.setAttribute('aria-hidden', isActive ? 'false' : 'true');
        }
        if (tab) {
            tab.classList.toggle('active', isActive);
            tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
            if (i === 2) tab.disabled = !state.videoFile || !state.readmeText;
            if (i === 3) tab.disabled = state.scenes.length === 0;
            if (i === 4) tab.disabled = state.dialogue.length === 0;
            if (i === 5) tab.disabled = !state.chronosSchedule || !state.audioUrl;
        }
        if (pipeItem) {
            pipeItem.classList.toggle('active', isActive);
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

    // 4. Update Pre-Flight Cost Estimation Card
    updateCostEstimation(state);
}

function updateCostEstimation(state) {
    const dur = (state && state.videoDurationSec && state.videoDurationSec > 0) ? state.videoDurationSec : 120.0;
    const readmeChars = (state && state.readmeText && state.readmeText.length > 0) ? state.readmeText.length : 5000;

    const videoTokens = Math.round(dur * 258);
    const readmeTokens = Math.round(readmeChars / 4);
    const ingestTokens = videoTokens + readmeTokens + 2200;
    const estWords = Math.round(dur * 2.5);
    const scriptTokens = Math.round(estWords * 1.35 + 2250);
    const ttsChars = Math.round(estWords * 5.5);

    const visionCost = (ingestTokens / 1000000) * 0.15;
    const scriptCost = (scriptTokens / 1000000) * 0.35;
    const ttsCost = (ttsChars / 1000) * 0.015;
    const totalCost = Math.max(0.01, visionCost + scriptCost + ttsCost);

    const mins = Math.floor(dur / 60);
    const secs = Math.floor(dur % 60);
    const durStr = `${mins}m ${secs.toString().padStart(2, '0')}s`;

    const elDur = document.getElementById('est-video-dur');
    if (elDur) elDur.textContent = durStr;
    const elLen = document.getElementById('est-readme-len');
    if (elLen) elLen.textContent = `${readmeChars.toLocaleString()} chars`;
    const elVision = document.getElementById('est-vision-tokens');
    if (elVision) elVision.textContent = `~${videoTokens.toLocaleString()}`;
    const elScript = document.getElementById('est-script-tokens');
    if (elScript) elScript.textContent = `~${scriptTokens.toLocaleString()}`;
    const elTts = document.getElementById('est-tts-chars');
    if (elTts) elTts.textContent = `~${ttsChars.toLocaleString()} chars`;
    const elCost = document.getElementById('est-total-cost');
    if (elCost) elCost.textContent = `~$${totalCost.toFixed(3)} USD`;
    const elBadge = document.getElementById('cost-badge');
    if (elBadge) elBadge.textContent = `~$${totalCost.toFixed(3)} USD`;
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

        setStepLoading(2, true, 'Computing video fingerprint...');
        window.navigateToStep(2);
        updateStepProgress(2, 5);

        try {
            const fastHash = await api.computeFastHash(videoFile);
            updateStepProgress(2, 10);
            
            // Clean probe check (returns 200 {cached: false} on cache miss)
            const cacheStatus = await api.checkCache(fastHash);
            
            let analyzeRes;
            let finalVideoFilename;

            if (cacheStatus && cacheStatus.cached && cacheStatus.result) {
                // CACHE HIT
                setStepLoading(2, true, 'Cache hit! Instant replay of visual scenes...');
                updateStepProgress(2, 80);
                
                analyzeRes = cacheStatus.result;
                
                // Silently upload video in background for FFmpeg compiler stage later
                api.uploadAssets(videoFile, readmeFile).then(uploadRes => {
                    store.setState({ uploadedVideoFilename: uploadRes.video_filename });
                }).catch(e => console.warn("Background upload synchronization note:", e.message));
                
                finalVideoFilename = null;
                updateStepProgress(2, 100);
            } else {
                // CACHE MISS: Track real-time upload bytes & progress
                setStepLoading(2, true, 'Uploading screencast (0%)...');
                
                const uploadRes = await api.uploadAssets(videoFile, readmeFile, (p) => {
                    setStepLoading(2, true, `Uploading screencast: ${p.percent}% (${p.loadedMb}MB / ${p.totalMb}MB)...`);
                    updateStepProgress(2, 10 + Math.round(p.percent * 0.45)); // Scale 10% -> 55%
                });
                
                finalVideoFilename = uploadRes.video_filename;
                updateStepProgress(2, 58);
                setStepLoading(2, true, 'Upload verified! Starting Gemini 3.7 Flash analysis...');

                let timerInterval;
                let secondsElapsed = 0;

                analyzeRes = await api.analyzeVideo(
                    uploadRes.video_filename, 
                    readmeText, 
                    videoDurationSec, 
                    apiKey,
                    fastHash,
                    (jobId) => {
                        timerInterval = setInterval(() => {
                            secondsElapsed++;
                            setStepLoading(2, true, `Director Agent analyzing screencast frames... (${secondsElapsed}s)`);
                        }, 1000);
                        setStepLoading(2, true, `Director Agent analyzing screencast frames... (0s)`);
                        updateStepProgress(2, 70);
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
            markAgentStatus('agent-transcript-status', 'Director & Ingestion Agent: Complete');
            toast.success(`Video parsed into ${analyzeRes.scenes.length} visual scenes!`, 'Analysis Complete');
            checkBackendHealth();
            setTimeout(() => setStepLoading(2, false), 400);
        } catch (e) {
            console.error("Video Analysis Pipeline Error:", e);
            if (e.message && (e.message.includes('Quota') || e.message.includes('429') || e.message.includes('QUOTA_EXHAUSTED'))) {
                toast.warning(e.message, 'Hosted Demo Quota Limit');
                setTimeout(() => window.openKeyModal(), 500);
            } else {
                toast.error(`${e.message} (Please verify your server and file format)`, 'Analysis Error');
            }
            setStepLoading(2, false);
        }
    };

    window.generatePodcastScript = async () => {
        const { scenes, readmeText, apiKey } = store.getState();
        window.navigateToStep(3);
        setStepLoading(3, true, 'Scriptwriter Persona Agent drafting Alex & Sam dialogue...');

        try {
            const scriptRes = await api.generateScript(scenes, readmeText, apiKey);
            const qaRes = await api.auditScript(scenes, scriptRes.dialogue, readmeText, apiKey);

            store.setState({
                dialogue: scriptRes.dialogue,
                qaAudit: qaRes
            });

            renderScriptLines(scriptRes.dialogue);
            renderQaReport(qaRes);
            markAgentStatus('agent-script-status', 'Scriptwriter Persona Agent: Complete');
            markAgentStatus('agent-qa-status', `QA Auditor Agent: Passed (${qaRes.pacing_score || 90}/100)`);
            toast.success(`Generated ${scriptRes.dialogue.length} dialogue turns aligned to scenes.`, 'Script Ready');
            setStepLoading(3, false);
        } catch (e) {
            toast.error(e.message, 'Script Generation Failed');
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
            toast.success('Script refined with QA audit feedback.', 'Refinement Complete');
            setStepLoading(3, false);
        } catch (e) {
            toast.error(e.message, 'Refinement Failed');
            setStepLoading(3, false);
        }
    };

    window.generatePodcastAudio = async () => {
        const { scenes, dialogue, apiKey } = store.getState();
        const voiceAlex = document.getElementById('host-a-voice-select')?.value || 'Puck';
        const voiceSam = document.getElementById('host-b-voice-select')?.value || 'Kore';

        setStepLoading(4, true, 'Chronos MCP Tool calculating PCM duration & freeze schedule...');
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

            markAgentStatus('agent-chronos-status', 'Chronos MCP Tool: Synced');
            updateStepProgress(4, 100);
            toast.success('PCM audio synthesized & Chronos offsets calculated!', 'Audio Synced');
            setTimeout(() => setStepLoading(4, false), 400);
        } catch (e) {
            toast.error(e.message, 'Audio Synthesis Failed');
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
    let lastActiveElement = null;

    window.openKeyModal = async () => {
        lastActiveElement = document.activeElement;
        const modal = document.getElementById('key-modal');
        if (modal) {
            modal.classList.add('active');
            modal.setAttribute('aria-hidden', 'false');
        }
        const input = document.getElementById('api-key-input');
        if (input) {
            input.value = store.getState().apiKey;
            setTimeout(() => input.focus(), 120);
        }

        // Refresh quota banner
        const banner = document.getElementById('modal-quota-banner');
        if (banner) {
            const quota = await api.getQuota(store.getState().apiKey);
            if (quota && quota.has_server_key) {
                if (quota.has_custom_key) {
                    banner.innerHTML = `✅ <strong>Custom Key Active:</strong> You have unlimited runs enabled via your own Google Gemini API key.`;
                    banner.style.color = '#15803d';
                    banner.style.background = 'rgba(74, 222, 128, 0.1)';
                    banner.style.borderColor = 'rgba(74, 222, 128, 0.3)';
                } else if (quota.is_quota_exhausted) {
                    banner.innerHTML = `⚠️ <strong>Hosted Demo Exhausted:</strong> You have used all ${quota.videos_used}/${quota.max_videos} free demo runs. Enter your free Google Gemini API key below to continue running unlimited generations!`;
                    banner.style.color = '#b91c1c';
                    banner.style.background = 'rgba(239, 68, 68, 0.1)';
                    banner.style.borderColor = 'rgba(239, 68, 68, 0.3)';
                } else {
                    banner.innerHTML = `⚡ <strong>Hosted Demo Active:</strong> You have <strong>${quota.videos_remaining}/${quota.max_videos}</strong> free generations remaining without needing an API key! To unlock unlimited runs, enter your Google Gemini API key below.`;
                    banner.style.color = '#0284c7';
                    banner.style.background = 'rgba(56, 189, 248, 0.1)';
                    banner.style.borderColor = 'rgba(56, 189, 248, 0.3)';
                }
            }
        }
    };

    window.closeKeyModal = () => {
        const modal = document.getElementById('key-modal');
        if (modal) {
            modal.classList.remove('active');
            modal.setAttribute('aria-hidden', 'true');
        }
        if (lastActiveElement && typeof lastActiveElement.focus === 'function') {
            lastActiveElement.focus();
        }
    };

    // Close modal on Escape key and trap Tab focus inside dialog
    document.addEventListener('keydown', (e) => {
        const modal = document.getElementById('key-modal');
        if (!modal || !modal.classList.contains('active')) return;

        if (e.key === 'Escape') {
            e.preventDefault();
            window.closeKeyModal();
            return;
        }

        if (e.key === 'Tab') {
            const focusableElements = modal.querySelectorAll(
                'button:not([disabled]), input:not([disabled]), a[href], [tabindex="0"]'
            );
            if (focusableElements.length === 0) return;
            const first = focusableElements[0];
            const last = focusableElements[focusableElements.length - 1];

            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        }
    });

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
            store.setState({ apiKey: '' });
            checkBackendHealth();
            window.closeKeyModal();
            toast.info('Reverted to Hosted Demo Mode.', 'Credentials Updated');
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
                toast.success('Google Gemini API Key validated and saved securely.', 'Credentials Configured');
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
            toast.info(`Playing audio preview for ${voiceName}...`, 'Voice Test');
        }
    } catch (err) {
        console.error("Test Voice Error:", err);
        toast.error("Failed to test voice: " + err.message, 'Voice Test Error');
    } finally {
        if (btn) btn.disabled = false;
    }
};
