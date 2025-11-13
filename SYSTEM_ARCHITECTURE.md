# BetterFeeling System Architecture

## Overview
This document explains exactly how the system works, what happens during data fetching, how connections are made, and the role of Ollama.

---

## 1. How Connections Are Made

### Current Implementation: MANUAL + KEYWORD-BASED (No Ollama)

**Three methods are used to create relationships:**

#### A. Manual Curation (add_relationships.py)
```python
# Hard-coded relationships based on medical knowledge
if 'sample_diabetes_type2' in graph:
    add_relationship('sample_diabetes_type2', 'target_GLP1R', 'treated_by')
```

**Evidence**: Lines 16-28 in add_relationships.py
- Disease → Target connections (e.g., diabetes → GLP-1 receptor)
- Based on established clinical evidence
- **No AI involvement** - purely curated medical knowledge

#### B. Keyword Matching (add_relationships.py)
```python
# Line 58-69: Link KEGG diseases to sample diseases
disease_name = disease_data.get('name', '').lower()
if 'cancer' in disease_name or 'leukemia' in disease_name:
    add_relationship(kegg_disease, 'sample_cancer_lung', 'related_to')
```

**Evidence**: Lines 56-69 in add_relationships.py
- Simple string matching: "cancer" → link to lung cancer
- **No semantic analysis** - purely text pattern matching
- **No Ollama used**

#### C. Predefined Clusters (add_relationships.py)
```python
# Line 31-37: Disease clusters
disease_clusters = {
    'metabolic': ['sample_obesity', 'sample_diabetes_type2', 'sample_hypertension'],
    'neurodegenerative': ['sample_alzheimers', 'sample_parkinsons'],
}
```

**Evidence**: Lines 30-50 in add_relationships.py
- Pre-defined groupings based on disease categories
- Creates "shares_mechanism" edges within groups
- **No AI reasoning** - hard-coded medical categories

### Critical Finding: NO AUTOMATIC RELATIONSHIP DISCOVERY

**The system does NOT:**
- Use Ollama to infer relationships
- Parse KEGG pathway data to extract gene-disease connections
- Automatically discover therapeutic targets from text
- Learn relationships from medical literature

**Why this matters:**
- Current relationships are limited to what's manually coded
- KEGG provides GENE and PATHWAY data but we're not parsing it
- Connections are conservative but extremely limited in scope

---

## 2. Links to Pathways Associated with Diseases

### Current State: PATHWAYS ARE IGNORED

**What KEGG provides:**
```
ENTRY       H00001
NAME        B-cell acute lymphoblastic leukemia
GENE        BCR-ABL1, PAX5, IKZF1, ETV6-RUNX1, etc.
PATHWAY     hsa05200  Pathways in cancer
            hsa05202  Transcriptional misregulation in cancer
```

**What we currently extract:**
```python
# populate_data.py line 58-66
rag_system.add_document(
    disease_id,
    f"Disease: {disease_name}\n{disease_info}",  # Raw text only!
    metadata,
    'disease'
)
```

**Critical Issue**:
- KEGG diseases contain PATHWAY references (e.g., `hsa05200`)
- We store this as plain text in the RAG system
- **We DO NOT parse it to create graph edges**
- Pathways exist as separate nodes but are NOT connected to diseases via structured relationships

**Evidence**: Check populate_data.py lines 44-66 - no pathway parsing logic

### What SHOULD Happen (Not Implemented):

```python
# Extract pathway IDs from KEGG disease info
pathway_ids = extract_pathway_ids(disease_info)  # NOT IMPLEMENTED
for pathway_id in pathway_ids:
    rag_system.add_relationship(disease_id, pathway_id, 'involves_pathway')
```

---

## 3. How Deep Will Queries Go on the Web?

### Answer: SINGLE-LEVEL FETCH ONLY (No Recursion)

**When you click "Fetch Data":**

