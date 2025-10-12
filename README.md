# Nieve Analytics

Nieve Analytics is a powerful, AI-assisted desktop application designed for intuitive data visualization and analysis. Built with Electron and powered by a Python backend with the Google Gemini API, it allows users to seamlessly load CSV files, generate complex plots using natural language commands, and refine visualizations by directly editing the underlying Python code.

## Features

- **AI-Powered Plot Generation:** Simply type what you want to see, and Nieve Analytics will generate the corresponding plot.
- **Interactive Visualizations:** Modify existing plots with new instructions or by editing the generated Python code directly within the app.
- **Multiple Data Source Types:** Load data from CSV files, SQLite databases, or create derived data sources from existing ones.
- **Data Transformations:** Apply transformations to your data using natural language instructions.
- **Code-Level Control:** For advanced users, the generated Python code for each visualization is available for direct editing and execution.
- **State Persistence:** Your data sources, visualizations, and settings are saved locally, so you can pick up where you left off.

## Getting Started

To get started with Nieve Analytics, you'll need to have Node.js, npm, and Python installed on your system.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/nieve-analytics.git
    cd nieve-analytics
    ```

2.  **Install Node.js dependencies:**
    ```bash
    npm install
    ```

3.  **Create a Python virtual environment and install dependencies:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows, use `.venv\Scripts\activate`
    pip install -r requirements.txt
    ```

4.  **Start the application:**
    ```bash
    npm start
    ```

## Contributing

We welcome contributions from the community! Whether you're a developer, a designer, or a data enthusiast, there are many ways to get involved.

### Reporting Bugs

If you encounter a bug, please open an issue on our GitHub repository. When filing a bug report, please include the following:

-   A clear and descriptive title.
-   A detailed description of the issue, including steps to reproduce it.
-   Screenshots or screen recordings, if applicable.
-   Information about your operating system and app version.

### Suggesting Features

We're always looking for ways to improve Nieve Analytics. If you have an idea for a new feature or an enhancement to an existing one, please open an issue on our GitHub repository. Be sure to include a clear and detailed description of your suggestion and why you think it would be a valuable addition.

### Submitting Pull Requests

If you'd like to contribute code to the project, please follow these steps:

1.  Fork the repository and create a new branch for your feature or bug fix.
2.  Make your changes, ensuring that you follow the existing code style and conventions.
3.  Write tests for your changes, if applicable.
4.  Submit a pull request with a clear and detailed description of your changes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE.md) file for details.
