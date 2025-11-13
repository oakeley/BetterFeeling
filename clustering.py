import numpy as np
from sklearn.cluster import KMeans, DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import logging
from typing import List, Dict, Optional
import networkx as nx

logger = logging.getLogger(__name__)

class ClusteringAnalyzer:
    """Performs clustering and filtering on disease and drug data"""

    def __init__(self, config):
        self.config = config
        logger.info("ClusteringAnalyzer initialized")

    def extract_features_from_graph(self, graph: nx.MultiDiGraph, node_ids: List[str]) -> np.ndarray:
        """Extract numerical features from graph nodes for clustering"""
        features = []

        for node_id in node_ids:
            if node_id not in graph:
                continue

            node_data = graph.nodes[node_id]
            feature_vector = [
                graph.degree(node_id),
                graph.in_degree(node_id),
                graph.out_degree(node_id),
                len(list(graph.neighbors(node_id)))
            ]

            features.append(feature_vector)

        return np.array(features)

    def cluster_kmeans(self, features: np.ndarray, n_clusters: int = 5) -> np.ndarray:
        """Perform K-means clustering on feature vectors"""
        if len(features) < n_clusters:
            logger.warning("Number of samples less than clusters, using n_clusters=%d", len(features))
            n_clusters = max(1, len(features))

        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features)

        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(features_scaled)

        logger.info("K-means clustering produced %d clusters", n_clusters)
        return labels

    def cluster_dbscan(self, features: np.ndarray, eps: float = 0.5, min_samples: int = 3) -> np.ndarray:
        """Perform DBSCAN clustering for density-based grouping"""
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features)

        dbscan = DBSCAN(eps=eps, min_samples=min_samples)
        labels = dbscan.fit_predict(features_scaled)

        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise = list(labels).count(-1)

        logger.info("DBSCAN clustering found %d clusters and %d noise points", n_clusters, n_noise)
        return labels

    def reduce_dimensions(self, features: np.ndarray, n_components: int = 2) -> np.ndarray:
        """Reduce feature dimensions using PCA for visualization"""
        if features.shape[1] < n_components:
            logger.warning("Feature dimension less than target components")
            n_components = features.shape[1]

        pca = PCA(n_components=n_components)
        reduced = pca.fit_transform(features)

        variance_explained = sum(pca.explained_variance_ratio_)
        logger.info("PCA reduced to %d dimensions, variance explained: %.2f%%",
                   n_components, variance_explained * 100)
        return reduced

    def filter_by_attribute(self, graph: nx.MultiDiGraph, node_ids: List[str],
                           attribute: str, value) -> List[str]:
        """Filter nodes by a specific attribute value"""
        filtered = []
        for node_id in node_ids:
            if node_id in graph:
                node_data = graph.nodes[node_id]
                if attribute in node_data and node_data[attribute] == value:
                    filtered.append(node_id)

        logger.info("Filtered %d nodes by attribute %s=%s", len(filtered), attribute, value)
        return filtered

    def filter_by_keyword(self, graph: nx.MultiDiGraph, node_ids: List[str],
                         keyword: str, search_fields: List[str]) -> List[str]:
        """Filter nodes by keyword search in specified fields"""
        keyword_lower = keyword.lower()
        filtered = []

        for node_id in node_ids:
            if node_id in graph:
                node_data = graph.nodes[node_id]
                for field in search_fields:
                    if field in node_data:
                        field_value = str(node_data[field]).lower()
                        if keyword_lower in field_value:
                            filtered.append(node_id)
                            break

        logger.info("Filtered %d nodes by keyword '%s'", len(filtered), keyword)
        return filtered

    def identify_shared_mechanisms(self, graph: nx.MultiDiGraph,
                                  node_ids: List[str],
                                  relation_type: str) -> Dict[str, List[str]]:
        """Identify groups of nodes sharing common mechanisms via relation type"""
        mechanism_groups = {}

        for node_id in node_ids:
            if node_id not in graph:
                continue

            for neighbor in graph.neighbors(node_id):
                edges = graph.get_edge_data(node_id, neighbor)
                for key, edge_data in edges.items():
                    if edge_data.get('type') == relation_type:
                        if neighbor not in mechanism_groups:
                            mechanism_groups[neighbor] = []
                        mechanism_groups[neighbor].append(node_id)

        mechanism_groups = {k: v for k, v in mechanism_groups.items() if len(v) > 1}
        logger.info("Identified %d shared mechanisms", len(mechanism_groups))
        return mechanism_groups

    def cluster_and_annotate(self, graph: nx.MultiDiGraph, node_ids: List[str],
                            method: str = 'kmeans', n_clusters: int = 5) -> Dict[str, int]:
        """Cluster nodes and return cluster assignments"""
        features = self.extract_features_from_graph(graph, node_ids)

        if len(features) == 0:
            logger.warning("No features extracted for clustering")
            return {}

        if method == 'kmeans':
            labels = self.cluster_kmeans(features, n_clusters)
        elif method == 'dbscan':
            labels = self.cluster_dbscan(features)
        else:
            logger.error("Unknown clustering method: %s", method)
            return {}

        cluster_map = {}
        for i, node_id in enumerate(node_ids):
            if i < len(labels):
                cluster_map[node_id] = int(labels[i])

        return cluster_map

    def cluster_semantic(self, rag_system, node_ids: List[str], n_clusters: int = 5) -> Dict[str, int]:
        """
        Cluster nodes by semantic similarity using vector embeddings

        Uses ChromaDB embeddings to group nodes by meaning rather than graph topology
        """
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
        import numpy as np

        if len(node_ids) < 2:
            logger.warning("Need at least 2 nodes for semantic clustering")
            return {node_ids[0]: 0} if node_ids else {}

        # Get embeddings from ChromaDB
        embeddings = []
        valid_node_ids = []

        for node_id in node_ids:
            try:
                result = rag_system.collection.get(ids=[node_id], include=['embeddings'])
                if result and result['embeddings'] and len(result['embeddings']) > 0:
                    embeddings.append(result['embeddings'][0])
                    valid_node_ids.append(node_id)
            except Exception as e:
                logger.warning("Could not get embedding for node %s: %s", node_id, str(e))
                continue

        if len(embeddings) == 0:
            logger.error("No embeddings found for semantic clustering")
            return {}

        embeddings_array = np.array(embeddings)

        # Adjust n_clusters if we have fewer nodes
        actual_n_clusters = min(n_clusters, len(valid_node_ids))

        if actual_n_clusters < 2:
            logger.warning("Only %d valid nodes, assigning all to cluster 0", len(valid_node_ids))
            return {node_id: 0 for node_id in valid_node_ids}

        # Standardize embeddings
        scaler = StandardScaler()
        embeddings_scaled = scaler.fit_transform(embeddings_array)

        # Perform K-means clustering on embeddings
        kmeans = KMeans(n_clusters=actual_n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(embeddings_scaled)

        cluster_map = {}
        for i, node_id in enumerate(valid_node_ids):
            cluster_map[node_id] = int(labels[i])

        logger.info("Semantic clustering created %d clusters from %d nodes",
                   actual_n_clusters, len(valid_node_ids))

        return cluster_map
