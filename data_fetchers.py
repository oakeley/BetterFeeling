import requests
import logging
from typing import Dict, List, Optional
import json
from bioservices.kegg import KEGG

logger = logging.getLogger(__name__)

class DataGouvFetcher:
    """Fetches drug evaluation data from data.gouv.fr"""

    def __init__(self, rate_limiter, config):
        self.rate_limiter = rate_limiter
        self.base_url = config['urls']['data_gouv_base']
        self.dataset_id = config['urls']['data_gouv_dataset']
        logger.info("DataGouvFetcher initialized")

    def fetch_dataset_info(self) -> Optional[Dict]:
        """Fetch dataset metadata"""
        if not self.rate_limiter.acquire('data_gouv_fr'):
            logger.error("Rate limit exceeded for data.gouv.fr")
            return None

        try:
            url = f"{self.base_url}/datasets/{self.dataset_id}/"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            logger.info("Fetched dataset info from data.gouv.fr")
            return data
        except requests.RequestException as e:
            logger.error("Error fetching from data.gouv.fr: %s", str(e))
            return None

    def fetch_resources(self) -> List[Dict]:
        """Fetch available resources from the dataset"""
        dataset_info = self.fetch_dataset_info()
        if not dataset_info:
            return []

        resources = dataset_info.get('resources', [])
        logger.info("Found %d resources in dataset", len(resources))
        return resources

    def fetch_resource_data(self, resource_url: str) -> Optional[Dict]:
        """Fetch data from a specific resource URL"""
        if not self.rate_limiter.acquire('data_gouv_fr'):
            logger.error("Rate limit exceeded for data.gouv.fr")
            return None

        try:
            response = requests.get(resource_url, timeout=30)
            response.raise_for_status()

            if 'json' in response.headers.get('Content-Type', ''):
                return response.json()
            else:
                return {'raw_data': response.text}
        except requests.RequestException as e:
            logger.error("Error fetching resource from %s: %s", resource_url, str(e))
            return None

class HetIOFetcher:
    """Fetches disease and drug relationship data from het.io"""

    def __init__(self, rate_limiter, config):
        self.rate_limiter = rate_limiter
        self.base_url = config['urls']['hetio_base']
        logger.info("HetIOFetcher initialized")

    def fetch_diseases(self) -> List[Dict]:
        """Fetch list of diseases"""
        if not self.rate_limiter.acquire('hetio'):
            logger.error("Rate limit exceeded for hetio")
            return []

        try:
            url = f"{self.base_url}/nodes/Disease"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            logger.info("Fetched %d diseases from hetio", len(data))
            return data
        except requests.RequestException as e:
            logger.error("Error fetching diseases from hetio: %s", str(e))
            return []

    def fetch_compounds(self) -> List[Dict]:
        """Fetch list of compounds"""
        if not self.rate_limiter.acquire('hetio'):
            logger.error("Rate limit exceeded for hetio")
            return []

        try:
            url = f"{self.base_url}/nodes/Compound"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            logger.info("Fetched %d compounds from hetio", len(data))
            return data
        except requests.RequestException as e:
            logger.error("Error fetching compounds from hetio: %s", str(e))
            return []

    def fetch_relationships(self, source_id: str, metaedge: str) -> List[Dict]:
        """Fetch relationships for a given node and metaedge type"""
        if not self.rate_limiter.acquire('hetio'):
            logger.error("Rate limit exceeded for hetio")
            return []

        try:
            url = f"{self.base_url}/node/{source_id}/edges/{metaedge}"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            logger.info("Fetched %d relationships for %s via %s", len(data), source_id, metaedge)
            return data
        except requests.RequestException as e:
            logger.error("Error fetching relationships: %s", str(e))
            return []

class KEGGFetcher:
    """Fetches pathway data from KEGG database"""

    def __init__(self, rate_limiter, config):
        self.rate_limiter = rate_limiter
        self.kegg = KEGG()
        logger.info("KEGGFetcher initialized")

    def fetch_pathway_list(self, organism='hsa') -> List[str]:
        """Fetch list of pathways for an organism"""
        if not self.rate_limiter.acquire('kegg'):
            logger.error("Rate limit exceeded for KEGG")
            return []

        try:
            pathways = self.kegg.list(organism)
            pathway_list = pathways.strip().split('\n')
            logger.info("Fetched %d pathways for organism %s", len(pathway_list), organism)
            return pathway_list
        except Exception as e:
            logger.error("Error fetching pathways from KEGG: %s", str(e))
            return []

    def fetch_pathway_info(self, pathway_id: str) -> Optional[str]:
        """Fetch detailed information for a specific pathway"""
        if not self.rate_limiter.acquire('kegg'):
            logger.error("Rate limit exceeded for KEGG")
            return None

        try:
            info = self.kegg.get(pathway_id)
            logger.info("Fetched pathway info for %s", pathway_id)
            return info
        except Exception as e:
            logger.error("Error fetching pathway %s: %s", pathway_id, str(e))
            return None

    def fetch_disease_list(self) -> List[str]:
        """Fetch list of diseases from KEGG"""
        if not self.rate_limiter.acquire('kegg'):
            logger.error("Rate limit exceeded for KEGG")
            return []

        try:
            diseases = self.kegg.list('disease')
            disease_list = diseases.strip().split('\n')
            logger.info("Fetched %d diseases from KEGG", len(disease_list))
            return disease_list
        except Exception as e:
            logger.error("Error fetching diseases from KEGG: %s", str(e))
            return []

    def fetch_disease_info(self, disease_id: str) -> Optional[str]:
        """Fetch detailed information for a specific disease"""
        if not self.rate_limiter.acquire('kegg'):
            logger.error("Rate limit exceeded for KEGG")
            return None

        try:
            info = self.kegg.get(disease_id)
            logger.info("Fetched disease info for %s", disease_id)
            return info
        except Exception as e:
            logger.error("Error fetching disease %s: %s", disease_id, str(e))
            return None

class DataFetcherManager:
    """Manages all data fetchers"""

    def __init__(self, rate_limiter_manager, config):
        self.data_gouv = DataGouvFetcher(rate_limiter_manager, config)
        self.hetio = HetIOFetcher(rate_limiter_manager, config)
        self.kegg = KEGGFetcher(rate_limiter_manager, config)
        logger.info("DataFetcherManager initialized with all fetchers")

    def fetch_all_initial_data(self) -> Dict:
        """Fetch initial data from all sources"""
        logger.info("Starting initial data fetch from all sources")

        data = {
            'data_gouv': {
                'resources': self.data_gouv.fetch_resources()
            },
            'hetio': {
                'diseases': self.hetio.fetch_diseases()[:50],
                'compounds': self.hetio.fetch_compounds()[:50]
            },
            'kegg': {
                'pathways': self.kegg.fetch_pathway_list()[:20],
                'diseases': self.kegg.fetch_disease_list()[:20]
            }
        }

        logger.info("Completed initial data fetch")
        return data
