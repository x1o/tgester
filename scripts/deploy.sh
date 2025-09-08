#!/bin/bash
set -e

# Check arguments
if [ $# -lt 2 ]; then
    echo "Usage: $0 <server> <deploy_dir> [python_version]"
    echo "Example: $0 user@hostname /opt/tgester 3.13"
    exit 1
fi

# Arguments
SERVER=$1
DEPLOY_DIR=$2
PYTHON_VERSION=${3:-"3.13"}  # Default to 3.13 if not specified

echo "🚀 Starting deployment"
echo "   Server: $SERVER"
echo "   Deploy directory: $DEPLOY_DIR"
echo "   Python version: $PYTHON_VERSION"
echo ""

# 1. Build the package locally
echo "📦 Building package..."
uv build

# Get the wheel filename
WHEEL=$(ls -t dist/*.whl | head -1)
if [ -z "$WHEEL" ]; then
    echo "❌ No wheel file found in dist/"
    exit 1
fi
WHEEL_NAME=$(basename $WHEEL)
echo "   Built: $WHEEL_NAME"

# 2. Ensure deployment directory exists with correct permissions
echo "📁 Setting up deployment directory..."
ssh $SERVER "sudo mkdir -p $DEPLOY_DIR && sudo chown -R \$USER:\$USER $DEPLOY_DIR"

# 3. Copy files to deployment directory
echo "📤 Copying files to server..."
scp $WHEEL $SERVER:$DEPLOY_DIR/
scp inst/tgester.service.template inst/tgester.timer $SERVER:$DEPLOY_DIR/
scp inst/install_service.sh $SERVER:$DEPLOY_DIR/

# 4. Run installation on server
echo "🔧 Installing on server..."
ssh $SERVER "cd $DEPLOY_DIR && bash install_service.sh '$WHEEL_NAME' '$PYTHON_VERSION' '$DEPLOY_DIR'"

# 5. Clean up installation files
echo "🧹 Cleaning up..."
ssh $SERVER "cd $DEPLOY_DIR && rm -f *.whl install_service.sh"

# 6. Configuration reminder
echo ""
echo "⚠️  IMPORTANT: Manual steps required:"
echo ""
echo "1. Copy your configuration files to the server:"
echo "   scp config.yaml $SERVER:$DEPLOY_DIR/"
echo "   scp .env $SERVER:$DEPLOY_DIR/"
echo ""
echo "2. Copy your Telegram session if you have one:"
echo "   scp telegram.session $SERVER:$DEPLOY_DIR/"
echo ""
echo "3. Test the service manually:"
echo "   ssh $SERVER"
echo "   cd $DEPLOY_DIR"
echo "   .venv/bin/tgester --config config.yaml --env .env"
echo "OR"
echo "   sudo systemctl start tgester.service"
echo "and check the status with the usual"
echo "   sudo journalctl -xefu tgester.service"
echo ""
echo "4. Enable and start the timer:"
echo "   ssh $SERVER"
echo "   sudo systemctl enable --now tgester.timer"
echo ""
echo "5. Check timer status:"
echo "   systemctl status tgester.timer"
echo "   systemctl list-timers"
echo ""
echo "✅ Deployment complete!"