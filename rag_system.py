import chromadb
from chromadb.config import Settings
import logging
import json
import os
from typing import List, Dict, Optional
import networkx as nx
import pickle

logger = logging.getLogger(__name__)

class RAGGraphSystem:
    """RAG system combining vector database with graph structure"""

    def __init__(self, config):
        self.config = config
        self.vector_db_path = config['paths']['vector_db']
        self.graph_db_path = config['paths']['graph_db']

        os.makedirs(self.vector_db_path, exist_ok=True)
        os.makedirs(os.path.dirname(self.graph_db_path), exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=self.vector_db_path,
            settings=Settings(anonymized_telemetry=False)
        )

        self.collection = self.client.get_or_create_collection(
            name="medical_knowledge",
            metadata={"description": "Medical and disease knowledge graph"}
        )

        self.graph = nx.MultiDiGraph()
        self._load_graph()

        logger.info("RAGGraphSystem initialized with vector DB at %s", self.vector_db_path)

    def _load_graph(self):
        """Load graph from disk if it exists"""
        if os.path.exists(self.graph_db_path):
            with open(self.graph_db_path, 'rb') as f:
                self.graph = pickle.load(f)
            logger.info("Loaded graph with %d nodes and %d edges",
                       self.graph.number_of_nodes(),
                       self.graph.number_of_edges())
        else:
            logger.info("Starting with empty graph")

    def _save_graph(self):
        """Save graph to disk"""
        with open(self.graph_db_path, 'wb') as f:
            pickle.dump(self.graph, f)
        logger.info("Saved graph with %d nodes and %d edges",
                   self.graph.number_of_nodes(),
                   self.graph.number_of_edges())

    def add_document(self, doc_id: str, text: str, metadata: Dict, node_type: str):
        """Add a document to both vector DB and graph"""
        self.collection.add(
            documents=[text],
            metadatas=[metadata],
            ids=[doc_id]
        )

        self.graph.add_node(doc_id, type=node_type, **metadata)
        logger.debug("Added document %s of type %s", doc_id, node_type)

    def add_relationship(self, source_id: str, target_id: str, relation_type: str, metadata: Optional[Dict] = None):
        """Add a relationship between two entities in the graph"""
        if metadata is None:
            metadata = {}

        self.graph.add_edge(source_id, target_id, type=relation_type, **metadata)
        logger.debug("Added relationship %s between %s and %s", relation_type, source_id, target_id)

    def query_similar(self, query_text: str, n_results: int = 10) -> List[Dict]:
        """Query for similar documents using vector similarity"""
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )

        formatted_results = []
        if results['ids'] and len(results['ids']) > 0:
            for i, doc_id in enumerate(results['ids'][0]):
                formatted_results.append({
                    'id': doc_id,
                    'document': results['documents'][0][i] if results['documents'] else None,
                    'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                    'distance': results['distances'][0][i] if results['distances'] else None
                })

        logger.info("Query returned %d results", len(formatted_results))
        return formatted_results

    def get_node_neighbors(self, node_id: str, relation_types: Optional[List[str]] = None) -> List[Dict]:
        """Get neighbors of a node in the graph, optionally filtered by relation type"""
        if node_id not in self.graph:
            logger.warning("Node %s not found in graph", node_id)
            return []

        neighbors = []
        for neighbor in self.graph.neighbors(node_id):
            edges = self.graph.get_edge_data(node_id, neighbor)
            for key, edge_data in edges.items():
                if relation_types is None or edge_data.get('type') in relation_types:
                    neighbors.append({
                        'node_id': neighbor,
                        'relation': edge_data.get('type'),
                        'edge_metadata': edge_data,
                        'node_metadata': dict(self.graph.nodes[neighbor])
                    })

        logger.debug("Found %d neighbors for node %s", len(neighbors), node_id)
        return neighbors

    def find_paths(self, source_id: str, target_id: str, max_length: int = 4) -> List[List[str]]:
        """Find paths between two nodes in the graph"""
        if source_id not in self.graph or target_id not in self.graph:
            logger.warning("Source or target node not found in graph")
            return []

        try:
            paths = list(nx.all_simple_paths(self.graph, source_id, target_id, cutoff=max_length))
            logger.info("Found %d paths between %s and %s", len(paths), source_id, target_id)
            return paths
        except nx.NetworkXNoPath:
            logger.info("No path found between %s and %s", source_id, target_id)
            return []

    def get_subgraph(self, node_ids: List[str], depth: int = 1) -> nx.MultiDiGraph:
        """Extract a subgraph centered on given nodes with specified depth"""
        nodes_to_include = set(node_ids)

        for node_id in node_ids:
            if node_id in self.graph:
                for _ in range(depth):
                    new_nodes = set()
                    for n in nodes_to_include:
                        if n in self.graph:
                            new_nodes.update(self.graph.predecessors(n))
                            new_nodes.update(self.graph.successors(n))
                    nodes_to_include.update(new_nodes)

        subgraph = self.graph.subgraph(nodes_to_include).copy()
        logger.info("Extracted subgraph with %d nodes and %d edges",
                   subgraph.number_of_nodes(),
                   subgraph.number_of_edges())
        return subgraph

    def save(self):
        """Persist both vector DB and graph to disk"""
        self._save_graph()
        logger.info("RAG system saved to disk")

    def get_statistics(self) -> Dict:
        """Get statistics about the RAG system"""
        stats = {
            'graph_nodes': self.graph.number_of_nodes(),
            'graph_edges': self.graph.number_of_edges(),
            'vector_documents': self.collection.count(),
            'node_types': {}
        }

        for node, data in self.graph.nodes(data=True):
            node_type = data.get('type', 'unknown')
            stats['node_types'][node_type] = stats['node_types'].get(node_type, 0) + 1

        return stats
