from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import json
import logging
import os
from rate_limiter import RateLimiterManager
from data_fetchers import DataFetcherManager
from rag_system import RAGGraphSystem
from ollama_client import OllamaClient
from clustering import ClusteringAnalyzer
from web_search import WebSearcher
import networkx as nx
from networkx.readwrite import json_graph

def setup_logging(config):
    """Configure logging based on config settings"""
    log_dir = config['paths']['logs_dir']
    os.makedirs(log_dir, exist_ok=True)

    log_file = config['paths']['log_file']
    log_level = getattr(logging, config['logging']['level'])
    log_format = config['logging']['format']

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

def load_config(config_path='config.json'):
    """Load configuration from JSON file"""
    with open(config_path, 'r') as f:
        return json.load(f)

config = load_config()
setup_logging(config)
logger = logging.getLogger(__name__)

app = Flask(__name__,
           static_folder=config['paths']['static_dir'],
           template_folder=config['paths']['templates_dir'])
CORS(app)

rate_limiter = RateLimiterManager(config['api_limits'])
data_fetcher = DataFetcherManager(rate_limiter, config)
rag_system = RAGGraphSystem(config)
ollama_client = OllamaClient(config)
clustering_analyzer = ClusteringAnalyzer(config)
web_searcher = WebSearcher()

logger.info("Application initialized successfully")

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    stats = rag_system.get_statistics()
    logger.info("Stats requested: %s", stats)
    return jsonify(stats)

@app.route('/api/query', methods=['POST'])
def query():
    """Handle natural language queries using RAG with web search enhancement"""
    data = request.json
    query_text = data.get('query', '')
    enable_web_search = data.get('web_search', True)

    if not query_text:
        return jsonify({'error': 'Query text is required'}), 400

    logger.info("Query received: %s (web_search=%s)", query_text, enable_web_search)

    # Query RAG system first
    result = ollama_client.query_rag(query_text, rag_system)

    # Get subgraph with relevant nodes and their connections
    if result['relevant_nodes']:
        subgraph = rag_system.get_subgraph(result['relevant_nodes'], depth=1)
        from networkx.readwrite import json_graph
        graph_data = json_graph.node_link_data(subgraph)
    else:
        graph_data = {'nodes': [], 'links': []}

    # Perform web search if enabled
    research_links = []
    new_entities_added = False

    if enable_web_search:
        try:
            logger.info("Performing web search for: %s", query_text)

            # Search Swisscows
            search_results = web_searcher.search(query_text, max_results=10)

            if search_results:
                logger.info("Found %d search results", len(search_results))

                # Filter relevant URLs using Ollama
                relevant_urls = ollama_client.filter_relevant_urls(query_text, search_results, max_urls=3)

                if relevant_urls:
                    logger.info("Filtered to %d relevant URLs", len(relevant_urls))

                    # Fetch and summarize content
                    for url_info in relevant_urls:
                        url_content = web_searcher.fetch_url_content(url_info['url'])

                        if url_content:
                            # Summarize using Ollama
                            summary = ollama_client.summarize_url_content(query_text, url_content)

                            research_links.append({
                                'url': summary['url'],
                                'title': summary['title'],
                                'summary': summary['summary'],
                                'key_facts': summary['key_facts'],
                                'relevance_score': url_info.get('relevance_score', 0)
                            })

                            # Extract entities and add to graph
                            if summary['entities']:
                                for entity in summary['entities']:
                                    entity_clean = entity.strip().lower()
                                    if len(entity_clean) > 2:
                                        entity_id = f"web_{entity_clean.replace(' ', '_')}"

                                        # Check if entity already exists
                                        if entity_id not in rag_system.graph:
                                            # Determine entity type
                                            entity_type = 'entity'
                                            if any(keyword in entity_clean for keyword in ['disease', 'cancer', 'diabetes', 'syndrome']):
                                                entity_type = 'disease'
                                            elif any(keyword in entity_clean for keyword in ['gene', 'protein']):
                                                entity_type = 'gene'
                                            elif any(keyword in entity_clean for keyword in ['drug', 'inhibitor', 'therapy']):
                                                entity_type = 'compound'
                                            elif any(keyword in entity_clean for keyword in ['pathway']):
                                                entity_type = 'pathway'

                                            # Add to graph
                                            rag_system.add_document(
                                                entity_id,
                                                f"{entity_type.title()}: {entity} (from web research)",
                                                {
                                                    'name': entity,
                                                    'source': 'web_research',
                                                    'source_url': summary['url'],
                                                    'query': query_text
                                                },
                                                entity_type
                                            )
                                            new_entities_added = True

                                            # Link to query-relevant nodes
                                            for relevant_node in result['relevant_nodes'][:3]:
                                                if relevant_node in rag_system.graph:
                                                    rag_system.add_relationship(
                                                        relevant_node,
                                                        entity_id,
                                                        'related_to_web_research',
                                                        {
                                                            'source': 'web_research',
                                                            'url': summary['url'],
                                                            'query': query_text
                                                        }
                                                    )

                    # Save if new entities added
                    if new_entities_added:
                        rag_system.save()
                        logger.info("Added new entities from web research to graph")

                        # Update graph data with new entities
                        if result['relevant_nodes']:
                            subgraph = rag_system.get_subgraph(result['relevant_nodes'], depth=1)
                            graph_data = json_graph.node_link_data(subgraph)

        except Exception as e:
            logger.error("Error during web search: %s", str(e))
            # Continue without web search results

    return jsonify({
        'query': query_text,
        'response': result['response'],
        'sources': result['sources'],
        'source_details': result['source_details'],
        'relevant_nodes': result['relevant_nodes'],
        'graph_data': graph_data,
        'research_links': research_links,
        'new_entities_added': new_entities_added
    })

