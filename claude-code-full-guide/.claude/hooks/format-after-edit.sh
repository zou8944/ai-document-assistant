#!/bin/bash
# PostToolUse hook: Automatically format code after file edits
# This hook runs after Edit, Write, or MultiEdit tools to ensure consistent formatting

# Read the JSON input from stdin
input=$(cat)

# Extract tool name and file path from the input
tool_name=$(echo "$input" | jq -r '.tool_name // empty')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

# Only process if it's a file editing tool and we have a file path
if [[ "$tool_name" =~ ^(Edit|Write|MultiEdit)$ ]] && [[ -n "$file_path" ]]; then
    # Determine file extension
    extension="${file_path##*.}"
    
    # Format based on file type
    case "$extension" in
        js|jsx|ts|tsx)
            # JavaScript/TypeScript files
            if command -v prettier &> /dev/null; then
                echo "Formatting $file_path with Prettier..." >&2
                prettier --write "$file_path" 2>/dev/null || true
            elif command -v npx &> /dev/null; then
                echo "Formatting $file_path with npx prettier..." >&2
                npx prettier --write "$file_path" 2>/dev/null || true
            fi
            ;;
        py)
            # Python files
            if command -v black &> /dev/null; then
                echo "Formatting $file_path with Black..." >&2
                black "$file_path" 2>/dev/null || true
            elif command -v ruff &> /dev/null; then
                echo "Formatting $file_path with Ruff..." >&2
                ruff format "$file_path" 2>/dev/null || true
            fi
            ;;
        go)
            # Go files
            if command -v gofmt &> /dev/null; then
                echo "Formatting $file_path with gofmt..." >&2
                gofmt -w "$file_path" 2>/dev/null || true
            fi
            ;;
        rs)
            # Rust files
            if command -v rustfmt &> /dev/null; then
                echo "Formatting $file_path with rustfmt..." >&2
                rustfmt "$file_path" 2>/dev/null || true
            fi
            ;;
        json)
            # JSON files
            if command -v jq &> /dev/null; then
                echo "Formatting $file_path with jq..." >&2
                # Format JSON with jq (careful with large files)
                if [[ $(stat -f%z "$file_path" 2>/dev/null || stat -c%s "$file_path" 2>/dev/null) -lt 1048576 ]]; then
                    jq . "$file_path" > "$file_path.tmp" && mv "$file_path.tmp" "$file_path" 2>/dev/null || true
                fi
            fi
            ;;
    esac
    
    # Log formatting completion
    echo "Post-edit formatting completed for $file_path" >&2
fi

# Always return success to avoid blocking the tool
echo "{}"