#!/bin/bash

# Chess-GPT New Computer Setup Script
# This script will check for and install all required dependencies

echo "🚀 Chess-GPT Setup Script for New Computer"
echo "==========================================="
echo ""

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Homebrew is installed
echo "📦 Checking for Homebrew..."
if ! command -v brew &> /dev/null; then
    echo -e "${RED}❌ Homebrew not found${NC}"
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for Apple Silicon Macs
    if [[ $(uname -m) == 'arm64' ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
    echo -e "${GREEN}✅ Homebrew installed${NC}"
else
    echo -e "${GREEN}✅ Homebrew already installed${NC}"
fi

echo ""

# Check if Python 3 is installed
echo "🐍 Checking for Python 3..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found${NC}"
    echo "Installing Python 3..."
    brew install python@3.11
    echo -e "${GREEN}✅ Python 3 installed${NC}"
else
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo -e "${GREEN}✅ Python 3 already installed (version $PYTHON_VERSION)${NC}"
fi

echo ""

# Check if Node.js is installed
echo "📦 Checking for Node.js..."
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js not found${NC}"
    echo "Installing Node.js..."
    brew install node@20
    brew link node@20
    echo -e "${GREEN}✅ Node.js installed${NC}"
else
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}✅ Node.js already installed (version $NODE_VERSION)${NC}"
fi

echo ""

# Check if Stockfish is installed
echo "♟️  Checking for Stockfish chess engine..."
if ! command -v stockfish &> /dev/null; then
    echo -e "${RED}❌ Stockfish not found${NC}"
    echo "Installing Stockfish..."
    brew install stockfish
    echo -e "${GREEN}✅ Stockfish installed${NC}"
else
    echo -e "${GREEN}✅ Stockfish already installed${NC}"
fi

echo ""
echo "================================================"
echo "📚 Installing Project Dependencies..."
echo "================================================"

# Install Python backend dependencies
echo ""
echo "🐍 Installing Python backend dependencies..."
cd backend
if [ -f "requirements.txt" ]; then
    python3 -m pip install --upgrade pip
    pip3 install -r requirements.txt
    echo -e "${GREEN}✅ Backend dependencies installed${NC}"
else
    echo -e "${RED}❌ requirements.txt not found${NC}"
fi
cd ..

echo ""

# Install Node.js frontend dependencies
echo "📦 Installing Node.js frontend dependencies..."
cd frontend
if [ -f "package.json" ]; then
    npm install
    echo -e "${GREEN}✅ Frontend dependencies installed${NC}"
else
    echo -e "${RED}❌ package.json not found${NC}"
fi
cd ..

echo ""

# Setup Stockfish symlink in backend
echo "♟️  Setting up Stockfish in backend..."
if [ -f "backend/stockfish" ]; then
    echo -e "${GREEN}✅ Stockfish binary already exists in backend${NC}"
else
    STOCKFISH_PATH=$(which stockfish)
    if [ -n "$STOCKFISH_PATH" ]; then
        ln -s "$STOCKFISH_PATH" backend/stockfish
        chmod +x backend/stockfish
        echo -e "${GREEN}✅ Stockfish symlink created in backend${NC}"
    else
        echo -e "${RED}❌ Could not find Stockfish. Please install it manually.${NC}"
    fi
fi

echo ""
echo "================================================"
echo "🔑 API Key Configuration"
echo "================================================"

# Check for OpenAI API key in backend
if [ -f "backend/.env" ]; then
    echo -e "${GREEN}✅ Backend .env file exists${NC}"
else
    echo -e "${YELLOW}⚠️  Backend .env file not found${NC}"
    echo ""
    echo "Please enter your OpenAI API key (or press Enter to skip for now):"
    read -r OPENAI_KEY
    if [ -n "$OPENAI_KEY" ]; then
        echo "OPENAI_API_KEY=$OPENAI_KEY" > backend/.env
        echo -e "${GREEN}✅ Backend .env file created${NC}"
    else
        echo -e "${YELLOW}⚠️  Skipped. You'll need to create backend/.env manually later.${NC}"
    fi
fi

echo ""

# Check for OpenAI API key in frontend
if [ -f "frontend/.env.local" ]; then
    echo -e "${GREEN}✅ Frontend .env.local file exists${NC}"
else
    echo -e "${YELLOW}⚠️  Frontend .env.local file not found${NC}"
    echo ""
    echo "Creating frontend .env.local file..."
    if [ -n "$OPENAI_KEY" ]; then
        cat > frontend/.env.local << EOF
# Backend API URL
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000

# OpenAI API key (required for LLM features)
NEXT_PUBLIC_OPENAI_API_KEY=$OPENAI_KEY

# OpenAI model (optional, defaults to gpt-4o-mini)
OPENAI_MODEL=gpt-4o-mini
EOF
        echo -e "${GREEN}✅ Frontend .env.local file created${NC}"
    else
        cat > frontend/.env.local << EOF
# Backend API URL
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000

# OpenAI API key (required for LLM features)
NEXT_PUBLIC_OPENAI_API_KEY=your-api-key-here

# OpenAI model (optional, defaults to gpt-4o-mini)
OPENAI_MODEL=gpt-4o-mini
EOF
        echo -e "${YELLOW}⚠️  Frontend .env.local created with placeholder. Please edit it with your API key.${NC}"
    fi
fi

echo ""
echo "================================================"
echo "✅ Setup Complete!"
echo "================================================"
echo ""
echo "📋 Summary of installed software:"
echo "  - Homebrew: $(brew --version | head -n1)"
echo "  - Python: $(python3 --version)"
echo "  - Node.js: $(node --version)"
echo "  - npm: $(npm --version)"
echo "  - Stockfish: $(stockfish --help 2>&1 | head -n1 || echo 'Installed')"
echo ""
echo "🚀 Next Steps:"
echo ""
echo "1. If you haven't added your OpenAI API key yet, edit:"
echo "   - backend/.env"
echo "   - frontend/.env.local"
echo ""
echo "2. Start the application with:"
echo "   ${GREEN}./start.sh${NC}"
echo ""
echo "   Or start backend and frontend separately:"
echo "   ${GREEN}./start_backend.sh${NC}  (in one terminal)"
echo "   ${GREEN}./start_frontend.sh${NC}  (in another terminal)"
echo ""
echo "3. Open your browser to:"
echo "   Frontend: ${GREEN}http://localhost:3000${NC}"
echo "   Backend API: ${GREEN}http://localhost:8000${NC}"
echo ""
echo "Happy chess playing! ♟️"

