const { app, BrowserWindow } = require('electron');
const path = require('path');
const os = require('os');
const fs = require('fs');

// Redirect user data to a temporary folder so locked cache files don't break restarts
const tempUserDataPath = path.join(os.tmpdir(), 'electron_ui_' + Date.now());
app.setPath('userData', tempUserDataPath);

app.commandLine.appendSwitch('disable-gpu-disk-cache');

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

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});
