#!/bin/bash
# Book2Audible Quick Setup

echo "🎧 Book2Audible Setup"

# Create virtual environment
python3 -m venv book2audible-env
source book2audible-env/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# Setup configuration
if [ ! -f .env ]; then
    cp .env.example .env
    echo "📝 Edit .env file with your Baseten API key"
fi

# Create directories
mkdir -p data/input data/output data/logs

# Download NLTK data
python3 -c "import nltk; nltk.download('punkt')"

echo "✅ Setup completed!"
echo "Next: Edit .env file, then run:"
echo "python3 book2audible.py --test-connection"
