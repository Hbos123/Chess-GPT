#!/bin/bash

# Chess-GPT Installation Commands
# Run each section one at a time, waiting for each to complete

echo "================================================================"
echo "📱 STEP 1: Install Xcode Command Line Tools"
echo "================================================================"
echo ""
echo "Running: xcode-select --install"
echo "A popup will appear - click Install and wait for it to finish"
echo ""
read -p "Press Enter to install Xcode Command Line Tools..."
xcode-select --install
echo ""
echo "⏳ Wait for the installation to complete, then press Enter..."
read -p "Press Enter once Xcode installation is done..."
echo ""

echo "================================================================"
echo "🍺 STEP 2: Install Homebrew"
echo "================================================================"
echo ""
echo "This will take 2-5 minutes..."
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
echo ""
echo "🔧 Adding Homebrew to your PATH..."
if [[ $(uname -m) == 'arm64' ]]; then
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    eval "$(/opt/homebrew/bin/brew shellenv)"
else
    echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zprofile
    eval "$(/usr/local/bin/brew shellenv)"
fi
echo ""
echo "✅ Verifying Homebrew..."
brew --version
echo ""
read -p "Press Enter to continue..."

echo "================================================================"
echo "📦 STEP 3: Install Node.js 20"
echo "================================================================"
echo ""
brew install node@20
echo ""
echo "✅ Node.js installed:"
node --version
npm --version
echo ""
read -p "Press Enter to continue..."

echo "================================================================"
echo "♟️  STEP 4: Install Stockfish Chess Engine"
echo "================================================================"
echo ""
brew install stockfish
echo ""
echo "✅ Stockfish installed"
which stockfish
echo ""
read -p "Press Enter to continue..."

echo "================================================================"
echo "🐍 STEP 5: Install Python Backend Dependencies"
echo "================================================================"
echo ""
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend
python3 -m pip install --upgrade pip
pip3 install -r requirements.txt
echo ""
echo "✅ Backend dependencies installed"
echo ""
read -p "Press Enter to continue..."

echo "================================================================"
echo "📦 STEP 6: Install Node.js Frontend Dependencies"
echo "================================================================"
echo ""
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/frontend
npm install
echo ""
echo "✅ Frontend dependencies installed"
echo ""
read -p "Press Enter to continue..."

echo "================================================================"
echo "🔗 STEP 7: Link Stockfish to Backend"
echo "================================================================"
echo ""
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend
ln -sf $(which stockfish) ./stockfish
chmod +x stockfish
echo "✅ Stockfish linked to backend"
echo ""
read -p "Press Enter to continue..."

echo "================================================================"
echo "🔑 STEP 8: Configure OpenAI API Key"
echo "================================================================"
echo ""
echo "You need an OpenAI API key to use the AI features."
echo ""
echo "To get one:"
echo "1. Go to https://platform.openai.com/api-keys"
echo "2. Sign in or create an account"
echo "3. Click 'Create new secret key'"
echo "4. Copy the key (starts with sk-)"
echo ""
read -p "Enter your OpenAI API key (or press Enter to skip): " OPENAI_KEY
echo ""

if [ -n "$OPENAI_KEY" ]; then
    # Create backend .env
    cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend
    echo "OPENAI_API_KEY=$OPENAI_KEY" > .env
    echo "✅ Backend .env created"
    
    # Create frontend .env.local
    cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/frontend
    cat > .env.local << EOF
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_OPENAI_API_KEY=$OPENAI_KEY
OPENAI_MODEL=gpt-4o-mini
EOF
    echo "✅ Frontend .env.local created"
else
    echo "⚠️  Skipped. You can add your API key later by editing:"
    echo "   - /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend/.env"
    echo "   - /Users/hugobosnic/Desktop/Projects/Chess-GPT/frontend/.env.local"
fi
echo ""

echo "================================================================"
echo "🎉 INSTALLATION COMPLETE!"
echo "================================================================"
echo ""
echo "✅ All dependencies installed successfully!"
echo ""
echo "📋 What was installed:"
echo "   - Xcode Command Line Tools"
echo "   - Homebrew: $(brew --version | head -n1)"
echo "   - Python 3: $(python3 --version)"
echo "   - Node.js: $(node --version)"
echo "   - npm: $(npm --version)"
echo "   - Stockfish: $(which stockfish)"
echo "   - Backend Python packages (FastAPI, python-chess, etc.)"
echo "   - Frontend Node packages (React, Next.js, etc.)"
echo ""
echo "🚀 To start the application:"
echo ""
echo "   cd /Users/hugobosnic/Desktop/Projects/Chess-GPT"
echo "   ./start.sh"
echo ""
echo "Then open your browser to:"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo ""
echo "Happy chess playing! ♟️"

