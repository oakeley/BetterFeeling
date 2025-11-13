import json
import logging
from rate_limiter import RateLimiterManager
from data_fetchers import DataFetcherManager
from rag_system import RAGGraphSystem
from kegg_parser import KEGGParser
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
kegg_parser = KEGGParser()

def load_config(config_path='config.json'):
    """Load configuration from JSON file"""
    with open(config_path, 'r') as f:
        return json.load(f)

def populate_kegg_diseases(data_fetcher, rag_system, limit=20):
    """Populate RAG system with KEGG disease data"""
    logger.info("Fetching KEGG diseases...")

    disease_list = data_fetcher.kegg.fetch_disease_list()[:limit]

    for disease_line in disease_list:
        parts = disease_line.split('\t')
        if len(parts) >= 2:
            disease_id = parts[0]
            disease_name = parts[1]

            logger.info("Fetching details for disease: %s", disease_id)
            disease_info = data_fetcher.kegg.fetch_disease_info(disease_id)

            if disease_info:
                rag_system.add_document(
                    disease_id,
                    f"Disease: {disease_name}\n{disease_info}",
                    {
                        'id': disease_id,
                        'name': disease_name,
                        'source': 'kegg',
                        'category': 'disease'
                    },
                    'disease'
                )

                # Parse and link genes
                genes = kegg_parser.parse_disease_genes(disease_info)
                for gene in genes:
                    gene_id = f"gene_{gene['gene_symbol']}"

                    # Add gene node if not exists
                    if gene_id not in rag_system.graph:
                        rag_system.add_document(
                            gene_id,
                            f"Gene: {gene['gene_symbol']} - HSA:{','.join(gene['gene_ids'])}",
                            {
                                'id': gene_id,
                                'name': gene['gene_symbol'],
                                'hsa_ids': ','.join(gene['gene_ids']),
                                'source': 'kegg',
                                'category': 'gene'
                            },
                            'gene'
                        )

                    # Link disease to gene
                    rag_system.add_relationship(
                        disease_id,
                        gene_id,
                        'involves_gene',
                        {'relationship_type': gene['relationship'], 'source': 'kegg'}
                    )

                # Parse and link pathways
                pathways = kegg_parser.parse_disease_pathways(disease_info)
                for pathway in pathways:
                    pathway_id = pathway['pathway_id']

                    # Add pathway node if not exists
                    if pathway_id not in rag_system.graph:
                        rag_system.add_document(
                            pathway_id,
                            f"Pathway: {pathway['pathway_name']}",
                            {
                                'id': pathway_id,
                                'name': pathway['pathway_name'],
                                'source': 'kegg',
                                'category': 'pathway'
                            },
                            'pathway'
                        )

                    # Link disease to pathway
                    rag_system.add_relationship(
                        disease_id,
                        pathway_id,
                        'involves_pathway',
                        {'source': 'kegg'}
                    )

            time.sleep(0.5)

    logger.info("Added %d KEGG diseases", len(disease_list))

def populate_kegg_pathways(data_fetcher, rag_system, limit=30):
    """Populate RAG system with KEGG pathway data"""
    logger.info("Fetching KEGG pathways...")

    pathway_list = data_fetcher.kegg.fetch_pathway_list()[:limit]

    for pathway_line in pathway_list:
        parts = pathway_line.split('\t')
        if len(parts) >= 2:
            pathway_id = parts[0]
            pathway_name = parts[1]

            if 'disease' in pathway_name.lower() or 'cancer' in pathway_name.lower() or 'metabolic' in pathway_name.lower():
                logger.info("Fetching details for pathway: %s", pathway_id)
                pathway_info = data_fetcher.kegg.fetch_pathway_info(pathway_id)

                if pathway_info:
                    rag_system.add_document(
                        pathway_id,
                        f"Pathway: {pathway_name}\n{pathway_info}",
                        {
                            'id': pathway_id,
                            'name': pathway_name,
                            'source': 'kegg',
                            'category': 'pathway'
                        },
                        'pathway'
                    )

                time.sleep(0.5)

    logger.info("Added KEGG pathways")

