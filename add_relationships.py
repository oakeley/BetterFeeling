import json
import logging
from rag_system import RAGGraphSystem

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config(config_path='config.json'):
    with open(config_path, 'r') as f:
        return json.load(f)

def add_disease_relationships(rag_system):
    """Add more relationships between diseases, targets, and pathways"""

    # Type 2 Diabetes relationships
    if 'sample_diabetes_type2' in rag_system.graph:
        rag_system.add_relationship('sample_diabetes_type2', 'target_GLP1R', 'treated_by', {'evidence': 'clinical'})
        logger.info("Added diabetes -> GLP1R relationship")

    # Lung cancer relationships
    if 'sample_cancer_lung' in rag_system.graph and 'target_EGFR' in rag_system.graph:
        rag_system.add_relationship('sample_cancer_lung', 'target_EGFR', 'has_target', {'evidence': 'clinical'})
        logger.info("Added lung cancer -> EGFR relationship")

    # Alzheimer's relationships
    if 'sample_alzheimers' in rag_system.graph and 'target_BACE1' in rag_system.graph:
        rag_system.add_relationship('sample_alzheimers', 'target_BACE1', 'has_target', {'evidence': 'preclinical'})
        logger.info("Added Alzheimer's -> BACE1 relationship")

    # Add disease-disease relationships based on shared mechanisms
    disease_clusters = {
        'metabolic': ['sample_obesity', 'sample_diabetes_type2', 'sample_hypertension'],
        'neurodegenerative': ['sample_alzheimers', 'sample_parkinsons'],
        'cancer': ['sample_cancer_lung'],
        'autoimmune': ['sample_rheumatoid_arthritis'],
        'psychiatric': ['sample_depression']
    }

    for cluster_name, disease_list in disease_clusters.items():
        # Create shared mechanism relationships within clusters
        for i, disease1 in enumerate(disease_list):
            for disease2 in disease_list[i+1:]:
                if disease1 in rag_system.graph and disease2 in rag_system.graph:
                    rag_system.add_relationship(
                        disease1,
                        disease2,
                        'shares_mechanism',
                        {'mechanism': cluster_name, 'bidirectional': True}
                    )
                    logger.info(f"Added shared mechanism: {disease1} <-> {disease2}")

    # Add KEGG disease relationships to sample diseases
    kegg_diseases = [n for n, d in rag_system.graph.nodes(data=True)
                     if d.get('type') == 'disease' and d.get('source') == 'kegg']

    for kegg_disease in kegg_diseases[:5]:
        # Link some KEGG diseases to our curated diseases based on keywords
        disease_data = rag_system.graph.nodes[kegg_disease]
        disease_name = disease_data.get('name', '').lower()

        if 'cancer' in disease_name or 'leukemia' in disease_name:
            if 'sample_cancer_lung' in rag_system.graph:
                rag_system.add_relationship(
                    kegg_disease,
                    'sample_cancer_lung',
                    'related_to',
                    {'similarity': 'cancer_type'}
                )
                logger.info(f"Linked KEGG disease {kegg_disease} to lung cancer")

    # Add pathway-disease relationships
    pathways = [n for n, d in rag_system.graph.nodes(data=True) if d.get('type') == 'pathway']

    for pathway in pathways[:5]:
        pathway_data = rag_system.graph.nodes[pathway]
        pathway_name = pathway_data.get('name', '').lower()

        # Link metabolic pathways to metabolic diseases
        if 'sample_diabetes_type2' in rag_system.graph:
            rag_system.add_relationship(
                pathway,
                'sample_diabetes_type2',
                'involved_in',
                {'pathway_role': 'metabolic'}
            )
            logger.info(f"Linked pathway {pathway} to diabetes")

    rag_system.save()
    logger.info("All relationships added and saved")

def main():
    config = load_config()
    rag_system = RAGGraphSystem(config)

    logger.info(f"Initial state: {rag_system.graph.number_of_nodes()} nodes, {rag_system.graph.number_of_edges()} edges")

    add_disease_relationships(rag_system)

    stats = rag_system.get_statistics()
    logger.info(f"Final state: {stats}")

if __name__ == '__main__':
    main()
