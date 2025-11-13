import re
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

class KEGGParser:
    """Parses KEGG disease and pathway entries to extract structured data"""

    @staticmethod
    def parse_disease_genes(disease_info: str) -> List[Dict[str, str]]:
        """
        Extract gene information from KEGG disease entry

        Returns list of dicts with:
        - gene_symbol: Gene name (e.g., BCR-ABL)
        - gene_ids: List of HSA IDs (e.g., [25])
        - ko_ids: List of KO IDs (e.g., [K06619])
        - relationship: Type (translocation, mutation, etc.)
        """
        genes = []

        # Find GENE section
        gene_match = re.search(r'GENE\s+(.+?)(?=\n[A-Z]+\s+|\Z)', disease_info, re.DOTALL)
        if not gene_match:
            return genes

        gene_section = gene_match.group(1)

        # Parse each gene line
        # Format: GENE_NAME (type) [HSA:id1 id2] [KO:id1 id2]
        gene_lines = gene_section.strip().split('\n')

        for line in gene_lines:
            line = line.strip()
            if not line:
                continue

            # Extract gene name and relationship type
            name_match = re.match(r'([A-Za-z0-9\-]+(?:\s*\([^)]+\))?)\s*(\([^)]+\))?', line)
            if not name_match:
                continue

            gene_symbol = name_match.group(1).strip()
            relationship = name_match.group(2).strip('()') if name_match.group(2) else 'associated'

            # Extract HSA IDs
            hsa_match = re.search(r'\[HSA:([^\]]+)\]', line)
            gene_ids = []
            if hsa_match:
                gene_ids = [g.strip() for g in hsa_match.group(1).split()]

            # Extract KO IDs
            ko_match = re.search(r'\[KO:([^\]]+)\]', line)
            ko_ids = []
            if ko_match:
                ko_ids = [k.strip() for k in ko_match.group(1).split()]

            genes.append({
                'gene_symbol': gene_symbol,
                'gene_ids': gene_ids,
                'ko_ids': ko_ids,
                'relationship': relationship
            })

        logger.info("Parsed %d genes from KEGG disease entry", len(genes))
        return genes

    @staticmethod
    def parse_disease_pathways(disease_info: str) -> List[Dict[str, str]]:
        """
        Extract pathway information from KEGG disease entry

        Returns list of dicts with:
        - pathway_id: KEGG pathway ID (e.g., hsa05200)
        - pathway_name: Pathway name
        """
        pathways = []

        # Find PATHWAY section
        pathway_match = re.search(r'PATHWAY\s+(.+?)(?=\n[A-Z]+\s+|\Z)', disease_info, re.DOTALL)
        if not pathway_match:
            return pathways

        pathway_section = pathway_match.group(1)

        # Parse each pathway line
        # Format: hsa05200  Pathway name
        pathway_lines = pathway_section.strip().split('\n')

        for line in pathway_lines:
            line = line.strip()
            if not line:
                continue

            # Extract pathway ID and name
            parts = line.split(None, 1)
            if len(parts) >= 2:
                pathway_id = parts[0]
                pathway_name = parts[1]

                pathways.append({
                    'pathway_id': pathway_id,
                    'pathway_name': pathway_name
                })

        logger.info("Parsed %d pathways from KEGG disease entry", len(pathways))
        return pathways

    @staticmethod
    def parse_disease_drugs(disease_info: str) -> List[Dict[str, str]]:
        """
        Extract drug information from KEGG disease entry

        Returns list of dicts with drug information
        """
        drugs = []

        # Find DRUG section
        drug_match = re.search(r'DRUG\s+(.+?)(?=\n[A-Z]+\s+|\Z)', disease_info, re.DOTALL)
        if not drug_match:
            return drugs

        drug_section = drug_match.group(1)

        # Parse each drug line
        drug_lines = drug_section.strip().split('\n')

        for line in drug_lines:
            line = line.strip()
            if not line:
                continue

            # Extract drug ID and name
            parts = line.split(None, 1)
            if len(parts) >= 2:
                drug_id = parts[0]
                drug_name = parts[1]

                drugs.append({
                    'drug_id': drug_id,
                    'drug_name': drug_name
                })

        logger.info("Parsed %d drugs from KEGG disease entry", len(drugs))
        return drugs