@app.route('/api/fetch_data', methods=['POST'])
def fetch_data():
    """Fetch new data from external APIs and update RAG"""
    data = request.json
    source = data.get('source', 'all')

    logger.info("Data fetch requested for source: %s", source)

    fetched_data = {}

    if source == 'all' or source == 'hetio':
        diseases = data_fetcher.hetio.fetch_diseases()[:10]
        compounds = data_fetcher.hetio.fetch_compounds()[:10]

        disease_count = 0
        compound_count = 0
        relationship_count = 0

        for disease in diseases:
            disease_id = f"hetio_disease_{disease.get('identifier', disease.get('id', 'unknown'))}"
            disease_name = disease.get('name', 'Unknown')
            rag_system.add_document(
                disease_id,
                f"Disease: {disease_name} (HetIO)",
                disease,
                'disease'
            )
            disease_count += 1

            # Fetch relationships for this disease
            try:
                source_identifier = disease.get('identifier', disease.get('id'))
                if source_identifier:
                    # Try to fetch disease-gene associations
                    relationships = data_fetcher.hetio.fetch_relationships(source_identifier, 'DaG')
                    for rel in relationships[:5]:
                        target_id = f"hetio_gene_{rel.get('target_id', 'unknown')}"
                        target_name = rel.get('target_name', 'Unknown')

                        if target_id not in rag_system.graph:
                            rag_system.add_document(
                                target_id,
                                f"Gene: {target_name} (HetIO)",
                                {'id': target_id, 'name': target_name, 'source': 'hetio'},
                                'gene'
                            )

                        rag_system.add_relationship(
                            disease_id,
                            target_id,
                            'associates_gene',
                            {'source': 'hetio'}
                        )
                        relationship_count += 1
            except Exception as e:
                logger.debug("Could not fetch relationships for %s: %s", disease_name, str(e))

        for compound in compounds:
            compound_id = f"hetio_compound_{compound.get('identifier', compound.get('id', 'unknown'))}"
            compound_name = compound.get('name', 'Unknown')
            rag_system.add_document(
                compound_id,
                f"Compound: {compound_name} (HetIO)",
                compound,
                'compound'
            )
            compound_count += 1

        fetched_data['hetio'] = {
            'diseases': disease_count,
            'compounds': compound_count,
            'relationships': relationship_count
        }

    if source == 'all' or source == 'kegg':
        pathways = data_fetcher.kegg.fetch_pathway_list()[:10]

        for pathway_line in pathways:
            parts = pathway_line.split('\t')
            if len(parts) >= 2:
                pathway_id = parts[0]
                pathway_name = parts[1]
                rag_system.add_document(
                    pathway_id,
                    f"Pathway: {pathway_name}",
                    {'id': pathway_id, 'name': pathway_name},
                    'pathway'
                )

        fetched_data['kegg'] = {
            'pathways': len(pathways)
        }

    rag_system.save()
    logger.info("Data fetched and saved: %s", fetched_data)

    return jsonify({
        'status': 'success',
        'fetched': fetched_data
    })

