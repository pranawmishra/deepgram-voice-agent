# Voice Agent Function Calling Python Flask Starter

This repository serves as a reference implementation for integrating function calling capabilities with Deepgram's Voice Agent API. It demonstrates production-ready patterns for building AI Voice Agent applications with clientside function calling.

## Sign-up to Deepgram

Before you start, it's essential to generate a Deepgram API key to use in this project. [Sign-up now for Deepgram](https://console.deepgram.com/signup).

## Quickstart

This reference implementation demonstrates:

- Core function calling patterns with Voice Agent API
- Natural conversation flow using agent filler messages
- Customer information lookup and verification
- Order history retrieval
- Appointment scheduling and management
- Graceful conversation termination through an `end_call` function

### Function Calling Architecture
The implementation uses a three-layer architecture:
- Function definitions that guide the LLM's behavior
- Function handlers that route requests
- Business logic that executes the actual functionality

### Natural Conversation Flow
Shows how to implement natural dialogue patterns:
- Agent filler messages for lookup operations
- Proper message sequencing
- Audio completion handling
- Clean session termination

## Project Structure

```
├── business_logic.py     # Core function implementations
├── client.py             # WebSocket client and message handling
├── config.py             # Configuration settings
├── functions.py          # Function definitions and routing
```

## Mock Data System

The implementation uses a mock data system for demonstration:
- Generates realistic customer, order, and appointment data
- Saves data to timestamped JSON files in `mock_data_outputs/`
- Configurable through `config.py`

### Artificial Delays
The implementation demonstrates how to handle real-world latency:
- Configurable database operation delays in `config.py`
- Helps simulate production environment timing

## Setup Instructions

`pipenv`  can be used to manage virtual env. and packages in one easy to use tool. instead of running pip commands, you just use [pipenv](https://pypi.org/project/pipenv/).

1. Install pipenv if not already installed.

```bash
pip install pipenv
```

2. Switch to a pipenv virtual env.
```bash
pipenv shell
```

3. Install the project dependencies:

In the root directory of the project, run the following command to install the dependencies:

```bash
pipenv install -r requirements.txt
```

3. Set your Deepgram API key:
```bash
export DEEPGRAM_API_KEY=<your-key-here>
```

## Application Usage

1. Run the client:
   ```bash
   python client.py
   ```

2. Use headphones to prevent audio feedback (the agent hearing itself).

## Example Interactions

The voice agent handles natural conversations like:

```
User: "I need to check my order status"
Agent: "Let me look that up for you..."
[Agent executes customer lookup]
Agent: "I can see you have two recent orders. Your most recent
       order from last week is currently being shipped..."
```

## Configuration

Key settings in `config.py`:
- `ARTIFICIAL_DELAY`: Configurable delays for database operations
- `MOCK_DATA_SIZE`: Control size of generated test data


## Issue Reporting

If you have found a bug or if you have a feature request, please report them at this repository issues section. Please do not report security vulnerabilities on the public GitHub issue tracker. The [Security Policy](./SECURITY.md) details the procedure for contacting Deepgram.

## Author

[Deepgram](https://deepgram.com)

## License

This project is licensed under the MIT license. See the [LICENSE](./LICENSE) file for more info.