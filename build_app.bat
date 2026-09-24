@echo off
echo ==============================================
echo Building AI Smart Assistant
echo ==============================================

echo [1/3] Compiling Python Backend with PyInstaller...
cd code
:: Clean previous builds
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

:: Install PyInstaller if missing
pip install pyinstaller

:: Compile the main.py into a standalone folder
python -m PyInstaller --name main --noconfirm --onedir --add-data "src/errors_db.json;." --collect-all scipy --collect-all nltk --collect-all llama_index --collect-all sentence_transformers --collect-all faiss src/main.py

echo [2/3] Building Electron UI and Installer...
cd ../electron_ui
:: Clean previous builds
if exist dist rmdir /s /q dist

:: Install electron-builder if missing
call npm install electron-builder --save-dev

:: Bypass Windows Administrator permission errors for symlinks
set USE_HARD_LINKS=false
set CSC_IDENTITY_AUTO_DISCOVERY=false

:: Run electron builder
call npm run build

echo [3/3] Done!
echo ==============================================
echo Your installer is located at: 
echo electron_ui/dist/AI Smart Assistant Setup 1.0.0.exe
echo.
echo Make sure to place OllamaSetup.exe in the same folder 
echo before distributing to your users!
pause
