/**
 * Frame Talk Accessible Toast Notification System
 * WCAG 2.1 AA compliant non-blocking toasts with ARIA live regions and keyboard controls.
 */

class ToastManager {
    constructor() {
        this.container = null;
    }

    _ensureContainer() {
        if (!this.container || !document.body.contains(this.container)) {
            let existing = document.getElementById('toast-container');
            if (existing) {
                this.container = existing;
            } else {
                this.container = document.createElement('div');
                this.container.id = 'toast-container';
                this.container.setAttribute('aria-label', 'System notifications');
                document.body.appendChild(this.container);
            }
        }
        return this.container;
    }

    show(message, type = 'info', title = null, durationMs = 6000) {
        const container = this._ensureContainer();

        const toast = document.createElement('div');
        toast.className = `toast-item toast-${type}`;
        
        // WCAG Accessibility: Assertive for errors, Polite for info/success
        const isError = type === 'error';
        toast.setAttribute('role', isError ? 'alert' : 'status');
        toast.setAttribute('aria-live', isError ? 'assertive' : 'polite');
        toast.setAttribute('aria-atomic', 'true');

        let icon = 'ℹ️';
        if (type === 'success') icon = '✅';
        else if (type === 'error') icon = '⚠️';
        else if (type === 'warning') icon = '🔔';

        const displayTitle = title || (
            type === 'success' ? 'Success' :
            type === 'error' ? 'Attention Needed' :
            type === 'warning' ? 'Notice' : 'Information'
        );

        toast.innerHTML = `
            <span class="toast-icon" aria-hidden="true">${icon}</span>
            <div class="toast-content">
                <div class="toast-title">${displayTitle}</div>
                <div class="toast-msg">${this._escapeHtml(message)}</div>
            </div>
            <button class="toast-close" type="button" aria-label="Dismiss notification">&times;</button>
        `;

        const closeBtn = toast.querySelector('.toast-close');
        closeBtn.addEventListener('click', () => {
            this._dismiss(toast);
        });

        container.appendChild(toast);

        if (durationMs > 0) {
            setTimeout(() => {
                this._dismiss(toast);
            }, durationMs);
        }

        return toast;
    }

    _dismiss(toast) {
        if (!toast || !toast.parentNode) return;
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(12px) scale(0.95)';
        setTimeout(() => {
            if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 300);
    }

    _escapeHtml(str) {
        if (typeof str !== 'string') return String(str);
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    success(message, title = 'Success') {
        return this.show(message, 'success', title, 4500);
    }

    error(message, title = 'Error') {
        return this.show(message, 'error', title, 8000);
    }

    warning(message, title = 'Warning') {
        return this.show(message, 'warning', title, 6000);
    }

    info(message, title = 'Notice') {
        return this.show(message, 'info', title, 5000);
    }
}

export const toast = new ToastManager();
window.toast = toast;
