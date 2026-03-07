# Document Intelligence Refinery

A production-grade, multi-stage agentic pipeline for unstructured document extraction.

## Project Structure

- `src/agents/triage.py`: Classifies documents and selects extraction strategies.
- `src/agents/extractor.py`: Routes extraction requests with a confidence-gated escalation guard.
- `src/agents/chunker.py`: Implements semantic chunking rules to produce Logical Document Units (LDUs).
- `src/agents/indexer.py`: Builds a hierarchical navigation tree (`PageIndex`) with LLM summaries.
- `src/agents/query_agent.py`: LangGraph-based interface with tools for navigation, search, and SQL querying.
- `src/models/`: Pydantic schemas for data consistency across all stages.
- `src/strategies/`: Specialized extractors (Fast Text, Layout-Aware, Vision-Augmented).
- `src/utils/`: Database and vector store utilities.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your OLLAMA_HOST and API keys
   ```

## Usage

### Run Triage and Extraction
```bash
python main.py --file data/sample.pdf
```

### Query the Refinery
```python
from src.agents.query_agent import RefineryAssistant
# ... initialize and run
answer = assistant.run("What is the total revenue?")
print(answer)
```

### Audit Mode
```python
verification = assistant.audit_claim("The report states revenue was $4.2B.")
print(verification)
```

## Artifacts
- `.refinery/profiles/`: Document classification JSONs.
- `.refinery/pageindex/`: Navigation tree JSONs.
- `.refinery/extraction_ledger.jsonl`: Performance and cost audit logs.
