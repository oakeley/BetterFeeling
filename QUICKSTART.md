# BetterFeeling - Quick Start Guide

## Current Status

The application is running on **http://localhost:9999**

### Database Contents
- **37 nodes**: 23 diseases, 10 pathways, 4 drug targets
- **2 relationships**: Disease-to-target connections
- **37 vector documents**: For RAG-based natural language queries

### Populated Data Includes:
- Common diseases: Obesity, Type 2 Diabetes, Hypertension, Alzheimer's, Parkinson's, Lung Cancer, Depression, Rheumatoid Arthritis
- Drug targets: GLP-1 Receptor, TNF-alpha, EGFR, BACE1
- KEGG diseases: 15 diseases with detailed pathway information
- KEGG pathways: Metabolic and disease-related pathways

## Using the Web Interface

1. **Open browser**: Navigate to http://localhost:9999
2. **View statistics**: See node counts in the header
3. **Submit queries**:
   - Enter questions in the Query text box
   - Click "Submit Query"
   - The "Loading..." indicator will show while Ollama processes
   - Results appear below the controls with smooth scrolling
4. **Filter data**:
   - Select node type (disease/pathway/target)
   - Enter keywords to search
   - Click "Apply Filter"
5. **Visualize graph**:
   - Interactive D3.js visualization
   - Click and drag nodes
   - Zoom with +/- buttons
   - Click nodes to see details
6. **Fetch more data**:
   - Select data source
   - Click "Fetch Data"
   - Progress shown in loading indicator

## Example Queries

Try these queries to test the system:

```
What are potential therapies for obesity?
What drug targets are associated with type 2 diabetes?
Tell me about Alzheimer's disease and its treatments
What is the GLP-1 receptor and what drugs target it?
How are obesity and diabetes related?
```

## Improvements Made

### Fixed Frontend Issues:
1. **Loading feedback**: Now shows "Loading..." when queries are running
2. **Error messages**: Clear error display if something fails
3. **Response display**: Automatically scrolls to show results
4. **Status messages**: Shows progress when fetching data

### Data Population:
- Created `populate_data.py` script to add curated disease and drug data
- Includes high-value diseases with unmet medical needs
- Links diseases to drug targets with relationships
- Can be re-run to refresh data: `conda run -n better python populate_data.py`

## Technical Notes

### Current Ollama Model
Using `qwen3:4b` for queries (configured in config.json)

### API Endpoints Working:
- `GET /api/stats` - System statistics
- `POST /api/query` - Natural language queries (RAG-based)
- `POST /api/fetch_data` - Fetch from external APIs
- `GET /api/graph` - Graph visualization data
- `POST /api/cluster` - Cluster nodes
- `POST /api/filter` - Filter by keyword

### Known Issues:
- HetIO API endpoints have changed (404 errors) but error handling works correctly
- ChromaDB telemetry errors are harmless (disabled telemetry issue)
- Graph statistics may take a moment to update after fetching new data

## Managing the Server

### Start server:
```bash
conda run -n better python app.py
```

### Stop server:
```bash
pkill -f "python app.py"
```

### View logs:
```bash
tail -f logs/app.log
```

### Repopulate database:
```bash
conda run -n better python populate_data.py
```

## Configuration

All settings are in `config.json`:
- Ollama model selection
- API rate limits
- Server port
- Data paths
- Logging level

No hard-coded paths - everything references config.json for portability.
