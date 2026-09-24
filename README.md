# AI Smart Assistant

**Team:** SENTINELS  
**University:** University of Peradeniya  

** The Project :** 2YP (Second Year Project)  
CO2060 : Software Systems Design Project
---
## Team members 

K.J.V.Kahagalla

K.A.H.Kumarasinghe

P.A.K.N.Sooriyabandara

K.D.N.Chandrasena


## Project Overview

The **AI Smart Assistant** is an intelligent software tool designed to help users interact with their computers more efficiently.
It combines **screen reading (OCR)**, **AI reasoning**, and **automation** to guide users through tasks like software installations, error handling, and routine operations. 
The system aims to simplify complex computer interactions and make them accessible even to non-technical users.
For now this use local AI model.

---

## Key Features

- **Screen Text Extraction (OCR):** Captures screen content in real-time and extracts text for processing.  
- **Hotkey & Region Selection:** Users can trigger OCR with a hotkey and select specific screen areas for analysis.  
- **AI Reasoning:** Processes extracted text to determine context, suggest actions, or guide users.  
- **Chatbot Interface:** Displays instructions or recommendations on-screen and allows user interaction.  
- **Automation Module:** Performs safe mouse and keyboard actions based on AI suggestions.    
- **Automated AI Model Management:** Automatically launches Ollama in the background and downloads Mistral if required.

---

## Project Structure

- `src/`: Source code modules (OCR, AI, Automation)
- `docs/`: Documentation and timeline
- `tests/`: Test scripts
- `assets/`: Project assets

---

## How to Run (Developer Mode)

1. **Install Python dependencies:**
   Navigate to the `code` directory and run:
   ```bash
   pip install -r requirements.txt
   ```

2. **Install Electron UI dependencies:**
   Navigate to the `electron_ui` directory and run:
   ```bash
   npm install
   ```

3. **Run the application:**
   Go to the `code` directory and start the main python script (this will automatically launch the UI):
   ```bash
   python -m src.main
   ```

---

## How to Package for Release

To generate a standalone `.exe` setup file for clients:

1. Open **Command Prompt** as **Administrator** (Important: Administrator rights are required on Windows to bypass symlink security restrictions during the build).
2. Navigate to the project root directory.
3. Run the automated build script:
   ```cmd
   .\build_app.bat
   ```
4. The final installer will be generated at `electron_ui/dist/AI Smart Assistant Setup 1.0.0.exe`.

*Note: Make sure to place `OllamaSetup.exe` in the same folder as your generated installer before distributing it to your users, so the setup can seamlessly install Ollama!*

---
