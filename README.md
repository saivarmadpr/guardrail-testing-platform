# Guardrail Testing Platform

An agentic AI application built with LangChain whose primary purpose is to **test and validate LLM guardrails** — including [Votal](https://github.com/your-org/litellm-guardrails-votal-ai) guardrails via the LiteLLM proxy.

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Make sure Ollama is running with a model
ollama pull qwen2.5:7b

# Run the agent interactively
guardrail-tester run "Look up customer John Smith and draft a summary email"

# Run through LiteLLM proxy (with Votal guardrails)
guardrail-tester run --llm-base-url http://localhost:4000/v1 "Look up customer John Smith"

# Run eval suite
guardrail-tester eval --scenarios scenarios/

# Run specific category
guardrail-tester eval --scenarios scenarios/pii/
```

## Architecture

```
User Input → [Input Guards] → Agent (ReAct) → [Tool Guards] → Tools → LLM (via LiteLLM/Ollama) → [Output Guards] → Response
```

Three guardrail layers:
- **Input**: PII detection, prompt injection, topic filtering
- **Tool**: Permission checks, parameter validation, rate limiting, scope enforcement
- **Output**: PII leakage, toxicity, hallucination detection

## Project Structure

```
config/              # Agent, guardrail, and LiteLLM proxy configs
src/guardrail_tester/
  agent/             # ReAct agent runtime and system prompts
  tools/             # 10 guarded tools (web search, DB, email, etc.)
  guardrails/        # Pluggable guardrail framework (input/tool/output)
  eval/              # Scenario runner, reporter, adversarial generator
  mocks/             # Mock Votal server and seed data
  logging/           # Structured JSON-lines logging
scenarios/           # YAML test scenario definitions
tests/               # pytest test suite
```

## Running with Votal Guardrails

1. Start the LiteLLM proxy with Votal:
   ```bash
   cd /path/to/litellm-guardrails-votal-ai
   litellm --config config.yaml --port 4000
   ```

2. Point the agent at the proxy:
   ```bash
   guardrail-tester run --llm-base-url http://localhost:4000/v1 "your prompt"
   ```

Every LLM call flows through Votal's pre/post-call hooks automatically.
