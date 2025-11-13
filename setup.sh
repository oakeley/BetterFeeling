#!/bin/bash

echo "Setting up BetterFeeling application..."

# Create necessary directories
echo "Creating directories..."
mkdir -p data/cache
mkdir -p data
mkdir -p logs
mkdir -p static
mkdir -p templates

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Setup complete!"
echo ""
echo "To run the application:"
echo "1. Ensure Ollama is running: ollama serve"
echo "2. Pull required models: ollama pull llama3.2 && ollama pull nomic-embed-text"
echo "3. Activate virtual environment: source venv/bin/activate"
echo "4. Run the application: python app.py"
echo ""
echo "The application will be available at http://localhost:9999"
