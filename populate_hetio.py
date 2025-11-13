import json
import logging
from rate_limiter import RateLimiterManager
from data_fetchers import DataFetcherManager
from rag_system import RAGGraphSystem
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config(config_path='config.json'):
    with open(config_path, 'r') as f:
        return json.load(f)

def populate_hetio_relationships(data_fetcher, rag_system, limit=10):
    """
    Fetch HetIO disease-compound relationships and add to graph

    Note: HetIO API endpoints have changed. This function attempts to use
    the available API but may encounter 404 errors.
    """
    logger.info("Attempting to fetch HetIO relationships...")

    # Try to fetch diseases first
    diseases = data_fetcher.hetio.fetch_diseases()[:limit]

    if not diseases:
        logger.warning("No diseases fetched from HetIO - API may be unavailable")
        return

    relationships_added = 0

    # For each disease, try to fetch its relationships
    for disease in diseases:
        disease_id = f"hetio_disease_{disease.get('identifier', disease.get('id', 'unknown'))}"
        disease_name = disease.get('name', 'Unknown')

        # Add disease node if not exists
        if disease_id not in rag_system.graph:
            rag_system.add_document(
                disease_id,
                f"Disease: {disease_name} (HetIO)",
                {
                    'id': disease_id,
                    'name': disease_name,
                    'source': 'hetio',
                    'category': 'disease'
                },
                'disease'
            )

        # Try different metaedge types to fetch relationships
        metaedges = [
            'DaG',  # Disease associates Gene
            'CtD',  # Compound treats Disease
            'CbG',  # Compound binds Gene
        ]

        for metaedge in metaedges:
            try:
                source_identifier = disease.get('identifier', disease.get('id'))
                if not source_identifier:
                    continue

                relationships = data_fetcher.hetio.fetch_relationships(
                    source_identifier,
                    metaedge
                )

                for rel in relationships:
                    target_id = f"hetio_{rel.get('target_node_type')}_{rel.get('target_id', 'unknown')}"
                    target_name = rel.get('target_name', 'Unknown')
                    target_type = rel.get('target_node_type', 'entity').lower()

                    # Add target node if not exists
                    if target_id not in rag_system.graph:
                        rag_system.add_document(
                            target_id,
                            f"{target_type.title()}: {target_name} (HetIO)",
                            {
                                'id': target_id,
                                'name': target_name,
                                'source': 'hetio',
                                'category': target_type
                            },
                            target_type
                        )

                    # Add relationship edge
                    rag_system.add_relationship(
                        disease_id,
                        target_id,
                        metaedge,
                        {'source': 'hetio', 'edge_type': metaedge}
                    )

                    relationships_added += 1

                    logger.debug("Added %s relationship: %s -> %s",
                               metaedge, disease_id, target_id)

            except Exception as e:
                logger.debug("Could not fetch %s relationships for %s: %s",
                           metaedge, disease_name, str(e))
                continue

        time.sleep(0.5)

    logger.info("Added %d HetIO relationships", relationships_added)
    return relationships_added

def main():
    """Populate HetIO relationships"""
    config = load_config()
    rate_limiter = RateLimiterManager(config['api_limits'])
    data_fetcher = DataFetcherManager(rate_limiter, config)
    rag_system = RAGGraphSystem(config)

    logger.info("Starting HetIO relationship population...")

    initial_edges = rag_system.graph.number_of_edges()
    logger.info("Initial graph has %d edges", initial_edges)

    try:
        relationships_added = populate_hetio_relationships(data_fetcher, rag_system, limit=5)

        rag_system.save()

        final_edges = rag_system.graph.number_of_edges()
        logger.info("Final graph has %d edges (added %d)", final_edges, final_edges - initial_edges)

        stats = rag_system.get_statistics()
        logger.info("Final statistics: %s", stats)

    except Exception as e:
        logger.error("Error populating HetIO relationships: %s", str(e))
        logger.info("This is expected if HetIO API endpoints have changed")

if __name__ == '__main__':
    main()
