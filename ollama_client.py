import ollama
import logging
from typing import List, Dict, Optional
import re

logger = logging.getLogger(__name__)

class OllamaClient:
    """Client for interacting with local Ollama models"""

    def __init__(self, config):
        self.model = config['ollama']['model']
        self.base_url = config['ollama']['base_url']
        self.embedding_model = config['ollama']['embedding_model']

        self.client = ollama.Client(host=self.base_url)
        logger.info("OllamaClient initialized with model %s", self.model)

    def generate_response(self, prompt: str, context: Optional[List[str]] = None) -> str:
        """Generate a response from the Ollama model"""
        full_prompt = prompt
        if context:
            context_text = "\n\n".join(context)
            full_prompt = f"Context:\n{context_text}\n\nQuestion: {prompt}\n\nAnswer:"

        try:
            response = self.client.generate(model=self.model, prompt=full_prompt)
            answer = response['response']
            logger.info("Generated response of length %d", len(answer))
            return answer
        except Exception as e:
            logger.error("Error generating response: %s", str(e))
            return f"Error generating response: {str(e)}"

    def generate_embeddings(self, text: str) -> Optional[List[float]]:
        """Generate embeddings for text using Ollama"""
        try:
            response = self.client.embeddings(model=self.embedding_model, prompt=text)
            embeddings = response['embedding']
            logger.debug("Generated embeddings of dimension %d", len(embeddings))
            return embeddings
        except Exception as e:
            logger.error("Error generating embeddings: %s", str(e))
            return None

    def chat(self, messages: List[Dict[str, str]]) -> str:
        """Chat with the model using message history"""
        try:
            response = self.client.chat(model=self.model, messages=messages)
            answer = response['message']['content']
            logger.info("Chat response generated with length %d", len(answer))
            return answer
        except Exception as e:
            logger.error("Error in chat: %s", str(e))
            return f"Error in chat: {str(e)}"

    def query_rag(self, query: str, rag_system, max_context_items: int = 5) -> Dict:
        """Query using RAG system to provide context with hallucination prevention

        Returns dict with:
        - response: The text answer
        - sources: List of source node IDs used
        - source_details: Metadata about each source
        - relevant_nodes: Node IDs mentioned or relevant to answer
        """
        similar_docs = rag_system.query_similar(query, n_results=max_context_items)

        context = []
        source_ids = []
        source_details = []

        for doc in similar_docs:
            if doc['document']:
                context.append(doc['document'])
                source_ids.append(doc['id'])

                # Get node metadata for source details
                if doc['id'] in rag_system.graph:
                    node_data = rag_system.graph.nodes[doc['id']]
                    source_details.append({
                        'id': doc['id'],
                        'name': node_data.get('name', doc['id']),
                        'type': node_data.get('type', 'unknown'),
                        'distance': doc.get('distance', 0)
                    })
                else:
                    source_details.append({
                        'id': doc['id'],
                        'name': doc['id'],
                        'type': 'unknown',
                        'distance': doc.get('distance', 0)
                    })

        if not context:
            logger.warning("No context found for query, using model without context")
            return {
                'response': "I don't have information about that in my database. Please fetch more data or rephrase your question.",
                'sources': [],
                'source_details': [],
                'relevant_nodes': []
            }

        # Build constrained prompt with actual node IDs
        context_with_ids = []
        for i, (ctx, src_detail) in enumerate(zip(context, source_details)):
            context_with_ids.append(f"[Source {i+1} - {src_detail['name']} ({src_detail['id']})]: {ctx}")

        context_text = "\n\n".join(context_with_ids)

        constrained_prompt = f"""STRICT INSTRUCTIONS:
- Answer ONLY using information from the sources below
- Do NOT add information from your training data or external knowledge
- Do NOT include URLs unless they are explicitly present in the source documents
- If the sources don't contain enough information to answer, say "The available data does not contain enough information to fully answer this question."
- When citing sources, use the format: [node_id] where node_id is the actual ID shown in parentheses
- Example: "According to sample_obesity, obesity is associated with diabetes"
- If you're uncertain about any fact, indicate this clearly
- Be precise and avoid speculation
- List specific node IDs that are relevant to your answer

AVAILABLE SOURCES:
{context_text}

USER QUESTION: {query}

ANSWER FORMAT:
1. Provide your answer with node ID citations
2. Then add a line "RELEVANT_NODES:" followed by comma-separated node IDs mentioned in your answer

ANSWER:"""

        try:
            response = self.client.generate(model=self.model, prompt=constrained_prompt)
            answer = response['response']

            # Extract relevant nodes mentioned in the answer
            relevant_nodes = set(source_ids)  # Start with source nodes

            # Try to extract RELEVANT_NODES section
            if 'RELEVANT_NODES:' in answer:
                parts = answer.split('RELEVANT_NODES:')
                answer = parts[0].strip()
                nodes_text = parts[1].strip()
                # Extract node IDs
                for node_id in nodes_text.split(','):
                    node_id = node_id.strip()
                    if node_id and node_id in rag_system.graph:
                        relevant_nodes.add(node_id)

            # Also scan answer for node IDs mentioned in square brackets
            import re
            node_mentions = re.findall(r'\[([^\]]+)\]', answer)
            for mention in node_mentions:
                if mention in rag_system.graph:
                    relevant_nodes.add(mention)

            # Validate response doesn't contain common hallucination markers
            hallucination_markers = [
                'as of my knowledge cutoff',
                'in recent years',
                'according to studies',
                'research has shown',
                'it is well known',
                'http://',
                'https://',
                'www.'
            ]

            answer_lower = answer.lower()
            warnings = []
            for marker in hallucination_markers:
                if marker in answer_lower:
                    # Check if it's cited from a source
                    marker_pos = answer_lower.index(marker)
                    # Look for citation nearby
                    context_window = answer_lower[max(0, marker_pos-50):min(len(answer_lower), marker_pos+50)]
                    if '[' not in context_window or 'source' in marker.lower():
                        logger.warning("Potential hallucination detected: %s", marker)
                        warnings.append(f"Warning: Response may contain uncited information ({marker})")

            if warnings:
                answer = answer + "\n\n" + "\n".join(warnings)

            logger.info("Generated constrained response with %d sources", len(source_ids))

            return {
                'response': answer,
                'sources': list(source_ids),
                'source_details': source_details,
                'relevant_nodes': list(relevant_nodes)
            }

        except Exception as e:
            logger.error("Error generating response: %s", str(e))
            return {
                'response': f"Error generating response: {str(e)}",
                'sources': [],
                'source_details': [],
                'relevant_nodes': []
            }

    def filter_relevant_urls(self, query: str, search_results: List[Dict[str, str]], max_urls: int = 5) -> List[Dict[str, str]]:
        """Use Ollama to filter search results for relevance to the query

        Args:
            query: Original user query
            search_results: List of dicts with 'url', 'title', 'snippet'
            max_urls: Maximum number of URLs to return

        Returns:
            List of relevant URLs with relevance scores
        """
        if not search_results:
            return []

        try:
            # Build prompt with search results
            results_text = ""
            for i, result in enumerate(search_results):
                results_text += f"[{i+1}] Title: {result['title']}\n"
                results_text += f"    URL: {result['url']}\n"
                results_text += f"    Snippet: {result['snippet']}\n\n"

            filter_prompt = f"""You are evaluating search results for relevance to a medical/scientific query.

USER QUERY: {query}

SEARCH RESULTS:
{results_text}

TASK: Identify which search results are most relevant to answering the user's query.

CRITERIA FOR RELEVANCE:
- Contains scientific/medical evidence (research papers, medical journals, clinical data)
- Directly addresses the query topic
- From reputable sources (universities, research institutions, medical organizations)
- Contains specific data, statistics, or research findings

INSTRUCTIONS:
1. Rate each result from 1-10 (10 = highly relevant, 1 = not relevant)
2. Select the top {max_urls} most relevant results
3. Respond ONLY with a list of result numbers and scores, one per line
4. Format: [number] score

Example:
[1] 9
[3] 8
[5] 7

Your response:"""

            response = self.client.generate(model=self.model, prompt=filter_prompt)
            answer = response['response']

            logger.debug("Ollama filter response: %s", answer[:500])

            # Parse the response to extract result numbers and scores
            relevant_results = []
            lines = answer.strip().split('\n')

            for line in lines:
                # Try multiple regex patterns
                match = (
                    re.match(r'\[(\d+)\]\s*(\d+)', line) or
                    re.match(r'(\d+)\s*[:\-\s]+(\d+)', line) or
                    re.search(r'result\s+(\d+).*?(\d+)', line, re.IGNORECASE)
                )

                if match:
                    result_num = int(match.group(1))
                    score = int(match.group(2))

                    # Get the corresponding search result (1-indexed)
                    if 1 <= result_num <= len(search_results):
                        result = search_results[result_num - 1].copy()
                        result['relevance_score'] = score
                        relevant_results.append(result)

            # Sort by relevance score and limit to max_urls
            relevant_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            relevant_results = relevant_results[:max_urls]

            # Fallback: if no results parsed, use simple heuristic
            if not relevant_results:
                logger.warning("Could not parse Ollama response, using simple heuristic")
                # Prefer results from reputable domains
                for i, result in enumerate(search_results[:max_urls]):
                    result_copy = result.copy()
                    # Score based on domain reputation
                    domain = urlparse(result['url']).netloc
                    if any(x in domain for x in ['nih.gov', 'edu', 'cancer.gov', 'who.int', 'cdc.gov', 'frontiersin.org', 'nature.com', 'science.org']):
                        result_copy['relevance_score'] = 9
                    else:
                        result_copy['relevance_score'] = 7
                    relevant_results.append(result_copy)

            logger.info("Filtered %d relevant URLs from %d results", len(relevant_results), len(search_results))
            return relevant_results

        except Exception as e:
            logger.error("Error filtering URLs: %s", str(e))
            # Fallback: return first max_urls results with scores
            fallback_results = []
            for result in search_results[:max_urls]:
                result_copy = result.copy()
                result_copy['relevance_score'] = 7
                fallback_results.append(result_copy)
            return fallback_results

    def summarize_url_content(self, query: str, url_content: Dict[str, str]) -> Dict[str, str]:
        """Summarize URL content in the context of the query

        Args:
            query: Original user query
            url_content: Dict with 'url', 'title', 'content'

        Returns:
            Dict with 'url', 'title', 'summary', 'key_facts'
        """
        try:
            summary_prompt = f"""Extract relevant information from this web page to answer the user's query.

USER QUERY: {query}

WEB PAGE TITLE: {url_content['title']}
WEB PAGE URL: {url_content['url']}

WEB PAGE CONTENT:
{url_content['content']}

TASK:
1. Provide a 2-3 sentence summary of the key findings relevant to the query
2. Extract specific facts, statistics, or findings that directly address the query
3. List any diseases, genes, drugs, or medical terms mentioned

FORMAT YOUR RESPONSE AS:
SUMMARY: [2-3 sentences]
KEY_FACTS: [Bullet point list]
ENTITIES: [Comma-separated list of diseases, genes, drugs, pathways]

Your response:"""

            response = self.client.generate(model=self.model, prompt=summary_prompt)
            answer = response['response']

            # Parse the response
            summary = ""
            key_facts = []
            entities = []

            if 'SUMMARY:' in answer:
                summary_part = answer.split('KEY_FACTS:')[0]
                summary = summary_part.replace('SUMMARY:', '').strip()

            if 'KEY_FACTS:' in answer:
                facts_part = answer.split('KEY_FACTS:')[1].split('ENTITIES:')[0] if 'ENTITIES:' in answer else answer.split('KEY_FACTS:')[1]
                for line in facts_part.strip().split('\n'):
                    line = line.strip()
                    if line and (line.startswith('-') or line.startswith('*') or line.startswith('•')):
                        key_facts.append(line.lstrip('-*• '))

            if 'ENTITIES:' in answer:
                entities_part = answer.split('ENTITIES:')[1].strip()
                entities = [e.strip() for e in entities_part.split(',') if e.strip()]

            logger.info("Summarized content from %s", url_content['url'])

            return {
                'url': url_content['url'],
                'title': url_content['title'],
                'summary': summary,
                'key_facts': key_facts,
                'entities': entities
            }

        except Exception as e:
            logger.error("Error summarizing URL content: %s", str(e))
            return {
                'url': url_content['url'],
                'title': url_content['title'],
                'summary': 'Error summarizing content',
                'key_facts': [],
                'entities': []
            }
