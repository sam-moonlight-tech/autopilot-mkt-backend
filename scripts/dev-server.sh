#!/bin/bash
# Development server daemon script with auto-reload

set -e

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
PID_FILE="$PROJECT_ROOT/.dev-server.pid"
LOG_FILE="$PROJECT_ROOT/.dev-server.log"

cd "$PROJECT_ROOT"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Unset shell env vars that should come from .env file
unset OPENAI_API_KEY

# Function to start the server
start_server() {
    # If server is already running, stop it first
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Server is already running (PID: $PID). Stopping it first..."
            kill "$PID" 2>/dev/null || true
            
            # Wait for graceful shutdown
            for i in {1..10}; do
                if ! ps -p "$PID" > /dev/null 2>&1; then
                    break
                fi
                sleep 1
            done
            
            # Force kill if still running
            if ps -p "$PID" > /dev/null 2>&1; then
                echo "Force killing existing server..."
                kill -9 "$PID" 2>/dev/null || true
            fi
            
            rm -f "$PID_FILE"
        else
            rm -f "$PID_FILE"
        fi
    fi

    echo "Starting development server with auto-reload..."
    echo "Logs: $LOG_FILE"
    
    # Start uvicorn with reload enabled
    nohup uvicorn src.main:app \
        --host 0.0.0.0 \
        --port 8080 \
        --reload \
        --reload-dir src \
        --log-level info \
        > "$LOG_FILE" 2>&1 &
    
    SERVER_PID=$!
    echo $SERVER_PID > "$PID_FILE"
    
    # Wait a moment to check if it started successfully
    sleep 2
    if ps -p "$SERVER_PID" > /dev/null 2>&1; then
        echo "✓ Server started successfully (PID: $SERVER_PID)"
        echo "  - API: http://localhost:8080"
        echo "  - Docs: http://localhost:8080/docs"
        echo "  - Logs: tail -f $LOG_FILE"
        return 0
    else
        echo "✗ Server failed to start. Check logs: $LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

# Function to stop the server
stop_server() {
    if [ ! -f "$PID_FILE" ]; then
        echo "Server is not running (no PID file found)"
        return 1
    fi

    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Stopping server (PID: $PID)..."
        kill "$PID"
        
        # Wait for graceful shutdown
        for i in {1..10}; do
            if ! ps -p "$PID" > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        
        # Force kill if still running
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Force killing server..."
            kill -9 "$PID"
        fi
        
        rm -f "$PID_FILE"
        echo "✓ Server stopped"
        return 0
    else
        echo "Server process not found (stale PID file)"
        rm -f "$PID_FILE"
        return 1
    fi
}

# Function to restart the server
restart_server() {
    echo "Restarting server..."
    stop_server || true
    sleep 1
    start_server
}

# Function to show server status
status_server() {
    if [ ! -f "$PID_FILE" ]; then
        echo "Server is not running"
        return 1
    fi

    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Server is running (PID: $PID)"
        echo "  - API: http://localhost:8080"
        echo "  - Logs: $LOG_FILE"
        return 0
    else
        echo "Server is not running (stale PID file)"
        rm -f "$PID_FILE"
        return 1
    fi
}

# Function to show logs
show_logs() {
    if [ ! -f "$LOG_FILE" ]; then
        echo "No log file found. Server may not have been started yet."
        return 1
    fi
    tail -f "$LOG_FILE"
}

# Main command handling
case "${1:-}" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        restart_server
        ;;
    status)
        status_server
        ;;
    logs)
        show_logs
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the development server with auto-reload"
        echo "  stop    - Stop the running server"
        echo "  restart - Restart the server"
        echo "  status  - Check if server is running"
        echo "  logs    - Show and follow server logs"
        exit 1
        ;;
esac

