#!/bin/bash
# Test script for VulTrial with PyKerberos vulnerability dataset
# Demonstrates the new pre-debate summarization and function-level analysis

set -e

CODEBASE="data/primevul/195220"
MODEL_TYPE="openai"
MODEL_ID="gpt-4o"
OUTPUT_DIR="output/demos/demo1"

# Create output directory
mkdir -p "$OUTPUT_DIR"
code_snippet="data/primevul/code_snippet.txt"
file_path="tmate-main.c"

# Test 1: Analyze the vulnerable function with full context
echo "--------------------------------------------------------------------------------"
python3 -m app.main \
  --codebase "$CODEBASE" \
  --file "$file_path" \
  --code-snippet "$code_snippet" \
  --model-type "$MODEL_TYPE" \
  --model-id "$MODEL_ID" \
  --output "$OUTPUT_DIR" \
  --max-tokens 16384 \
  --mode detailed \
  --max-turns 4

