/**
 * CastOps AI Studio - API Client
 * Bridges the browser studio with the FastAPI Python multi-agent backend.
 */

const API_BASE = window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')
    ? ''
    : '';

function getHeaders(apiKey) {
    const headers = { 'Content-Type': 'application/json' };
    if (apiKey && typeof apiKey === 'string' && apiKey.trim()) {
        headers['X-API-Key'] = apiKey.trim();
    }
    return headers;
}

async function computeFastHash(file) {
    const CHUNK_SIZE = 1024 * 1024; // 1MB
    const slice = file.slice(0, CHUNK_SIZE);
    const buffer = await slice.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    return `${hashHex}_${file.size}`;
}

export const api = {
    computeFastHash,

    async getJob(jobId) {
        const res = await fetch(`${API_BASE}/api/jobs/${jobId}`);
        if (!res.ok) {
            if (res.status === 404) return null;
            throw new Error(`Failed to fetch job: ${await res.text()}`);
        }
        return await res.json();
    },

    async checkHealth() {
        try {
            const res = await fetch(`${API_BASE}/api/health`);
            return await res.json();
        } catch (e) {
            return { status: 'offline', clickhouse_connected: false };
        }
    },

    async uploadAssets(videoFile, readmeFile) {
        const formData = new FormData();
        if (videoFile) formData.append('video', videoFile);
        if (readmeFile) formData.append('readme', readmeFile);

        const res = await fetch(`${API_BASE}/api/upload`, {
            method: 'POST',
            body: formData
        });
        if (!res.ok) throw new Error(`Upload failed: ${await res.text()}`);
        return await res.json();
    },

    async analyzeVideo(videoFilename, readmeText, videoDurationSeconds, apiKey, videoHash, onProgress) {
        // Step 1: Submit job
        const res = await fetch(`${API_BASE}/api/analyze-video`, {
            method: 'POST',
            headers: getHeaders(apiKey),
            body: JSON.stringify({
                video_filename: videoFilename,
                readme_text: readmeText,
                video_duration_seconds: videoDurationSeconds,
                video_hash: videoHash
            })
        });
        if (!res.ok) throw new Error(`Analysis submission failed: ${await res.text()}`);
        const resData = await res.json();
        const { job_id, status: initialStatus } = resData;
        
        if (onProgress) onProgress(job_id);

        if (initialStatus === 'COMPLETED' || initialStatus === 'FAILED') {
            const pollRes = await fetch(`${API_BASE}/api/jobs/${job_id}`);
            if (!pollRes.ok) throw new Error(`Fetch failed: ${await pollRes.text()}`);
            const job = await pollRes.json();
            if (job.status === 'COMPLETED') return job.result;
            if (job.status === 'FAILED') throw new Error(`Analysis job failed: ${job.error}`);
        }

        // Step 2: Poll for completion
        while (true) {
            await new Promise(resolve => setTimeout(resolve, 2000)); // Poll every 2 seconds
            
            const pollRes = await fetch(`${API_BASE}/api/jobs/${job_id}`);
            if (!pollRes.ok) throw new Error(`Polling failed: ${await pollRes.text()}`);
            
            const job = await pollRes.json();
            if (job.status === 'COMPLETED') {
                return job.result;
            } else if (job.status === 'FAILED') {
                throw new Error(`Analysis job failed: ${job.error}`);
            }
            // If PENDING or PROCESSING, continue loop
        }
    },

    async generateScript(scenes, readmeText, apiKey) {
        const res = await fetch(`${API_BASE}/api/generate-script`, {
            method: 'POST',
            headers: getHeaders(apiKey),
            body: JSON.stringify({
                scenes,
                readme_text: readmeText
            })
        });
        if (!res.ok) throw new Error(`Script generation failed: ${await res.text()}`);
        return await res.json();
    },

    async auditScript(scenes, dialogue, readmeText, apiKey) {
        const res = await fetch(`${API_BASE}/api/audit-script`, {
            method: 'POST',
            headers: getHeaders(apiKey),
            body: JSON.stringify({
                scenes,
                dialogue,
                readme_text: readmeText
            })
        });
        if (!res.ok) throw new Error(`QA audit failed: ${await res.text()}`);
        return await res.json();
    },

    async synthesizeAudio(scenes, dialogue, voiceAlex, voiceSam, apiKey) {
        const res = await fetch(`${API_BASE}/api/synthesize-audio`, {
            method: 'POST',
            headers: getHeaders(apiKey),
            body: JSON.stringify({
                scenes,
                dialogue,
                voice_alex: voiceAlex,
                voice_sam: voiceSam
            })
        });
        if (!res.ok) throw new Error(`Synthesis failed: ${await res.text()}`);
        return await res.json();
    },

    async testVoice(voiceName, apiKey) {
        const res = await fetch(`${API_BASE}/api/test-voice`, {
            method: 'POST',
            headers: getHeaders(apiKey),
            body: JSON.stringify({
                voice_name: voiceName,
                text: "Hi, I'm your selected voice. How do I sound?"
            })
        });
        if (!res.ok) throw new Error(`Voice test failed: ${await res.text()}`);
        return await res.json();
    },

    async compileVideo(sessionId, videoFilename, audioFilename, chronosSchedule) {
        const res = await fetch(`${API_BASE}/api/compile-video`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                video_filename: videoFilename,
                audio_filename: audioFilename,
                chronos_schedule: chronosSchedule
            })
        });
        if (!res.ok) throw new Error(`Video compilation failed: ${await res.text()}`);
        return await res.json();
    },

    async getClickHouseEvents(sessionId) {
        const url = sessionId 
            ? `${API_BASE}/api/clickhouse/events?session_id=${encodeURIComponent(sessionId)}`
            : `${API_BASE}/api/clickhouse/events`;
        const res = await fetch(url);
        if (!res.ok) return { events: [], metrics: {} };
        return await res.json();
    }
};
