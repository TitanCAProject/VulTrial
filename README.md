
# VulTrial

A lightweight, AI-powered code vulnerability analyzer using multi-agent debate with open-source models.

## Overview

VulTrial uses four specialized AI agents (Security Researcher, Code Author, Moderator, and Review Board) in a debate-style approach to identify security vulnerabilities in code snippets. The agents argue about potential issues and reach a consensus on findings.

**Powered by:** Open-source LLMs from Hugging Face (Llama, Qwen, Mistral, CodeLlama, etc.)

**Supported Languages:** Python, C/C++, Java, JavaScript/TypeScript

## Installation

**Prerequisites:** Python 3.10+, CUDA (recommended for GPU acceleration)

```bash
# Clone the repository
git clone https://github.com/yueyuel/Vultrial_agent.git
cd Vultrial_agent

# Install dependencies
pip install -r requirements.txt

# Optional: Set Hugging Face token for gated models (like Llama)
export HF_TOKEN="your_huggingface_token"
```

### System Requirements

| Model Size | GPU Memory | Quantization | Speed |
|------------|-----------|--------------|-------|
| 7B | 14GB | None | Fast |
| 7B | 7GB | 8-bit | Fast |
| 7B | 4GB | 4-bit | Fast |
| 13B | 26GB | None | Medium |
| 13B | 13GB | 8-bit | Medium |
| 13B | 7GB | 4-bit | Medium |
| 32B | 64GB | None | Slow |
| 32B | 32GB | 8-bit | Slow |
| 32B | 16GB | 4-bit | Slow |
| 70B | 140GB | None | Very Slow |
| 70B | 70GB | 8-bit | Very Slow |
| 70B | 35GB | 4-bit | Very Slow |

**Note:** CPU inference is supported but much slower.

## Usage

### Quick Start

```bash
# Analyze code snippet with Qwen 7B (default)
python -m app.main --code-snippet "if (user) { admin_check(); }"

# Use Qwen 32B with 4-bit quantization (saves memory)
python -m app.main --code-snippet "code here" --model Qwen/Qwen2-32B-Instruct --quantization 4bit

# Use Llama 3 8B with 8-bit quantization
python -m app.main --code-snippet "code here" --model meta-llama/Meta-Llama-3-8B-Instruct --quantization 8bit
```

### Load Snippet from File

```bash
python -m app.main --code-snippet /path/to/snippet.c --model Qwen/Qwen2-7B-Instruct
```

### Save Results to File

```bash
python -m app.main --code-snippet "code" --output results.json
```

### Advanced Options

```bash
# Specify device, max tokens, temperature
python -m app.main --code-snippet "code" \
                   --model meta-llama/Meta-Llama-3-8B-Instruct \
                   --quantization 4bit \
                   --device cuda \
                   --max-tokens 3000 \
                   --temperature 0.7 \
                   --max-turns 4
```

## Command Line Arguments

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--code-snippet` | | Code to analyze (required) | - |
| `--model` | `-m` | Hugging Face model ID | Qwen/Qwen2-7B-Instruct |
| `--quantization` | `-q` | none, 8bit, 4bit | none |
| `--max-turns` | | Number of debate rounds | 4 |
| `--temperature` | | Model temperature (0-1) | 0.7 |
| `--max-tokens` | | Max tokens per response | 2048 |
| `--device` | | cuda or cpu | auto |
| `--output` | `-o` | Output JSON file path | - |
| `--quiet` | | Suppress verbose output | False |

## Output Format

Results are provided as a JSON array of vulnerabilities:

```json
[
  {
    "vulnerability": "CWE-89: SQL Injection",
    "decision": "valid",
    "location": "Line 15-20",
    "severity": "high",
    "recommended_action": "fix immediately",
    "justification": "User input is directly concatenated into SQL query...",
    "confidence": 0.95
  }
]
```

If no vulnerabilities are found, the output is an empty array: `[]`

## Example

```bash
$ python -m app.main --code-snippet "
def login(username, password):
    query = f'SELECT * FROM users WHERE user={username} AND pass={password}'
    return db.execute(query)
" --model Qwen/Qwen2-7B-Instruct --quantization 4bit

======================================================================
VulTrial - Code Snippet Vulnerability Analyzer
======================================================================
Model: Qwen/Qwen2-7B-Instruct
Quantization: 4bit
Max turns: 4
======================================================================

Loading model: Qwen/Qwen2-7B-Instruct
Device: cuda
Using 4-bit quantization
Model loaded successfully!

Analyzing: 142 characters

...

======================================================================
FINAL DECISION
======================================================================
[
  {
    "vulnerability": "CWE-89: SQL Injection",
    "decision": "valid",
    "severity": "high",
    ...
  }
]
======================================================================
```

## License

MIT License
