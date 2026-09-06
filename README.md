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

## Key Features (Not yet)

- **Screen Text Extraction (OCR):** Captures screen content in real-time and extracts text for processing.  
- **Hotkey & Region Selection:** Users can trigger OCR with a hotkey and select specific screen areas for analysis.  
- **AI Reasoning:** Processes extracted text to determine context, suggest actions, or guide users.  
- **Chatbot Interface:** Displays instructions or recommendations on-screen and allows user interaction.  
- **Automation Module:** Performs safe mouse and keyboard actions based on AI suggestions.    

---


## Project Structure

- `src/`: Source code modules (OCR, AI, Automation)
- `docs/`: Documentation and timeline
- `tests/`: Test scripts
- `assets/`: Project assets

## How to Run

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   cd code
   python -m src.main
   ```

### Build the Windows chat application

The Electron chat client can be packaged with its custom application icon:

```bash
cd electron_ui
npm install
npm run dist
```

The installer is written to `electron_ui/dist/AI Smart Assistant Setup 1.0.0.exe`.
The installed application starts the bundled Python service automatically. Python and the
project dependencies must be installed on the target computer, and Tesseract must be
available at the path configured in `code/src/config.json`.

---
