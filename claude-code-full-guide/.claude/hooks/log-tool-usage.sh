#!/bin/bash
# PostToolUse hook: Log all tool usage for tracking and debugging
# This hook runs after any tool execution to maintain an audit log

# Read the JSON input from stdin
input=$(cat)

# Extract tool name and basic info
tool_name=$(echo "$input" | jq -r '.tool_name // "unknown"')
timestamp=$(date '+%Y-%m-%d %H:%M:%S')

# Create logs directory if it doesn't exist
mkdir -p .claude/logs

# Log the tool usage
echo "[$timestamp] Tool used: $tool_name" >> .claude/logs/tool-usage.log

# Optionally, you can add more detailed logging
if [[ "$tool_name" =~ ^(Edit|Write|MultiEdit)$ ]]; then
    file_path=$(echo "$input" | jq -r '.tool_input.file_path // "unknown"')
    echo "[$timestamp] File operation: $tool_name on $file_path" >> .claude/logs/file-operations.log
fi

# Always return success to avoid blocking tools
echo "{}"