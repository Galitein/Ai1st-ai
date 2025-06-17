# Ai1st-ai

This repository contains the AI components for the Ai1st & Bestforming project. It provides services for document ingestion, embedding, semantic search, prompt generation, and integration with Google Drive, all exposed via a FastAPI backend.

---

## Table of Contents

- [Project Structure](#project-structure)
- [Main Components](#main-components)
  - [API Entry Point](#api-entry-point)
  - [Routes](#routes)
  - [Services](#services)
    - [Google Drive Integration](#google-drive-integration)
    - [Text Processing](#text-processing)
    - [Text Generation](#text-generation)
  - [Database Layer](#database-layer)
  - [Models](#models)
  - [Utilities](#utilities)
- [Environment Variables](#environment-variables)
- [How It Works](#how-it-works)
- [Development](#development)
- [License](#license)

---

## Project Structure

```
Ai1st-ai/
│
├── app.py
├── index.py
├── requirements.txt
├── README.md
├── LICENSE
│
├── src/
│   ├── __init__.py
│   ├── config/
│   ├── database/
│   │   ├── mongo.py
│   │   ├── qdrant_service.py
│   │   └── sql_record_manager.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── input_models.py
│   │   │   └── google_models.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── example_service.py
│   │   │   ├── google_service/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── create_folder.py
│   │   │   │   ├── drive_download.py
│   │   │   │   ├── drive_file_loader.py
│   │   │   │   ├── drive_upload.py
│   │   │   │   ├── file_list.py
│   │   │   │   ├── folder_list.py
│   │   │   │   └── google_oauth.py
│   │   │   ├── text_generation/
│   │   │   │   ├── generate_prompt.py
│   │   │   │   └── generate_response.py
│   │   │   ├── text_processing/
│   │   │   │   ├── create_embeddings.py
│   │   │   │   └── vector_search.py
│   │   ├── utils/
│   │   │   ├── __init__.py
│   │   │   ├── helpers.py
│   │   │   └── prompts/
│   │   │       ├── system_prompt.py
│   │   │       ├── meta_prompt.py
│   │   │       └── ... (other prompt files)
│   ├── routes/
│   │   ├── __init__.py
│   │   └── routes.py
│
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

---

## Main Components

### API Entry Point

- **`app.py`**: Initializes the FastAPI application, sets up CORS, and includes all API routes.
- **`index.py`**: Simple entry point for the application (prints a message if run directly).

### Routes

- **`src/routes/routes.py`**: Defines all API endpoints, including authentication, file upload/download, folder and file listing, embedding creation, search, and prompt generation.

### Services

#### Google Drive Integration (`src/app/services/google_service/`)

- **`google_oauth.py`**: Handles OAuth authentication with Google and token management.
- **`drive_upload.py`**: Uploads files to Google Drive.
- **`drive_download.py`**: Downloads files from Google Drive.
- **`file_list.py`**: Lists files in a specific Google Drive folder.
- **`folder_list.py`**: Lists folders in Google Drive.
- **`create_folder.py`**: Creates a new folder in Google Drive if it does not exist.
- **`drive_file_loader.py`**: Loads and chunks files from Google Drive for further processing.

#### Text Processing (`src/app/services/text_processing/`)

- **`create_embeddings.py`**: Orchestrates the process of loading documents, chunking, embedding, and indexing them in Qdrant for semantic search.
- **`vector_search.py`**: Performs semantic search over the indexed embeddings using Qdrant.

#### Text Generation (`src/app/services/text_generation/`)

- **`generate_prompt.py`**: Uses OpenAI to generate system prompts based on user tasks or existing prompts.
- **`generate_response.py`**: Generates chat completions using OpenAI, leveraging context retrieved from the semantic search.

### Database Layer (`src/database/`)

- **`mongo.py`**: Async MongoDB client for storing and retrieving documents.
- **`qdrant_service.py`**: Async and sync clients for interacting with Qdrant vector database.
- **`sql_record_manager.py`**: Manages SQL records for tracking file states and indexing.

### Models (`src/app/models/`)

- **`input_models.py`**: Pydantic models for API request/response validation (e.g., file names, queries, prompts).
- **`google_models.py`**: Pydantic models specific to Google Drive operations.

### Utilities (`src/app/utils/`)

- **`helpers.py`**: Common helper functions, such as text chunking and Google Drive file content loading.
- **`prompts/`**: Contains prompt templates and dynamically generated system prompts for use with LLMs.

---

## Environment Variables

The application relies on several environment variables, typically set in a `.env` file:

- `MODEL_NAME`: Name of the embedding model.
- `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_BIB_COLLECTION`: Qdrant vector DB configuration.
- `SCOPES`, `SCOPES_URL`: Google API scopes.
- `CREDENTIALS_PATH`, `CLIENT_FILE`: Paths to Google OAuth credentials.
- `REPO_NAME`: Default Google Drive folder name.
- `OPENAI_API_KEY`: API key for OpenAI.
- `SQLITE_DB_PATH`: Path for SQLite DB used by LangChain.
- `MONGO_URI`, `MONGO_DB`: MongoDB connection details.
- `DOWNLOAD_PATH`: Local path for downloaded files.

---

## How It Works

1. **Authentication**:  
   Users authenticate with Google via OAuth. Credentials and tokens are securely stored for subsequent API calls.

2. **File Management**:  
   - Upload files to Google Drive.
   - List folders and files in Google Drive.
   - Download files from Google Drive.

3. **Document Processing**:  
   - Files are loaded and chunked into manageable pieces.
   - Each chunk is embedded using a transformer model.
   - Embeddings are indexed in Qdrant for fast semantic search.

4. **Semantic Search**:  
   - Users can query the indexed data.
   - The system retrieves the most relevant document chunks using vector similarity.

5. **Prompt Generation & Chat**:  
   - System prompts are generated using OpenAI based on user tasks.
   - Chat completions are generated using OpenAI, leveraging retrieved context.

6. **Database Storage**:  
   - MongoDB is used for storing metadata and user sessions.
   - Qdrant is used for vector storage and search.
   - SQLite is used for tracking indexing state.

---

## Development

### Prerequisites

- Python 3.8+
- [Qdrant](https://qdrant.tech/) running locally or remotely
- MongoDB instance
- Google Cloud project with Drive API enabled
- OpenAI API key

### Setup

1. **Clone the repository**  
   ```bash
   git clone <repo-url>
   cd Ai1st-ai
   ```

2. **Install dependencies**  
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**  
   Create a `.env` file in the root directory with all required variables.

4. **Run the application**  
   ```bash
   python app.py
   ```

### Testing

- Place your unit, integration, and end-to-end tests in the `tests/` directory.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## Notes

- Sensitive files and data (such as credentials, tokens, and local cache) are excluded from version control via `.gitignore`.
- For prompt engineering, see the templates in `src/app/utils/prompts/`.
- For extending or customizing the AI pipeline, refer to the modular service files in `src/app/services/`.

---

**For any questions or contributions, please open an issue or pull request.**