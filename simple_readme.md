

#### 1. Tool Information

* **Tool Name:** VulTrial (Vulnerability Trial)

* **Repository / URL:** https://github.com/yueyuel/Vultrial_agent

#### 2. Authors and Contact

* **Main Author(s):** Yue Liu, Ratnadira Widyasari 
* **Contact:** yuehhhliu@gmail.com

#### 3. Overview

VulTrial is an AI-powered security analysis tool that uses multiple agents in a debate-style approach to identify vulnerabilities in source code. Four specialized agents (Security Researcher, Code Author, Moderator, and Review Board) argue about potential security issues while research assistants automatically search the codebase for evidence. The tool supports Python, C/C++, Java, and JavaScript/TypeScript, and can perform analysis at function, file, or entire codebase levels with intelligent context retrieval and CWE knowledge base integration.

#### 4. Installation

**Prerequisites:** Python 3.10+ and an LLM API key (Claude, GPT, Gemini, or Grok)

```bash
# Clone the repository
git clone https://github.com/yueyuel/Vultrial_agent.git
cd Vultrial_agent

# Install Python dependencies
pip install -r requirements.txt

# Set up API key (choose one)
export ANTHROPIC_API_KEY="your-key"    # For Claude
export OPENAI_API_KEY="your-key"       # For GPT
export GOOGLE_API_KEY="your-key"       # For Gemini
export XAI_API_KEY="your-key"          # For Grok

# Optional: Install cscope for enhanced C/C++ analysis
brew install cscope  # macOS
# sudo apt-get install cscope  # Ubuntu/Debian

# Optional: Install ts-morph for enhanced JS/TS analysis
cd app/context/search_js/
npm install
cd ../../..
```

#### 5. Usage

**Interactive UI (Recommended):**
```bash
./vultrial-ui
```

**Command Line Examples:**
```bash
# WITH CODEBASE (enables research assistants for evidence gathering):

# Analyze a specific function
python -m app.main --codebase data/demo1 \
                   --file auth.c \
                   --function perform_admin_operation \
                   --model-type claude \
                   --model-id claude-3-5-sonnet-20241022

# Analyze an entire file
python -m app.main --codebase data/demo1 \
                   --file auth.c \
                   --model-type claude \
                   --model-id claude-3-5-sonnet-20241022

# Analyze entire codebase
python -m app.main --codebase data/demo1 \
                   --model-type claude \
                   --model-id claude-3-5-sonnet-20241022

# STANDALONE MODE (NO codebase - pure debate without research assistants):

# Analyze standalone file
python -m app.main --file /path/to/auth.c \
                   --model-type claude \
                   --model-id claude-3-5-sonnet-20241022

# Analyze standalone function
python -m app.main --file /path/to/auth.c \
                   --function login \
                   --model-type claude \
                   --model-id claude-3-5-sonnet-20241022

# Analyze code snippet directly (no file needed!)
python -m app.main --code-snippet "if (user) { admin_check(); }" \
                   --model-type claude \
                   --model-id claude-3-5-sonnet-20241022

# Or load snippet from file
python -m app.main --code-snippet /path/to/snippet.c \
                   --model-type claude \
                   --model-id claude-3-5-sonnet-20241022

# OTHER OPTIONS:

# Fast scan mode (consensus - only obvious vulnerabilities)
python -m app.main --codebase data/demo1 \
                   --file auth.c \
                   --mode consensus \
                   --max-turns 2

# With output directory
python -m app.main --codebase data/demo1 \
                   --file auth.c \
                   --output output/results
```

**Key Arguments:**
- `--codebase` / `-c`: Path to codebase directory (optional - enables research assistants)
- `--file` / `-f`: Specific file to analyze (for standalone file analysis)
- `--function`: Specific function name (requires --file)
- `--code-snippet`: Code snippet to analyze directly (standalone, no file needed)
- `--model-type` / `-t`: LLM provider (openai, claude, gemini, grok)
- `--model-id` / `-m`: Specific model ID
- `--mode`: Analysis mode ('detailed' or 'consensus')
- `--output` / `-o`: Output directory or file base name
- `--max-turns`: Number of debate rounds (default: 4)

**Analysis Modes:**
- **With Codebase**: Enables research assistants that search for evidence (functions, callers, data flow, etc.)
- **Standalone**: Pure agent debate based only on the provided code (no context retrieval)
  - Use `--file` for file analysis
  - Use `--code-snippet` for direct snippet analysis (paste code directly!)

#### 6. Input and Output Format

**Input Format:**

The tool accepts source code in the following formats:

* **Supported Languages:** Python (.py), C/C++ (.c, .cpp, .h, .hpp), Java (.java), JavaScript/TypeScript (.js, .ts, .jsx, .tsx)

* **Analysis Levels:**
  - **Function Level:** Single function from a specific file
  - **Code Snippet Level:** Arbitrary code snippet (provided directly or from file)
  - **File Level:** All functions within a single file
  - **Codebase Level:** All source files in the entire project

* **Required Structure:** 
  - A valid codebase directory path
  - Source files with standard extensions
  - Valid function names or code snippets (for targeted analysis)

**Output Format:**

VulTrial generates three output files per analysis:

1. **JSON Results** (`filename_TIMESTAMP.json`):
   - Structured data with full analysis results
   - Includes vulnerability findings, severity levels, CWE classifications
   - Token usage statistics and cost information
   - Machine-readable for CI/CD integration

2. **Text Summary** (`filename_TIMESTAMP.txt`):
   - Human-readable summary of key findings
   - Vulnerability descriptions and recommendations
   - Quick overview for manual review

3. **Detailed Log** (`filename_TIMESTAMP.detailed.txt`):
   - Complete debate transcript with all agent interactions
   - Evidence retrieval details and reasoning chains
   - Full context for understanding the analysis process

**Output Structure Example:**
```json
{
  "timestamp": "2025-11-09T14:30:00",
  "file_analyzed": "auth.c",
  "codebase": "data/demo1",
  "model": "claude-3-5-sonnet-20241022",
  "analysis_mode": "detailed",
  "analysis_results": {
    "vulnerabilities": [...],
    "severity": "high",
    "confidence": 0.85,
    "recommendations": [...]
  },
  "token_usage": {
    "input_tokens": 12450,
    "output_tokens": 3280,
    "total_cost": 0.0866
  }
}
```

**Key Features:**
- Automated evidence gathering through codebase search
- CWE vulnerability database integration
- Multi-turn debate with intelligent coordination
- Context-aware analysis with caller/callee tracking
- Taint flow analysis for injection vulnerabilities

