/**
 * Anonymous Client Identity Manager (IndexedDB + localStorage Fallback)
 * Generates and securely persists an anonymous CSPRNG client token
 * with zero server login requirements.
 */

const DB_NAME = 'FrameTalkDB';
const DB_VERSION = 1;
const STORE_NAME = 'user_meta';
const USER_KEY = 'frametalk_user_id';

let cachedUserId = null;

/**
 * Initializes or accesses the IndexedDB database.
 */
function openIndexedDB() {
    return new Promise((resolve, reject) => {
        if (!window.indexedDB) {
            return reject(new Error('IndexedDB not supported'));
        }
        const request = window.indexedDB.open(DB_NAME, DB_VERSION);
        request.onupgradeneeded = (e) => {
            const db = e.target.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME);
            }
        };
        request.onsuccess = (e) => resolve(e.target.result);
        request.onerror = (e) => reject(e.target.error);
    });
}

/**
 * Retrieves the anonymous user_id from IndexedDB.
 */
async function getIdFromIndexedDB() {
    try {
        const db = await openIndexedDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(STORE_NAME, 'readonly');
            const store = tx.objectStore(STORE_NAME);
            const req = store.get(USER_KEY);
            req.onsuccess = () => resolve(req.result || null);
            req.onerror = () => reject(req.error);
        });
    } catch (e) {
        console.warn('IndexedDB read failed, trying localStorage fallback:', e);
        return null;
    }
}

/**
 * Persists the anonymous user_id to IndexedDB.
 */
async function saveIdToIndexedDB(id) {
    try {
        const db = await openIndexedDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(STORE_NAME, 'readwrite');
            const store = tx.objectStore(STORE_NAME);
            const req = store.put(id, USER_KEY);
            req.onsuccess = () => resolve(true);
            req.onerror = () => reject(req.error);
        });
    } catch (e) {
        console.warn('IndexedDB write failed:', e);
        return false;
    }
}

/**
 * Generates a cryptographically secure random UUIDv4 token.
 */
function generateSecureUserId() {
    if (window.crypto && window.crypto.randomUUID) {
        return 'usr_' + window.crypto.randomUUID();
    }
    // Fallback CSPRNG
    const array = new Uint8Array(16);
    (window.crypto || window.msCrypto).getRandomValues(array);
    const hex = Array.from(array, b => b.toString(16).padStart(2, '0')).join('');
    return 'usr_' + hex;
}

/**
 * Retrieves the persistent anonymous user_id.
 * Checks memory cache -> IndexedDB -> localStorage -> generates new if absent.
 */
async function getUserId() {
    if (cachedUserId) {
        return cachedUserId;
    }

    // 1. Try IndexedDB
    let id = await getIdFromIndexedDB();

    // 2. Try localStorage fallback
    if (!id && window.localStorage) {
        try {
            id = window.localStorage.getItem(USER_KEY);
        } catch (e) {
            // private browsing mode restrictions
        }
    }

    // 3. Obtain cryptographically signed session token from server if missing or unsigned
    if (!id || !id.includes('.')) {
        try {
            const resp = await fetch('/api/auth/session');
            if (resp.ok) {
                const sessionData = await resp.json();
                if (sessionData.user_id) {
                    id = sessionData.user_id;
                }
            }
        } catch (e) {
            // fallback in offline environments
        }
        if (!id) {
            id = generateSecureUserId();
        }
        await saveIdToIndexedDB(id);
        if (window.localStorage) {
            try {
                window.localStorage.setItem(USER_KEY, id);
            } catch (e) {}
        }
    } else {
        // Ensure synchronized across both stores
        if (window.localStorage && !window.localStorage.getItem(USER_KEY)) {
            try { window.localStorage.setItem(USER_KEY, id); } catch (e) {}
        }
    }

    cachedUserId = id;
    return cachedUserId;
}

// Attach globally
window.getUserId = getUserId;
