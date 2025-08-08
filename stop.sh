#!/bin/bash

# MCP Local RAG Server停止スクリプト

echo "🛑 Stopping MCP Local RAG Server..."

# Find and kill the server process
if pgrep -f "python.*server.py" > /dev/null; then
    # Try graceful shutdown first (SIGTERM)
    pkill -TERM -f "python.*server.py"
    echo "Sent SIGTERM signal, waiting for graceful shutdown..."
    
    # Wait up to 5 seconds for graceful shutdown
    for i in {1..5}; do
        if ! pgrep -f "python.*server.py" > /dev/null; then
            echo "✅ Server stopped gracefully"
            exit 0
        fi
        sleep 1
    done
    
    # If still running, force kill
    echo "⚠️  Server didn't stop gracefully, forcing shutdown..."
    pkill -9 -f "python.*server.py"
    sleep 1
    
    if ! pgrep -f "python.*server.py" > /dev/null; then
        echo "✅ Server stopped (forced)"
    else
        echo "❌ Failed to stop server"
        exit 1
    fi
else
    echo "ℹ️  Server is not running"
fi

# Also kill any uv run processes
pkill -f "uv run.*server.py" 2>/dev/null