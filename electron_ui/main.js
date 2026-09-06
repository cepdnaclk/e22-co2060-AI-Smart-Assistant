const { app, BrowserWindow, globalShortcut } = require('electron');
const { spawn } = require('child_process');
const net = require('net');
const path = require('path');
const fs = require('fs');

let backendProcess = null;
let backendConsoleProcess = null;
let backendLogStream = null;

app.commandLine.appendSwitch('disable-gpu-disk-cache');

// Keep runtime data outside the packaged app.asar archive.
const userDataPath = path.join(app.getPath('appData'), 'AI Smart Assistant');
fs.mkdirSync(userDataPath, { recursive: true });
app.setPath('userData', userDataPath);

// Disable GPU shader disk cache entirely (prevents GPU cache errors)
app.commandLine.appendSwitch('disable-gpu-shader-disk-cache');
// Use a no-sandbox mode to avoid cache locking issues under certain Windows setups
app.commandLine.appendSwitch('no-sandbox');


function createWindow() {
    const { screen } = require('electron');
    const primaryDisplay = screen.getPrimaryDisplay();
    const { width, height } = primaryDisplay.workAreaSize;

    const winWidth = 400;
    const winHeight = height - 100;

    const win = new BrowserWindow({
        width: winWidth,
        height: winHeight,
        x: width - winWidth - 20,
        y: height - winHeight - 60,
        frame: false,
        transparent: true,
        icon: path.join(__dirname, 'build', 'icon.ico'),
        alwaysOnTop: true,
        show: true,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        }
    });

    win.loadFile('index.html');
}

function showChatWindow() {
    const win = BrowserWindow.getAllWindows()[0];
    if (win) {
        if (win.isMinimized()) win.restore();
        win.show();
        win.focus();
    }
}

function startBackend() {
    if (!app.isPackaged) return;

    const backendRoot = path.join(process.resourcesPath, 'assistant', 'code');
    const pythonCommand = process.env.AI_ASSISTANT_PYTHON || 'python';
    const logPath = path.join(app.getPath('userData'), 'assistant.log');
    backendLogStream = fs.createWriteStream(logPath, { flags: 'a' });
    backendLogStream.write(`\n\n=== AI Smart Assistant started ${new Date().toISOString()} ===\n`);

    backendProcess = spawn(pythonCommand, ['-m', 'src.main'], {
        cwd: backendRoot,
        env: {
            ...process.env,
            AI_ASSISTANT_ELECTRON_MANAGED: '1',
            AI_ASSISTANT_DATA_DIR: path.join(app.getPath('userData'), 'data'),
            PYTHONUNBUFFERED: '1'
        },
        windowsHide: true,
        stdio: ['ignore', 'pipe', 'pipe']
    });
    backendProcess.stdout.on('data', (data) => backendLogStream.write(data));
    backendProcess.stderr.on('data', (data) => backendLogStream.write(`[stderr] ${data}`));
    backendProcess.on('error', (error) => {
        const message = `Unable to start Python backend: ${error.message}\n`;
        backendLogStream.write(message);
        console.error(message);
    });

    const escapedLogPath = logPath.replace(/'/g, "''");
    const consoleCommand = `title AI Smart Assistant Console & powershell.exe -NoLogo -NoExit -Command "Get-Content -Path '${escapedLogPath}' -Wait"`;
    backendConsoleProcess = spawn('cmd.exe', ['/k', consoleCommand], {
        detached: true,
        windowsHide: false,
        stdio: 'ignore'
    });
    backendConsoleProcess.unref();
}

function stopBackend() {
    if (!backendProcess || backendProcess.killed) return;

    if (process.platform === 'win32') {
        spawn('taskkill', ['/pid', backendProcess.pid, '/t', '/f'], { windowsHide: true });
    } else {
        backendProcess.kill();
    }
    backendProcess = null;
    if (backendConsoleProcess && !backendConsoleProcess.killed) {
        backendConsoleProcess.kill();
    }
    backendConsoleProcess = null;
    if (backendLogStream) {
        backendLogStream.end();
        backendLogStream = null;
    }
}

function requestCapture() {
    const dataDir = path.join(app.getPath('userData'), 'data');
    fs.mkdirSync(dataDir, { recursive: true });
    fs.writeFileSync(path.join(dataDir, 'capture.request'), String(Date.now()));
}

function waitForBackend(timeoutMs = 15000) {
    if (!app.isPackaged) return Promise.resolve();

    return new Promise((resolve) => {
        const startedAt = Date.now();
        const check = () => {
            const socket = net.createConnection({ host: '127.0.0.1', port: 8000 });
            socket.once('connect', () => {
                socket.destroy();
                resolve();
            });
            socket.once('error', () => {
                socket.destroy();
                if (Date.now() - startedAt >= timeoutMs) {
                    resolve();
                } else {
                    setTimeout(check, 250);
                }
            });
        };
        check();
    });
}

app.whenReady().then(async () => {
    startBackend();
    await waitForBackend();
    createWindow();
    globalShortcut.register('CommandOrControl+Alt+Shift+C', showChatWindow);
    globalShortcut.register('CommandOrControl+Alt+Shift+O', requestCapture);

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

const { ipcMain } = require('electron');
ipcMain.on('show-window', (event) => {
    showChatWindow();
});
ipcMain.on('hide-window', (event) => {
    const win = BrowserWindow.getAllWindows()[0];
    if (win && win.isVisible()) {
        win.hide();
    }
});
ipcMain.on('quit-app', () => {
    app.quit();
});
ipcMain.on('minimize-window', (event) => {
    const win = BrowserWindow.getAllWindows()[0];
    if (win) {
        win.minimize();
    }
});

app.on('window-all-closed', () => {
    globalShortcut.unregisterAll();
    if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', stopBackend);