@app.route('/api/graph', methods=['GET'])
def get_graph():
    """Get graph data for visualization"""
    node_type = request.args.get('type', None)
    limit = int(request.args.get('limit', 100))

    graph = rag_system.graph
    nodes = list(graph.nodes(data=True))

    if node_type:
        nodes = [(n, d) for n, d in nodes if d.get('type') == node_type]

    nodes = nodes[:limit]
    node_ids = set([n for n, d in nodes])

    # Get all edges between the selected nodes plus their direct neighbors
    subgraph_nodes = set(node_ids)
    for node_id in list(node_ids):
        if node_id in graph:
            # Add neighbors to show connections
            neighbors = list(graph.neighbors(node_id)) + list(graph.predecessors(node_id))
            subgraph_nodes.update(neighbors[:5])  # Limit neighbors to avoid overcrowding

    subgraph = graph.subgraph(subgraph_nodes).copy()

    graph_data = json_graph.node_link_data(subgraph)

    logger.info("Graph data requested: %d nodes, %d edges",
               len(graph_data['nodes']), len(graph_data['links']))

    return jsonify(graph_data)

@app.route('/api/cluster', methods=['POST'])
def cluster_nodes():
    """Perform clustering on nodes"""
    data = request.json
    node_type = data.get('type', None)
    method = data.get('method', 'kmeans')
    n_clusters = data.get('n_clusters', 5)
    use_semantic = data.get('semantic', False)

    graph = rag_system.graph
    nodes = list(graph.nodes())

    if node_type:
        nodes = [n for n in nodes if graph.nodes[n].get('type') == node_type]

    if len(nodes) == 0:
        return jsonify({'error': 'No nodes found'}), 400

    if use_semantic:
        cluster_map = clustering_analyzer.cluster_semantic(
            rag_system, nodes, n_clusters
        )
    else:
        cluster_map = clustering_analyzer.cluster_and_annotate(
            graph, nodes, method, n_clusters
        )

    for node_id, cluster_id in cluster_map.items():
        if node_id in graph:
            graph.nodes[node_id]['cluster'] = cluster_id

    rag_system.save()

    logger.info("Clustering completed: %d nodes in %d clusters",
               len(cluster_map), len(set(cluster_map.values())))

    return jsonify({
        'status': 'success',
        'clusters': cluster_map,
        'n_clusters': len(set(cluster_map.values())),
        'method': 'semantic' if use_semantic else method
    })

@app.route('/api/filter', methods=['POST'])
def filter_nodes():
    """Filter nodes by criteria"""
    data = request.json
    keyword = data.get('keyword', '')
    node_type = data.get('type', None)

    graph = rag_system.graph
    nodes = list(graph.nodes())

    if node_type:
        nodes = [n for n in nodes if graph.nodes[n].get('type') == node_type]

    if keyword:
        nodes = clustering_analyzer.filter_by_keyword(
            graph, nodes, keyword, ['name', 'identifier', 'id']
        )

    node_data = []
    for node_id in nodes[:100]:
        node_data.append({
            'id': node_id,
            'data': dict(graph.nodes[node_id])
        })

    logger.info("Filter applied: %d nodes match criteria", len(nodes))

    return jsonify({
        'status': 'success',
        'nodes': node_data,
        'count': len(nodes)
    })

@app.route('/api/neighbors', methods=['GET'])
def get_neighbors():
    """Get neighbors of a specific node"""
    node_id = request.args.get('node_id')

    if not node_id:
        return jsonify({'error': 'node_id is required'}), 400

    neighbors = rag_system.get_node_neighbors(node_id)

    logger.info("Neighbors requested for node %s: %d found", node_id, len(neighbors))

    return jsonify({
        'node_id': node_id,
        'neighbors': neighbors
    })

@app.route('/api/path', methods=['POST'])
def find_path():
    """Find paths between two nodes"""
    data = request.json
    source = data.get('source')
    target = data.get('target')
    max_length = data.get('max_length', 4)

    if not source or not target:
        return jsonify({'error': 'source and target are required'}), 400

    paths = rag_system.find_paths(source, target, max_length)

    logger.info("Path search from %s to %s: %d paths found", source, target, len(paths))

    return jsonify({
        'source': source,
        'target': target,
        'paths': paths,
        'count': len(paths)
    })

def main():
    """Main entry point"""
    host = config['server']['host']
    port = config['server']['port']
    debug = config['server']['debug']

    logger.info("Starting server on %s:%d", host, port)
    app.run(host=host, port=port, debug=debug)

if __name__ == '__main__':
    main()
