#!/bin/bash
# FX Quant Research - Environment Setup Script

PROJECT_DIR="/home/ghost/Workspace/Projects/Exhausyion + filure to continue hupothesis/fx-quant-research"
cd "$PROJECT_DIR"

echo "🔧 Setting up FX Quant Research Environment..."
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
else
    echo "✅ Virtual environment already exists"
fi

# Activate venv
source venv/bin/activate

# Upgrade pip
echo ""
echo "⬆️  Upgrading pip..."
pip install --upgrade pip -q

# Install dependencies
echo ""
echo "📥 Installing dependencies..."
pip install -r requirements.txt matplotlib seaborn ipykernel jupyter -q

# Register Jupyter kernel
echo ""
echo "🎯 Registering Jupyter kernel..."
python -m ipykernel install --user --name=fx-quant-venv --display-name="Python (fx-quant-venv)" 2>&1

echo ""
echo "✅ Setup complete!"
echo ""
echo "📝 To use in VS Code notebooks:"
echo "   1. Click the kernel selector (top-right of notebook)"
echo "   2. Select 'Python (fx-quant-venv)'"
echo ""
echo "💻 To use in terminal:"
echo "   source venv/bin/activate"
echo ""
echo "🔍 Python path: $PROJECT_DIR/venv/bin/python"
