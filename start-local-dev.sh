#!/bin/bash

# Start both Backend and Frontend locally in separate terminals
echo "🚀 Starting ARGUS Development Environment..."
echo ""

# Check if tmux is available for split terminals
if command -v tmux &> /dev/null; then
    echo "📱 Using tmux for split terminal development..."
    
    # Kill existing session if it exists
    tmux kill-session -t argus-dev 2>/dev/null
    
    # Create new session
    tmux new-session -d -s argus-dev
    
    # Split the window
    tmux split-window -h
    
    # Run backend in left pane
    tmux send-keys -t argus-dev:0.0 'cd "$(dirname "$PWD")" && ./run-backend-local.sh' Enter
    
    # Run frontend in right pane  
    tmux send-keys -t argus-dev:0.1 'cd "$(dirname "$PWD")" && ./run-frontend-local.sh' Enter
    
    # Attach to session
    echo "🎯 Both services starting in tmux session 'argus-dev'..."
    echo "💡 Use 'tmux attach -t argus-dev' to view the sessions"
    echo "🔄 Use Ctrl+B then arrow keys to switch between panes"
    echo "🛑 Use 'tmux kill-session -t argus-dev' to stop both services"
    echo ""
    
    tmux attach -t argus-dev
    
elif command -v gnome-terminal &> /dev/null; then
    echo "🖥️  Opening separate terminals for backend and frontend..."
    
    # Open backend terminal
    gnome-terminal -- bash -c './run-backend-local.sh; exec bash'
    
    # Wait a moment then open frontend terminal
    sleep 2
    gnome-terminal -- bash -c './run-frontend-local.sh; exec bash'
    
    echo "✅ Both services should now be starting in separate terminals"
    
elif command -v osascript &> /dev/null; then
    echo "🍎 Opening separate Terminal tabs on macOS..."
    
    # Open backend in new tab
    osascript -e 'tell application "Terminal" to do script "cd '"$(pwd)"' && ./run-backend-local.sh"'
    
    # Wait a moment then open frontend in new tab
    sleep 2
    osascript -e 'tell application "Terminal" to do script "cd '"$(pwd)"' && ./run-frontend-local.sh"'
    
    echo "✅ Both services should now be starting in separate Terminal tabs"
    
else
    echo "⚠️  No suitable terminal multiplexer found."
    echo "🔧 Please run the following commands in separate terminals:"
    echo ""
    echo "Terminal 1 (Backend):"
    echo "  ./run-backend-local.sh"
    echo ""
    echo "Terminal 2 (Frontend):"
    echo "  ./run-frontend-local.sh"
fi

echo ""
echo "🌐 Services will be available at:"
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:8501"
echo "   API Docs: http://localhost:8000/docs"