def populate_sample_diseases(rag_system):
    """Add sample disease data for common conditions"""
    logger.info("Adding sample disease data...")

    sample_diseases = [
        {
            'id': 'obesity',
            'name': 'Obesity',
            'description': 'Obesity is a chronic disease characterized by excess body fat. Risk factors include genetics, diet, physical inactivity, and metabolic disorders. Associated with type 2 diabetes, cardiovascular disease, and certain cancers.',
            'targets': ['leptin', 'adiponectin', 'insulin signaling', 'lipid metabolism'],
            'therapies': ['GLP-1 agonists', 'lifestyle intervention', 'bariatric surgery', 'orlistat']
        },
        {
            'id': 'diabetes_type2',
            'name': 'Type 2 Diabetes',
            'description': 'Type 2 diabetes is a metabolic disorder characterized by insulin resistance and impaired glucose metabolism. Major complications include cardiovascular disease, nephropathy, and neuropathy.',
            'targets': ['insulin receptor', 'GLUT4', 'glucagon', 'incretin system'],
            'therapies': ['metformin', 'GLP-1 agonists', 'SGLT2 inhibitors', 'insulin']
        },
        {
            'id': 'hypertension',
            'name': 'Hypertension',
            'description': 'Hypertension is sustained elevation of blood pressure. Risk factors include obesity, sodium intake, stress, and genetics. Major cause of stroke, heart attack, and kidney disease.',
            'targets': ['renin-angiotensin system', 'calcium channels', 'beta receptors', 'endothelin'],
            'therapies': ['ACE inhibitors', 'ARBs', 'calcium channel blockers', 'beta blockers', 'diuretics']
        },
        {
            'id': 'alzheimers',
            'name': "Alzheimer's Disease",
            'description': "Alzheimer's disease is a progressive neurodegenerative disorder causing memory loss and cognitive decline. Characterized by amyloid plaques and tau tangles. Unmet need for disease-modifying therapies.",
            'targets': ['amyloid beta', 'tau protein', 'BACE1', 'acetylcholine', 'neuroinflammation'],
            'therapies': ['cholinesterase inhibitors', 'memantine', 'aducanumab', 'lecanemab']
        },
        {
            'id': 'cancer_lung',
            'name': 'Lung Cancer',
            'description': 'Lung cancer is the leading cause of cancer death worldwide. Main types are non-small cell lung cancer and small cell lung cancer. Risk factors include smoking, radon exposure, and air pollution.',
            'targets': ['EGFR', 'ALK', 'ROS1', 'PD-L1', 'KRAS'],
            'therapies': ['platinum chemotherapy', 'EGFR inhibitors', 'ALK inhibitors', 'immunotherapy', 'surgery']
        },
        {
            'id': 'parkinsons',
            'name': "Parkinson's Disease",
            'description': "Parkinson's disease is a neurodegenerative disorder affecting movement control. Caused by loss of dopaminergic neurons in substantia nigra. Unmet need for neuroprotective therapies.",
            'targets': ['dopamine receptors', 'MAO-B', 'COMT', 'alpha-synuclein', 'mitochondrial function'],
            'therapies': ['levodopa', 'dopamine agonists', 'MAO-B inhibitors', 'COMT inhibitors', 'deep brain stimulation']
        },
        {
            'id': 'rheumatoid_arthritis',
            'name': 'Rheumatoid Arthritis',
            'description': 'Rheumatoid arthritis is an autoimmune disease causing joint inflammation and damage. Characterized by synovial inflammation and bone erosion. Shared autoimmune mechanisms with other diseases.',
            'targets': ['TNF-alpha', 'IL-6', 'JAK', 'B cells', 'T cells'],
            'therapies': ['methotrexate', 'TNF inhibitors', 'IL-6 inhibitors', 'JAK inhibitors', 'rituximab']
        },
        {
            'id': 'depression',
            'name': 'Major Depressive Disorder',
            'description': 'Major depressive disorder is characterized by persistent sadness and loss of interest. Involves dysregulation of monoaminergic neurotransmission. Significant unmet need for rapid-acting treatments.',
            'targets': ['serotonin transporter', 'norepinephrine transporter', 'NMDA receptor', 'neuroinflammation'],
            'therapies': ['SSRIs', 'SNRIs', 'bupropion', 'ketamine', 'psychotherapy']
        }
    ]

    for disease in sample_diseases:
        disease_id = f"sample_{disease['id']}"

        text = f"Disease: {disease['name']}\n\n"
        text += f"Description: {disease['description']}\n\n"
        text += f"Therapeutic Targets: {', '.join(disease['targets'])}\n\n"
        text += f"Current Therapies: {', '.join(disease['therapies'])}\n"

        rag_system.add_document(
            disease_id,
            text,
            {
                'id': disease_id,
                'name': disease['name'],
                'description': disease['description'],
                'targets': ', '.join(disease['targets']),
                'therapies': ', '.join(disease['therapies']),
                'source': 'curated',
                'category': 'disease'
            },
            'disease'
        )

    logger.info("Added %d sample diseases", len(sample_diseases))

