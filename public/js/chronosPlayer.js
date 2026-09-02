/**
 * Chronos Interactive Canvas Player.
 * Synchronizes video playback with dialogue by dynamically holding/freezing
 * the visual frame on the canvas when audio discussion expands beyond
 * native video duration, resuming in exact lockstep.
 */

export class ChronosPlayer {
    constructor(canvasEl, videoEl, audioEl, onTimeUpdate, onFreezeChange) {
        this.canvas = canvasEl;
        this.ctx = canvasEl.getContext('2d');
        this.video = videoEl;
        this.audio = audioEl;
        this.onTimeUpdate = onTimeUpdate;
        this.onFreezeChange = onFreezeChange;

        this.schedule = null;
        this.isPlaying = false;
        this.animationFrameId = null;
        this.isFrozen = false;
        this.totalDurationMs = 0;

        this._initEvents();
    }

    setSchedule(schedule) {
        this.schedule = schedule;
        this.totalDurationMs = schedule.total_output_duration_ms || 0;
    }

    _initEvents() {
        this.audio.addEventListener('ended', () => {
            this.pause();
            if (this.onTimeUpdate) this.onTimeUpdate(this.totalDurationMs, this.totalDurationMs);
        });
    }

    async play() {
        if (!this.schedule) return;
        this.isPlaying = true;
        try {
            await this.audio.play();
            this._renderLoop();
        } catch (e) {
            console.error("Audio play blocked:", e);
        }
    }

    pause() {
        this.isPlaying = false;
        this.audio.pause();
        this.video.pause();
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }
    }

    togglePlay() {
        if (this.isPlaying) this.pause();
        else this.play();
    }

    seek(timeMs) {
        const timeSec = timeMs / 1000.0;
        this.audio.currentTime = Math.min(this.audio.duration || 0, timeSec);
        this._syncFrameAtTime(timeMs);
        if (this.onTimeUpdate) this.onTimeUpdate(timeMs, this.totalDurationMs);
    }

    _renderLoop() {
        if (!this.isPlaying) return;

        const currentMasterMs = (this.audio.currentTime * 1000.0);
        this._syncFrameAtTime(currentMasterMs);

        if (this.onTimeUpdate) {
            this.onTimeUpdate(currentMasterMs, this.totalDurationMs);
        }

        this.animationFrameId = requestAnimationFrame(() => this._renderLoop());
    }

    _syncFrameAtTime(masterTimeMs) {
        if (!this.schedule || !this.schedule.aligned_timeline) {
            this._drawDirect();
            return;
        }

        const segments = this.schedule.aligned_timeline;
        let activeSegment = null;

        for (const seg of segments) {
            if (masterTimeMs >= seg.playhead_start_ms && masterTimeMs < seg.playhead_end_ms) {
                activeSegment = seg;
                break;
            }
        }

        if (!activeSegment) {
            activeSegment = segments[segments.length - 1];
        }

        if (!activeSegment) {
            this._drawDirect();
            return;
        }

        const elapsedInSegmentMs = masterTimeMs - activeSegment.playhead_start_ms;
        const freezeDurationMs = activeSegment.freeze_duration_ms || 0;
        const nativeDurMs = activeSegment.video_duration_ms || 1000;

        let targetVideoMs = activeSegment.video_start_ms;
        let currentlyFrozen = false;

        if (freezeDurationMs > 0) {
            const freezeAnchorOffsetMs = activeSegment.freeze_anchor_video_ms - activeSegment.video_start_ms;

            if (elapsedInSegmentMs < freezeAnchorOffsetMs) {
                // Before freeze anchor: video plays at 1.0x
                targetVideoMs = activeSegment.video_start_ms + elapsedInSegmentMs;
                currentlyFrozen = false;
            } else if (elapsedInSegmentMs <= freezeAnchorOffsetMs + freezeDurationMs) {
                // In freeze zone: video stays locked at the focal action point
                targetVideoMs = activeSegment.freeze_anchor_video_ms;
                currentlyFrozen = true;
            } else {
                // After freeze: resume video to end of scene
                const resumedElapsed = elapsedInSegmentMs - freezeDurationMs;
                targetVideoMs = activeSegment.video_start_ms + Math.min(nativeDurMs, resumedElapsed);
                currentlyFrozen = false;
            }
        } else {
            // Normal 1:1 playback
            targetVideoMs = activeSegment.video_start_ms + Math.min(nativeDurMs, elapsedInSegmentMs);
            currentlyFrozen = false;
        }

        if (this.isFrozen !== currentlyFrozen) {
            this.isFrozen = currentlyFrozen;
            if (this.onFreezeChange) this.onFreezeChange(currentlyFrozen);
        }

        // Align video element time
        const targetVideoSec = targetVideoMs / 1000.0;
        if (Math.abs(this.video.currentTime - targetVideoSec) > 0.08) {
            this.video.currentTime = targetVideoSec;
        }

        this._drawDirect();
    }

    _drawDirect() {
        if (!this.canvas || !this.video) return;
        if (this.video.videoWidth && (this.canvas.width !== this.video.videoWidth || this.canvas.height !== this.video.videoHeight)) {
            this.canvas.width = this.video.videoWidth;
            this.canvas.height = this.video.videoHeight;
        }

        try {
            this.ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);
        } catch (e) {
            // Canvas draw error guard
        }
    }
}
