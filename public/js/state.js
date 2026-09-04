/**
 * CastOps AI Studio - Reactive State Store
 */

class StudioStateStore {
    constructor() {
        this.state = {
            apiKey: localStorage.getItem('castops_api_key') || '',
            activeStep: 1,
            videoFile: null,
            videoUrl: null,
            videoDurationSec: 0,
            videoDimensions: { width: 1280, height: 720 },
            readmeFile: null,
            readmeText: '',
            scenes: [],
            dialogue: [],
            qaAudit: null,
            voiceAlex: 'Puck',
            voiceSam: 'Kore',
            audioUrl: null,
            chronosSchedule: null,
            compiledVideoUrl: null,
            isProcessing: false,
            processingMessage: '',
            clickhouseEvents: [],
            clickhouseMetrics: null,
            autopilotMode: false
        };
        this.listeners = [];
    }

    getState() {
        return this.state;
    }

    setState(partial) {
        this.state = { ...this.state, ...partial };
        if (partial.apiKey !== undefined) {
            localStorage.setItem('castops_api_key', partial.apiKey);
        }
        this.notify();
    }

    subscribe(listener) {
        this.listeners.push(listener);
        return () => {
            this.listeners = this.listeners.filter(l => l !== listener);
        };
    }

    notify() {
        for (const listener of this.listeners) {
            try {
                listener(this.state);
            } catch (e) {
                console.error("State listener error:", e);
            }
        }
    }
}

export const store = new StudioStateStore();
