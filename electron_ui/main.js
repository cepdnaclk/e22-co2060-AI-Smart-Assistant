const { app, BrowserWindow } = require('electron');
const path = require('path');
const os = require('os');
const fs = require('fs');
const net = require('net');

function getFreePort() {
    return new Promise((resolve, reject) => {
        const srv = net.createServer(function(sock) {
            sock.end('Hello world\n');
        });
        srv.listen(0, function() {
            const port = srv.address().port;
            srv.close((err) => {
                if (err) reject(err);
                else resolve(port);
            });
        });
        srv.on('error', function(err) {
            reject(err);
        });
    });
}

// Redirect user data to a temporary folder so locked cache files don't break restarts
const tempUserDataPath = path.join(os.tmpdir(), 'electron_ui_' + Date.now());
app.setPath('userData', tempUserDataPath);

app.commandLine.appendSwitch('disable-gpu-disk-cache');

// Fix: Redirect Electron's cache to a writable local folder to avoid
// "Unable to move/create cache: Access is denied" errors on Windows.
app.setPath('userData', path.join(__dirname, '.electron_cache'));

// Disable GPU shader disk cache entirely (prevents GPU cache errors)
app.commandLine.appendSwitch('disable-gpu-shader-disk-cache');
// Use a no-sandbox mode to avoid cache locking issues under certain Windows setups
app.commandLine.appendSwitch('no-sandbox');


function createWindow() {
    const { screen } = require('electron');
    const primaryDisplay = screen.getPrimaryDisplay();
    const { width, height } = primaryDisplay.workAreaSize;

    const winWidth = 400;
    const winHeight = height - 40;

    const win = new BrowserWindow({
        width: winWidth,
        height: winHeight,
        x: width - winWidth - 20,
        y: height - winHeight - 20,
        frame: false,
        transparent: true,
        alwaysOnTop: true,
        show: true,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        }
    });

    win.loadFile('index.html');
}

app.whenReady().then(async () => {
    if (app.isPackaged) {
        try {
            const port = await getFreePort();
            process.env.CHAT_SERVER_PORT = port;
            const { spawn } = require('child_process');
            const backendPath = path.join(process.resourcesPath, 'backend', 'main.exe');
            if (fs.existsSync(backendPath)) {
                const backendProcess = spawn(backendPath, [], { 
                    detached: false,
                    env: { ...process.env, CHAT_SERVER_PORT: port, PYTHONIOENCODING: "utf8" }
                });
                app.on('will-quit', () => {
                    if (backendProcess) {
                        try {
                            backendProcess.kill();
                            const { exec } = require('child_process');
                            exec(`taskkill /F /PID ${backendProcess.pid} /T`);
                        } catch (e) {}
                    }
                });
            }
        } catch (err) {
            console.error("Failed to get free port:", err);
        }
    }
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

const { ipcMain } = require('electron');
ipcMain.on('show-window', (event) => {
    const win = BrowserWindow.getAllWindows()[0];
    if (win && !win.isVisible()) {
        win.show();
    }
});
ipcMain.on('hide-window', (event) => {
    const win = BrowserWindow.getAllWindows()[0];
    if (win && win.isVisible()) {
        win.hide();
    }
});
ipcMain.on('minimize-window', (event) => {
    const win = BrowserWindow.getAllWindows()[0];
    if (win) {
        win.minimize();
    }
});
ipcMain.handle('choose-file', async (event, options = {}) => {
    const { dialog } = require('electron');
    const win = BrowserWindow.fromWebContents(event.sender);
    const result = await dialog.showOpenDialog(win, {
        title: options.title || 'Choose a file',
        defaultPath: options.defaultPath || undefined,
        filters: options.filters || [],
        properties: ['openFile'],
    });
    return result.canceled ? null : result.filePaths[0];
});
ipcMain.on('set-always-on-top', (event, enabled) => {
    const win = BrowserWindow.fromWebContents(event.sender);
    if (win && win.isAlwaysOnTop() !== Boolean(enabled)) {
        win.setAlwaysOnTop(Boolean(enabled));
    }
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});
