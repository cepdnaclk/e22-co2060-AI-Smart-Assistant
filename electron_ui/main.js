const { app, BrowserWindow } = require('electron');
const path = require('path');

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
    const winHeight = height - 100;

    const win = new BrowserWindow({
        width: winWidth,
        height: winHeight,
        x: width - winWidth - 20,
        y: height - winHeight - 60,
        frame: false,
        transparent: true,
        alwaysOnTop: true,
        show: false,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        }
    });

    win.loadFile('index.html');
}

app.whenReady().then(() => {
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

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});
