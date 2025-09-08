#!/bin/bash
set -e

# Check arguments
if [ $# -lt 3 ]; then
    echo "❌ Missing arguments"
    echo "Usage: $0 <wheel_name> <python_version> <deploy_dir>"
    exit 1
fi

# Arguments
WHEEL_NAME=$1
PYTHON_VERSION=$2
DEPLOY_DIR=$3

echo "   Starting remote installation..."
echo "   Wheel: $WHEEL_NAME"
echo "   Python: $PYTHON_VERSION"
echo "   Directory: $DEPLOY_DIR"

cd $DEPLOY_DIR

# Install uv if needed
if ! command -v uv &> /dev/null; then
    echo "   Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Check if venv exists and Python version matches
if [ -d ".venv" ]; then
    CURRENT_PYTHON=$(.venv/bin/python --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
    if [ "$CURRENT_PYTHON" != "$PYTHON_VERSION" ]; then
        echo "   Python version mismatch. Recreating venv..."
        rm -rf .venv
        uv venv --python $PYTHON_VERSION
    else
        echo "   Using existing venv with Python $CURRENT_PYTHON"
    fi
else
    echo "   Creating virtual environment with Python $PYTHON_VERSION..."
    uv venv --python $PYTHON_VERSION
fi

# Install or upgrade the package
echo "   Installing tgester package..."
if uv pip list | grep -q tgester; then
    echo "   Upgrading existing installation..."
    uv pip install --upgrade $WHEEL_NAME
else
    echo "   Fresh installation..."
    uv pip install $WHEEL_NAME
fi

# Generate systemd service from template using sed
echo "   Generating systemd service..."
CURRENT_USER=$(whoami)

# Use sed to replace placeholders in template
sed -e "s|{{USER}}|$CURRENT_USER|g" \
    -e "s|{{DEPLOY_DIR}}|$DEPLOY_DIR|g" \
    tgester.service.template > tgester.service

# Install systemd services
echo "   Installing systemd services..."
sudo cp tgester.service /etc/systemd/system/
sudo cp tgester.timer /etc/systemd/system/
sudo systemctl daemon-reload

# Clean up
rm -f tgester.service tgester.service.template tgester.timer

echo "   ✅ Remote installation complete!"

# Show installed version
echo "   Installed version:"
.venv/bin/python -c "import tgester; print(f'   tgester {tgester.__version__}')" 2>/dev/null || echo "   (unable to determine version)"

# Show service configuration
echo ""
echo "   Service configured with:"
echo "   - User: $CURRENT_USER"
echo "   - Working directory: $DEPLOY_DIR"
echo "   - Python: $DEPLOY_DIR/.venv/bin/python"
