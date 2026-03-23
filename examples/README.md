# AgentHound Examples

This directory contains complete, runnable examples demonstrating how to test AI agents with AgentHound.

## Files

- **`support_agent.py`** — A simple customer support agent built with the OpenAI SDK
- **`test_support_agent.py`** — Tests for the agent using every AgentHound feature
- **`fixtures/`** — Pre-recorded session fixtures (no API keys needed to run tests)

## Running

```bash
# Run all tests (no API keys needed — uses recorded fixtures)
pytest examples/test_support_agent.py -v

# Re-record fixtures (requires OPENAI_API_KEY)
# pytest examples/test_support_agent.py -v --agenthound-record
```
