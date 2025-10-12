# Project: Nieve Analytics

## Project Overview

Nieve Analytics is a desktop application for AI-assisted data visualization. It is built with Electron and uses a Python backend for data processing and interaction with the Gemini API. Users can load CSV files, generate plots using natural language commands, and modify existing plots with either new instructions or by directly editing the generated Python code.

**Key Technologies:**

*   **Frontend:** HTML, CSS, JavaScript (Renderer Process)
*   **Application Shell:** Electron
*   **Backend:** Python
*   **AI:** Google Gemini
*   **Data Handling:** pandas
*   **Plotting:** Matplotlib

**Architecture:**

The application consists of two main parts:

1.  **Electron Shell:** The main process (`index.js`) manages the application window, state, and communication with the backend. The renderer process (`index.html`) provides the user interface. Communication between the two is handled via IPC and a preload script (`preload.js`).
2.  **Python Backend:** A Python script (`main.py`) is executed by the Electron app to handle data processing and AI-powered code generation. It receives commands and data from the Electron app via command-line arguments and returns results as JSON to stdout.

## Building and Running

**Prerequisites:**

*   Node.js and npm
*   Python and a virtual environment (`.venv`)

**Running the Application:**

1.  Install Node.js dependencies:
    ```bash
    npm install
    ```
2.  Create a Python virtual environment and install dependencies:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows, use `.venv\Scripts\activate`
    pip install pandas matplotlib google-generativeai
    ```
3.  Start the application:
    ```bash
    npm start
    ```

**Building a Distributable Package:**

*   **For Windows:**
    ```bash
    npm run dist
    ```
*   **For Linux (.deb):**
    ```bash
    npm run dist:linux
    ```
    *Note: Building for Linux on Windows requires Docker Desktop to be installed and running.*

## Development Conventions

*   **State Management:** Application state (loaded data sources, visualizations, settings) is persisted in a JSON file located at `~/.nieve-ai/state.json`.
*   **Communication:** The Electron frontend communicates with the Python backend by spawning the `main.py` script as a child process and passing commands and arguments. Data is exchanged via JSON strings.
*   **API Keys:** The Gemini API key is stored in the application state file and is encrypted.
*   **Error Handling:** The Python script logs errors to `app.log` and prints error messages to stderr, which are then caught by the Electron process and displayed to the user.
