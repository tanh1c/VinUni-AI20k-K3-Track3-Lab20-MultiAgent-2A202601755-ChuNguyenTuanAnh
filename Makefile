.PHONY: install test lint format typecheck run-baseline run-multi run-benchmark run-corpus-benchmark clean

install:
	pip install -e ".[dev,llm]"

test:
	pytest

lint:
	ruff check src tests

format:
	ruff format src tests

typecheck:
	mypy src

run-baseline:
	python -m multi_agent_research_lab.cli baseline --query "Research GraphRAG state-of-the-art"

run-multi:
	python -m multi_agent_research_lab.cli multi-agent --query "Research GraphRAG state-of-the-art"

run-benchmark:
	python -m multi_agent_research_lab.cli benchmark --query "Compare single-agent and multi-agent research systems" --output reports/benchmark_report.md

run-corpus-benchmark:
	python -m multi_agent_research_lab.cli corpus-benchmark --topics "AIAGENT-01,AIAGENT-12,AIAGENT-13" --source-budget 8 --output reports/corpus_benchmark_report.md --details reports/corpus_benchmark_details.json

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache dist build *.egg-info
