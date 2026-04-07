# Guardrail Testing Platform

A realistic agentic AI customer support application built with LangChain. It has 10 tools, handles multi-step requests, and behaves like a production app.

The agent itself has **no guardrails built in** — it is designed to be the **target** for external guardrail systems like [Votal](https://github.com/sundi133/litellm-guardrails-votal-ai.git) via the LiteLLM proxy.

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Make sure Ollama is running with a model
ollama pull qwen2.5:3b

# Run the agent with a single prompt
guardrail-tester run "Look up customer John Smith and draft a summary email"

# Run through LiteLLM proxy (Votal guardrails intercept every LLM call)
guardrail-tester run --llm-base-url http://localhost:4000/v1 "Look up customer John Smith"

# Send batch test scenarios to the agent
guardrail-tester test --scenarios scenarios/

# Test a specific category
guardrail-tester test --scenarios scenarios/pii/
```

## Architecture

```
User → Agent (ReAct) → Tools → LLM (Ollama / LiteLLM proxy) → Response
```

The agent is a clean, realistic customer support app. It does **not** enforce any guardrails itself. To test guardrails, point the agent at a LiteLLM proxy that runs Votal (or any other guardrail) on pre-call and post-call hooks.

### Tools (10)

| Tool | Description |
|------|-------------|
| `web_search` | DuckDuckGo web search |
| `database_query` | SQLite customer database (read-only) |
| `email_send` | Draft and send emails (dry-run mode) |
| `user_data_lookup` | Customer record lookup by name/email/ID |
| `file_read` | Read files from internal filesystem |
| `api_call` | HTTP requests to external APIs |
| `calendar_manage` | List, create, delete calendar events |
| `code_execute` | Run Python in a restricted sandbox |
| `knowledge_base_search` | Search internal docs and policies |
| `report_generate` | Generate customer reports |

## Testing Guardrails

### 1. Start the LiteLLM proxy with Votal

```bash
cd /path/to/litellm-guardrails-votal-ai
litellm --config config.yaml --port 4000
```

### 2. Point the agent at the proxy

```bash
guardrail-tester run --llm-base-url http://localhost:4000/v1 "Tell me John Smith's SSN"
```

Every LLM call now flows through Votal's pre/post-call hooks. The proxy decides whether to block, allow, or modify the request — the agent never knows.

### 3. Run the test suite

```bash
guardrail-tester test --scenarios scenarios/ --llm-base-url http://localhost:4000/v1
```

The test command sends 30 adversarial, benign, and edge-case scenarios to the agent, records what happened, and produces a pass/fail report showing which prompts were blocked vs allowed.

## Project Structure

```
config/              # Agent config and LiteLLM proxy config
src/guardrail_tester/
  agent/             # ReAct agent runtime and system prompt
  tools/             # 10 tools (web search, DB, email, etc.)
  eval/              # External test runner, reporter, scenario loader
  mocks/             # Mock seed data for tools
  logging/           # Structured JSON-lines logging
scenarios/           # YAML test scenario definitions (30 scenarios)
tests/               # pytest unit tests
```