def populate_drug_targets(rag_system):
    """Add common drug target data"""
    logger.info("Adding drug target data...")

    drug_targets = [
        {
            'id': 'EGFR',
            'name': 'Epidermal Growth Factor Receptor',
            'description': 'Receptor tyrosine kinase involved in cell growth and proliferation. Mutated in various cancers. Target for cancer therapy.',
            'drugs': ['erlotinib', 'gefitinib', 'osimertinib', 'cetuximab'],
            'diseases': ['lung cancer', 'colorectal cancer', 'head and neck cancer']
        },
        {
            'id': 'TNF_alpha',
            'name': 'Tumor Necrosis Factor Alpha',
            'description': 'Pro-inflammatory cytokine central to autoimmune diseases. Shared mechanism of action across multiple inflammatory conditions.',
            'drugs': ['adalimumab', 'infliximab', 'etanercept', 'golimumab'],
            'diseases': ['rheumatoid arthritis', 'inflammatory bowel disease', 'psoriasis']
        },
        {
            'id': 'GLP1R',
            'name': 'Glucagon-Like Peptide-1 Receptor',
            'description': 'Incretin receptor regulating insulin secretion and appetite. Target for metabolic diseases with shared pathophysiology.',
            'drugs': ['semaglutide', 'liraglutide', 'dulaglutide', 'exenatide'],
            'diseases': ['type 2 diabetes', 'obesity', 'cardiovascular disease']
        },
        {
            'id': 'BACE1',
            'name': 'Beta-Secretase 1',
            'description': 'Enzyme involved in amyloid beta production. Target for Alzheimer disease-modifying therapy.',
            'drugs': ['investigational compounds'],
            'diseases': ['Alzheimer disease']
        }
    ]

    for target in drug_targets:
        target_id = f"target_{target['id']}"

        text = f"Drug Target: {target['name']}\n\n"
        text += f"Description: {target['description']}\n\n"
        text += f"Drugs: {', '.join(target['drugs'])}\n\n"
        text += f"Associated Diseases: {', '.join(target['diseases'])}\n"

        rag_system.add_document(
            target_id,
            text,
            {
                'id': target_id,
                'name': target['name'],
                'description': target['description'],
                'drugs': ', '.join(target['drugs']),
                'diseases': ', '.join(target['diseases']),
                'source': 'curated',
                'category': 'target'
            },
            'target'
        )

        for disease in target['diseases']:
            disease_id = f"sample_{disease.replace(' ', '_')}"
            if disease_id in [n for n, _ in rag_system.graph.nodes(data=True)]:
                rag_system.add_relationship(
                    disease_id,
                    target_id,
                    'has_target',
                    {'evidence': 'clinical'}
                )

    logger.info("Added %d drug targets with relationships", len(drug_targets))

def main():
    """Main data population function"""
    logger.info("Starting data population...")

    config = load_config()
    rate_limiter = RateLimiterManager(config['api_limits'])
    data_fetcher = DataFetcherManager(rate_limiter, config)
    rag_system = RAGGraphSystem(config)

    populate_sample_diseases(rag_system)

    populate_drug_targets(rag_system)

    populate_kegg_diseases(data_fetcher, rag_system, limit=15)

    populate_kegg_pathways(data_fetcher, rag_system, limit=25)

    rag_system.save()

    stats = rag_system.get_statistics()
    logger.info("Data population complete!")
    logger.info("Final statistics: %s", stats)

if __name__ == '__main__':
    main()
