# BetterFeeling - Disease and Drug Analysis Platform

A platform for analyzing disease mechanisms, drug targets, and treatment pathways using data from multiple medical databases.

## Features

- Fetch data from multiple sources: data.gouv.fr, HetIO, and KEGG
- RAG (Retrieval Augmented Generation) system with vector embeddings and graph storage
- Natural language queries using local Ollama models
- Clustering and filtering of diseases and compounds
- Interactive graph visualization with zoom and pan controls
- API rate limiting to respect external service quotas

## Data Sources

- **data.gouv.fr**: French government open data for drug evaluations
- **HetIO**: Disease-compound relationships and biomedical knowledge
- **KEGG**: Pathway and disease information from KEGG database

## Requirements

- Python 3.8+
- Ollama (for local LLM queries)
- 4GB+ RAM recommended
- Internet connection for fetching external data

## Installation

1. Run the setup script:
```bash
chmod +x setup.sh
./setup.sh
```

2. Install and start Ollama:
```bash
# Install Ollama from https://ollama.ai
ollama serve

# In another terminal, pull required models
ollama pull llama3.2
ollama pull nomic-embed-text
```

## Running the Application

1. Activate the virtual environment:
```bash
source venv/bin/activate
```

2. Start the application:
```bash
python app.py
```

3. Open your browser to: http://localhost:9999

## Configuration

Edit `config.json` to customize:
- Ollama model settings
- API rate limits
- Server port and host
- Data storage paths
- Logging configuration

## Usage

### Fetching Data

1. Select a data source from the dropdown
2. Click "Fetch Data" to load data from external APIs
3. Data is automatically indexed in the RAG system

### Querying

1. Enter a natural language question in the query box
2. Click "Submit Query" to get AI-generated responses
3. The system uses RAG to provide context-aware answers

### Graph Visualization

- Pan: Click and drag on empty space
- Zoom: Use +/- buttons or mouse wheel
- Node Info: Click on any node to see details
- Filter: Use type filter or keyword search to focus on specific nodes

### Clustering

1. Select a clustering method (K-Means or DBSCAN)
2. Set the number of clusters
3. Click "Cluster" to group similar nodes
4. Clusters are saved and can be used for filtering

## Project Structure

```
BetterFeeling/
├── app.py                  # Main Flask application
├── rate_limiter.py         # API rate limiting
├── data_fetchers.py        # Data fetching from external APIs
├── rag_system.py           # RAG graph storage and retrieval
├── ollama_client.py        # Ollama LLM integration
├── clustering.py           # Clustering and filtering logic
├── config.json             # Configuration file
├── requirements.txt        # Python dependencies
├── templates/
│   └── index.html         # Web interface
├── data/                  # Data storage
│   ├── cache/            # Cached API responses
│   ├── graph.db          # Graph database
│   └── vectors/          # Vector database
└── logs/                  # Application logs
    └── app.log

```

## API Endpoints

- `GET /` - Main web interface
- `GET /api/stats` - System statistics
- `POST /api/query` - Natural language queries
- `POST /api/fetch_data` - Fetch data from external sources
- `GET /api/graph` - Get graph data for visualization
- `POST /api/cluster` - Perform clustering
- `POST /api/filter` - Filter nodes by criteria
- `GET /api/neighbors` - Get node neighbors
- `POST /api/path` - Find paths between nodes

## Logging

Logs are written to:
- Console (stdout)
- File: `logs/app.log`

Log level can be configured in `config.json`.

## Development

All configuration is centralized in `config.json` to avoid hard-coded paths and improve portability. When adding new features:

1. Add any new paths to the `paths` section of `config.json`
2. Reference config paths in Python code

