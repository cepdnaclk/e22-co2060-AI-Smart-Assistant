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

    const FONT_SIZES = { small: '12px', medium: '13px', large: '15px' };
    const SLIDER_SAVE_DELAY = 300;

    const state = { settings: null, profile: null };
    const pages = {};        // name -> { render(state), onMessage(data) }
    let currentView = 'list';
    let toastTimer = null;
    let returnFocusTo = null;
    const saveTimers = {};

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

    // -------------------------- Apply UI settings --------------------------
    const systemLight = window.matchMedia('(prefers-color-scheme: light)');

    function applyUiSettings(general) {
        if (!general) return;
        const root = document.documentElement;
        const theme = general.theme === 'system' ? (systemLight.matches ? 'light' : 'dark') : general.theme;
        root.dataset.theme = theme;
        root.style.setProperty('--chat-font-size', FONT_SIZES[general.font_size] || FONT_SIZES.medium);
        root.style.setProperty('--window-alpha', general.window_opacity);
        ipcRenderer.send('set-always-on-top', general.always_on_top);
    }

    systemLight.addEventListener('change', () => {
        if (state.settings) applyUiSettings(state.settings.general);
    });

    // -------------------------- Generic controls --------------------------
    // Any element with data-setting="section.key" is bound to that setting.
    function getSetting(path) {
        const [section, key] = path.split('.');
        return state.settings && state.settings[section] ? state.settings[section][key] : undefined;
    }

    function formatValue(value, format) {
        return format === 'percent' ? `${Math.round(value * 100)}%` : String(value);
    }

    function setControlValue(control, value) {
        if (control.classList.contains('segmented')) {
            control.querySelectorAll('button').forEach((btn) => {
                const selected = btn.dataset.value === String(value);
                btn.classList.toggle('selected', selected);
                btn.setAttribute('aria-checked', selected);
            });
        } else if (control.classList.contains('switch')) {
            control.setAttribute('aria-checked', value === true);
        } else if (control.type === 'range') {
            const invert = Number(control.dataset.invert);
            control.value = invert ? invert - value : value;
            updateSliderFill(control);
        }
        panel.querySelectorAll(`[data-value-for="${control.dataset.setting}"]`).forEach((label) => {
            label.textContent = formatValue(value, label.dataset.format);
        });
    }

    function readSliderValue(control) {
        const invert = Number(control.dataset.invert);
        const value = Number(control.value);
        return invert ? invert - value : value;
    }

    function updateSliderFill(control) {
        const min = Number(control.min), max = Number(control.max);
        const percent = ((Number(control.value) - min) / (max - min)) * 100;
        control.style.setProperty('--fill', `${percent}%`);
    }

    function updateDependencies(root) {
        root.querySelectorAll('[data-depends]').forEach((item) => {
            const enabled = getSetting(item.dataset.depends) === true;
            item.classList.toggle('disabled', !enabled);
            item.querySelectorAll('input, button, select, textarea').forEach((el) => { el.disabled = !enabled; });
        });
    }

    function renderControls(root) {
        if (!state.settings) return;
        root.querySelectorAll('[data-setting]').forEach((control) => {
            const value = getSetting(control.dataset.setting);
            if (value !== undefined) setControlValue(control, value);
        });
        updateDependencies(root);
    }

    // Update local state immediately (instant preview), then save to the backend
    function changeSetting(path, value, delay = 0) {
        const [section, key] = path.split('.');
        if (!state.settings) return;
        state.settings[section][key] = value;
        if (section === 'general') applyUiSettings(state.settings.general);
        updateDependencies(panel);

        clearTimeout(saveTimers[path]);
        const send = () => {
            delete saveTimers[path];
            save(section, { [key]: value });
        };
        if (delay) saveTimers[path] = setTimeout(send, delay);
        else send();
    }

    // Keep values the user is still dragging when a (older) reply arrives
    function keepPendingValues() {
        Object.keys(saveTimers).forEach((path) => {
            const [section, key] = path.split('.');
            const control = panel.querySelector(`[data-setting="${path}"]`);
            if (control && control.type === 'range') state.settings[section][key] = readSliderValue(control);
        });
    }

    panel.querySelectorAll('[data-setting]').forEach((control) => {
        const path = control.dataset.setting;
        if (control.classList.contains('segmented')) {
            control.querySelectorAll('button').forEach((btn) => {
                btn.addEventListener('click', () => {
                    if (getSetting(path) === btn.dataset.value) return;
                    setControlValue(control, btn.dataset.value);
                    changeSetting(path, btn.dataset.value);
                });
            });
        } else if (control.classList.contains('switch')) {
            control.addEventListener('click', () => {
                const value = control.getAttribute('aria-checked') !== 'true';
                setControlValue(control, value);
                changeSetting(path, value);
            });
        } else if (control.type === 'range') {
            control.addEventListener('input', () => {
                const value = readSliderValue(control);
                updateSliderFill(control);
                panel.querySelectorAll(`[data-value-for="${path}"]`).forEach((label) => {
                    label.textContent = formatValue(value, label.dataset.format);
                });
                changeSetting(path, value, SLIDER_SAVE_DELAY);
            });
        }
    });

    applyUiSettings(state.settings && state.settings.general);

    // -------------------------- Navigation --------------------------
    function showView(name) {
        currentView = name;
        views.forEach((view) => view.classList.toggle('active', view.dataset.view === name));
        const active = panel.querySelector(`.settings-view[data-view="${name}"]`);
        title.textContent = name === 'list' ? 'Settings' : active.dataset.title;
        backBtn.classList.toggle('hidden', name === 'list');
        active.scrollTop = 0;
        renderControls(active);
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
            keepPendingValues();
            applyUiSettings(state.settings.general);
            renderControls(panel);
            Object.values(pages).forEach((page) => page.onSettings && page.onSettings(state));
            if (currentView !== 'list' && pages[currentView]) pages[currentView].render(state);
            if (data.action === 'settings_saved') showToast('✓ Saved');
        } else if (data.action === 'settings_error') {
            const messages = Object.entries(data.errors || {}).map(([field, msg]) => `${field}: ${msg}`);
            showToast(messages.join('\n') || 'Could not save', 'error');
            if (pages[currentView] && pages[currentView].onErrors) pages[currentView].onErrors(data.errors);
            // Ask for the saved values so controls and preview snap back
            sendAction('get_settings');
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
