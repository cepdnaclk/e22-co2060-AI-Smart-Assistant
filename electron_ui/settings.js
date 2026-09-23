// Settings panel: open/close, section navigation, backend sync and toast.
// Section pages register themselves with settingsUI.registerPage() (later steps).
(() => {
    const panel = document.getElementById('settings-panel');
    const title = document.getElementById('settings-title');
    const backBtn = document.getElementById('settings-back-btn');
    const closeBtn = document.getElementById('settings-close-btn');
    const toast = document.getElementById('settings-toast');
    const views = panel.querySelectorAll('.settings-view');
    const CACHE_KEY = 'sentinel.settings';

    // Replies from the backend that belong to the settings panel
    const REPLY_ACTIONS = new Set([
        'settings', 'settings_saved', 'settings_error',
        'models', 'connection_result', 'learned_solutions_deleted',
    ]);

    const state = { settings: null, profile: null };
    const pages = {};        // name -> { render(state), onMessage(data) }
    let currentView = 'list';
    let toastTimer = null;
    let returnFocusTo = null;

    // -------------------------- Cache --------------------------
    // Last known settings, so the UI can apply them before the WebSocket connects
    try {
        const cached = JSON.parse(localStorage.getItem(CACHE_KEY));
        if (cached && cached.settings) Object.assign(state, cached);
    } catch (e) { /* storage unavailable or corrupt: wait for backend */ }

    function cacheState() {
        try {
            localStorage.setItem(CACHE_KEY, JSON.stringify(state));
        } catch (e) { /* ignore */ }
    }

    // -------------------------- Navigation --------------------------
    function showView(name) {
        currentView = name;
        views.forEach((view) => view.classList.toggle('active', view.dataset.view === name));
        const active = panel.querySelector(`.settings-view[data-view="${name}"]`);
        title.textContent = name === 'list' ? 'Settings' : active.dataset.title;
        backBtn.classList.toggle('hidden', name === 'list');
        active.scrollTop = 0;
        if (name !== 'list' && pages[name] && state.settings) pages[name].render(state);
    }

    function open() {
        returnFocusTo = document.activeElement;
        showView('list');
        panel.classList.add('open');
        panel.setAttribute('aria-hidden', 'false');
        sendAction('get_settings');
        setTimeout(() => panel.querySelector('.settings-row').focus(), 50);
    }

    function close() {
        panel.classList.remove('open');
        panel.setAttribute('aria-hidden', 'true');
        if (returnFocusTo && returnFocusTo.focus) returnFocusTo.focus();
    }

    function back() {
        if (currentView === 'list') {
            close();
        } else {
            const previous = currentView;
            showView('list');
            const row = panel.querySelector(`.settings-row[data-open="${previous}"]`);
            if (row) row.focus();
        }
    }

    panel.querySelectorAll('.settings-row').forEach((row) => {
        row.addEventListener('click', () => showView(row.dataset.open));
    });
    backBtn.addEventListener('click', back);
    closeBtn.addEventListener('click', close);

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && panel.classList.contains('open')) {
            e.preventDefault();
            back();
        }
    });

    // -------------------------- Toast --------------------------
    function showToast(message, type = 'success') {
        toast.textContent = message;
        toast.className = `settings-toast show ${type}`;
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => { toast.className = 'settings-toast'; }, type === 'error' ? 3500 : 1600);
    }

    // -------------------------- Backend sync --------------------------
    function save(section, values) {
        if (!sendAction('save_settings', { section, values })) {
            showToast('Not connected. Try again in a moment.', 'error');
            return false;
        }
        return true;
    }

    function saveProfile(values) {
        if (!sendAction('save_profile', { values })) {
            showToast('Not connected. Try again in a moment.', 'error');
            return false;
        }
        return true;
    }

    function handleMessage(data) {
        if (data.action === 'settings' || data.action === 'settings_saved') {
            state.settings = data.settings;
            state.profile = data.profile;
            cacheState();
            Object.values(pages).forEach((page) => page.onSettings && page.onSettings(state));
            if (currentView !== 'list' && pages[currentView]) pages[currentView].render(state);
            if (data.action === 'settings_saved') showToast('✓ Saved');
        } else if (data.action === 'settings_error') {
            const messages = Object.entries(data.errors || {}).map(([field, msg]) => `${field}: ${msg}`);
            showToast(messages.join('\n') || 'Could not save', 'error');
            if (pages[currentView] && pages[currentView].onErrors) pages[currentView].onErrors(data.errors);
            // Re-render so fields snap back to the last saved values
            if (pages[currentView] && state.settings) pages[currentView].render(state);
        }
        Object.values(pages).forEach((page) => page.onMessage && page.onMessage(data));
    }

    // -------------------------- Public API --------------------------
    window.settingsUI = {
        open,
        close,
        handles: (action) => REPLY_ACTIONS.has(action),
        handleMessage,
        registerPage: (name, page) => {
            pages[name] = page;
            if (state.settings && page.onSettings) page.onSettings(state);
        },
        save,
        saveProfile,
        showToast,
        state,
    };
})();