1. **KEGG Pathways**: Fetches list, extracts first 10 entries
   ```python
   pathways = data_fetcher.kegg.fetch_pathway_list()[:10]
   # Does NOT fetch detailed pathway info
   # Does NOT follow pathway → gene links
   ```
   **Depth**: 1 API call, surface-level metadata only

2. **KEGG Diseases**: Fetches list, then fetches DETAILS for each
   ```python
   diseases = data_fetcher.kegg.fetch_disease_list()[:15]
   for disease in diseases:
       info = fetch_disease_info(disease_id)  # Second API call per disease
   ```
   **Depth**: 2 levels (list → details), but does NOT follow gene/pathway references

3. **HetIO**: Single API call for nodes
   ```python
   diseases = data_fetcher.hetio.fetch_diseases()[:20]
   # Does NOT call fetch_relationships() to get edges!
   ```
   **Depth**: 1 level only

**Critical Limitation**:
- HetIO has a `fetch_relationships()` method (data_fetchers.py line 105)
- **It is NEVER called in the current implementation**
- HetIO provides disease-compound-gene relationships, but we ignore them

**Rate Limiting**:
- KEGG: Max 10 requests/minute (config.json line 17)
- Each disease detail fetch = 1 request
- Fetching 15 diseases = ~2 minutes with rate limiting
- **No background processing** - runs synchronously in web request
- **No restart on failure** - if browser closes, fetch stops

---

## 4. What Exactly Does "Fetch Data" Do?

### Detailed Breakdown (app.py lines 84-148)

**Step 1: User clicks "Fetch Data" button**
- Frontend sends POST to `/api/fetch_data` with source parameter

**Step 2: Backend fetches from APIs (SYNCHRONOUS)**
```python
if source == 'kegg':
    pathways = fetch_pathway_list()[:10]  # Get 10 pathway names
    # Store each as: "Pathway: {name}" in RAG system
    # Add to graph as node type 'pathway'
```

**Step 3: Add to RAG system**
```python
rag_system.add_document(
    pathway_id,           # e.g., "hsa:00001"
    f"Pathway: {name}",   # Plain text for vector search
    metadata,             # Dict with id, name, source
    'pathway'             # Node type
)
```

**What this does:**
- Adds node to NetworkX graph
- Creates vector embedding (using Ollama's nomic-embed-text)
- Stores in ChromaDB for similarity search
- **Does NOT create edges** - nodes are isolated

**Step 4: Save to disk**
```python
rag_system.save()  # Saves graph.db (pickle) and vectors/ (ChromaDB)
```

**What "Fetch Data" does NOT do:**
- Does NOT run in background (blocks browser request)
- Does NOT parse structured data (genes, pathways) into edges
- Does NOT call HetIO relationship APIs
- Does NOT restart on interruption
- Does NOT provide progress updates beyond initial "Fetching data from..."

---

## 5. Will It Continue in Background / Restart if Incomplete?

### Answer: NO BACKGROUND PROCESSING

**Current behavior:**
1. User clicks "Fetch Data"
2. Browser sends HTTP POST request
3. Flask handler runs SYNCHRONOUSLY
4. Browser waits for response (can timeout)
5. If browser is closed, fetch STOPS

**Evidence**: app.py line 84-148 - standard Flask route with no async/background processing

**What happens on timeout:**
- Partial data IS saved (rag_system.save() at line 142)
- But NO resume capability
- Next fetch starts from scratch
- Duplicate entries may occur

**What's needed for background processing:**
- Celery task queue (not implemented)
- Redis for job tracking (not implemented)
- Progress tracking endpoint (not implemented)

---

## 6. What Does "Clustering Method" Do?

### Answer: GRAPH TOPOLOGY CLUSTERING (Not Semantic)

**Located in**: clustering.py lines 18-51

**What gets clustered**: Graph structure features, NOT semantic content

```python
def extract_features_from_graph(graph, node_ids):
    for node_id in node_ids:
        feature_vector = [
            graph.degree(node_id),        # Total connections
            graph.in_degree(node_id),     # Incoming edges
            graph.out_degree(node_id),    # Outgoing edges
            len(list(graph.neighbors(node_id)))  # Neighbor count
        ]
```

**Evidence**: Lines 27-32 in clustering.py

**What this means:**
- Nodes are grouped by HOW MANY connections they have
- NOT by what they mean semantically
- Example: A highly-connected disease and a highly-connected pathway may cluster together
- This is NOT based on medical similarity

**Two methods available:**

1. **K-Means** (lines 38-51):
   - User specifies number of clusters
   - Groups nodes with similar connection counts
   - Example: "Diseases with 3-5 connections" vs "Diseases with 0-2 connections"

2. **DBSCAN** (lines 53-66):
   - Density-based clustering
   - Finds nodes with similar connection patterns
   - Can identify outliers (isolated nodes)

**Critical Limitation:**
- Clustering is based on graph topology ONLY
- Does NOT use semantic similarity
- Does NOT use vector embeddings from ChromaDB
- Does NOT use Ollama to understand content

**What clustering SHOULD do (not implemented):**
```python
# Use vector embeddings for semantic clustering
embeddings = [generate_embeddings(node_text) for node in nodes]
clusters = kmeans(embeddings)  # Group by meaning, not connections
```

---

## 7. Role of Ollama in the System

### Current Role: QUERY RESPONSE ONLY

**Ollama is used in EXACTLY ONE place:**

```python
# ollama_client.py line 44-58
def query_rag(query, rag_system, max_context_items=5):
    # 1. Get similar documents from vector DB
    similar_docs = rag_system.query_similar(query, n_results=5)

    # 2. Extract text from similar docs
    context = [doc['document'] for doc in similar_docs]

    # 3. Send to Ollama with context
    return ollama_client.generate_response(query, context)
```

**What Ollama does:**
- Receives user query (e.g., "How are obesity and diabetes related?")
- Receives 5 relevant text chunks from vector search
- Generates natural language response
- **That's it**

**What Ollama does NOT do:**
- Does NOT discover relationships between entities
- Does NOT parse KEGG data to extract genes/pathways
- Does NOT validate relationships
- Does NOT reason about graph structure
- Does NOT participate in data fetching
- Does NOT create embeddings (nomic-embed-text does that separately)

**Evidence**: Check ollama_client.py - only used in query_rag() method

---

## 8. Hallucination Risk: MODERATE TO HIGH

### Where Hallucinations Can Occur:

**Current Query Response (ollama_client.py line 44):**
```python
def query_rag(query, rag_system):
    similar_docs = rag_system.query_similar(query, n_results=5)
    context = [doc['document'] for doc in similar_docs]
    return self.generate_response(query, context)
```

**Problem**: No hallucination prevention
- Ollama can add information NOT in context
- No fact-checking against graph structure
- No citation of sources
- No confidence scores

**Example hallucination:**
```
Query: "What treats obesity?"
Context: "Obesity is characterized by excess body fat..."
Ollama: "Obesity is treated with semaglutide, liraglutide, and NEW_DRUG_2024"
```
The last drug may be hallucinated if not in the context.

### Recommendations for Reducing Hallucinations:

#### 1. Constrain Prompt (NOT IMPLEMENTED)
```python
# What we SHOULD do:
prompt = f"""Answer ONLY using information from the context below.
If the context doesn't contain the answer, say "I don't have that information."
Do NOT add information not present in the context.

Context:
{context}

Question: {query}

Answer:"""
```

#### 2. Cross-Check Against Graph (NOT IMPLEMENTED)
```python
# Validate response against graph edges
response = ollama.query_rag(query, rag_system)
claimed_relationships = extract_relationships(response)
for rel in claimed_relationships:
    if not graph.has_edge(rel.source, rel.target):
        flag_as_unsupported(rel)
```

#### 3. Add Citations (NOT IMPLEMENTED)
```python
# Include source document IDs in response
"Obesity is treated with GLP-1 agonists [source: sample_obesity]"
```

#### 4. Use Structured Output (NOT IMPLEMENTED)
```python
# Force Ollama to output JSON with source citations
response_schema = {
    "answer": str,
    "sources": [str],
    "confidence": float
}
```

---

## 9. What SHOULD Be Implemented

### A. Parse KEGG Pathway Data
```python
def extract_kegg_pathways(disease_info):
    """Parse PATHWAY section from KEGG disease entry"""
    pathway_matches = re.findall(r'hsa\d+', disease_info)
    return pathway_matches

# Then create edges:
for pathway_id in extract_kegg_pathways(disease_info):
    rag_system.add_relationship(disease_id, pathway_id, 'involves_pathway')
```

### B. Use HetIO Relationships
```python
# HetIO provides disease-gene-compound edges
for disease in hetio_diseases:
    relationships = data_fetcher.hetio.fetch_relationships(
        disease['id'],
        'DaG'  # Disease associates Gene
    )
    for rel in relationships:
        rag_system.add_relationship(disease_id, gene_id, 'associates_gene')
```

### C. Background Processing
```python
from celery import Celery

@celery.task
def fetch_data_background(source):
    # Runs in background
    # Can be interrupted and resumed
    # Provides progress updates
```

### D. Conservative Ollama Usage
```python
def query_rag_conservative(query, rag_system):
    similar_docs = rag_system.query_similar(query, n_results=5)

    # Build constrained prompt
    prompt = f"""STRICT INSTRUCTIONS:
    - Answer ONLY using the context below
    - Do NOT add external knowledge
    - If unsure, say "I don't have enough information"
    - Cite sources using [source: node_id]

    Context:
    {format_context_with_ids(similar_docs)}

    Question: {query}"""

    response = ollama.generate_response(prompt)

    # Validate response against graph
    if contains_unverified_claims(response, rag_system.graph):
        return "I found relevant information but cannot verify all details. Here's what I'm certain about: [safe_subset]"

    return response
```

### E. Semantic Clustering
```python
def cluster_by_meaning(nodes, rag_system):
    # Get embeddings from ChromaDB
    embeddings = []
    for node_id in nodes:
        doc_embedding = rag_system.collection.get(node_id)['embedding']
        embeddings.append(doc_embedding)

    # Cluster by semantic similarity
    return kmeans(embeddings, n_clusters=5)
```

---

## Summary Table

| Feature | Current State | Uses Ollama? | Hallucination Risk | Should Be Improved? |
|---------|--------------|--------------|-------------------|-------------------|
| **Relationship Creation** | Manual + keyword matching | No | None (no AI) | Yes - parse KEGG pathways |
| **Pathway Links** | Stored as text, not parsed | No | N/A | Yes - extract and link |
| **Web Query Depth** | 1-2 levels, no recursion | No | N/A | Yes - fetch HetIO edges |
| **Fetch Data** | Synchronous, no background | No | N/A | Yes - add Celery tasks |
| **Clustering** | Graph topology only | No | None | Yes - use semantic embeddings |
| **Query Response** | RAG-based generation | Yes | **HIGH** | **Yes - add constraints** |

## Critical Recommendations:

1. **PARSE KEGG PATHWAY DATA** - Extract structured gene/pathway relationships
2. **USE HETIO RELATIONSHIPS** - Fetch disease-gene-compound edges
3. **CONSTRAIN OLLAMA PROMPTS** - Reduce hallucinations with strict instructions
4. **ADD SOURCE CITATIONS** - Make Ollama cite where information comes from
5. **VALIDATE RESPONSES** - Cross-check Ollama output against graph structure
6. **SEMANTIC CLUSTERING** - Use vector embeddings, not just connection counts
7. **BACKGROUND PROCESSING** - Implement async data fetching with progress tracking
