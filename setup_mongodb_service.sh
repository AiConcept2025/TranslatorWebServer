#!/bin/bash

# ================================================
# MongoDB Service Setup - macOS Version
# ================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_info() { echo -e "${YELLOW}ℹ $1${NC}"; }

# Fixed paths for macOS
MONGO_DIR="/opt/mongodb"
DATA_DIR="$MONGO_DIR/data"
LOG_DIR="$MONGO_DIR/logs"
CONF_FILE="$MONGO_DIR/mongod.conf"
PORT="27017"
PLIST_FILE="$HOME/Library/LaunchAgents/com.mongodb.mongod.plist"

echo "MongoDB Service Setup - macOS"
echo "=============================="
echo ""

# Check if installed via Homebrew
if command -v brew &> /dev/null && brew list mongodb-community &> /dev/null 2>&1; then
    print_info "MongoDB installed via Homebrew detected"
    echo ""
    echo "Use Homebrew to manage MongoDB:"
    echo "  Start:   brew services start mongodb-community"
    echo "  Stop:    brew services stop mongodb-community"
    echo "  Restart: brew services restart mongodb-community"
    echo ""
    read -p "Continue with custom setup? (y/N): " CONTINUE
    if [ "$CONTINUE" != "y" ]; then
        exit 0
    fi
fi

# Check mongod
if ! command -v mongod &> /dev/null; then
    print_error "mongod not found"
    exit 1
fi
MONGOD_PATH=$(which mongod)
print_success "MongoDB found: $MONGOD_PATH"

# Create directories
print_info "Creating directories..."
mkdir -p "$DATA_DIR" "$LOG_DIR"
chmod 755 "$DATA_DIR" "$LOG_DIR"
print_success "Directories created"

# Create config file
print_info "Creating config file..."
cat > "$CONF_FILE" << EOF
storage:
  dbPath: $DATA_DIR
systemLog:
  destination: file
  path: $LOG_DIR/mongod.log
  logAppend: true
net:
  port: $PORT
  bindIp: 127.0.0.1
EOF
print_success "Config created: $CONF_FILE"

# Stop any running instances
if pgrep -x mongod > /dev/null; then
    print_info "Stopping existing MongoDB..."
    pkill mongod 2>/dev/null || true
    sleep 2
fi

# Create LaunchAgent plist
print_info "Creating LaunchAgent..."
mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mongodb.mongod</string>
    <key>ProgramArguments</key>
    <array>
        <string>$MONGOD_PATH</string>
        <string>--config</string>
        <string>$CONF_FILE</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>$MONGO_DIR</string>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/stderr.log</string>
</dict>
</plist>
EOF
print_success "LaunchAgent created: $PLIST_FILE"

# Load and start service
print_info "Loading and starting MongoDB..."
launchctl unload "$PLIST_FILE" 2>/dev/null || true
launchctl load "$PLIST_FILE"
sleep 3

# Check if running
if pgrep -x mongod > /dev/null; then
    print_success "MongoDB is running"
    
    # Test connection
    if command -v mongosh &> /dev/null; then
        sleep 2
        if mongosh --port "$PORT" --eval "db.version()" >/dev/null 2>&1; then
            print_success "MongoDB is accessible"
        fi
    fi
else
    print_error "MongoDB failed to start"
    echo "Check logs: tail -f $LOG_DIR/stderr.log"
    exit 1
fi

# Create helper scripts
cat > "$MONGO_DIR/start.sh" << 'EOF'
#!/bin/bash
launchctl load ~/Library/LaunchAgents/com.mongodb.mongod.plist
EOF

cat > "$MONGO_DIR/stop.sh" << 'EOF'
#!/bin/bash
launchctl unload ~/Library/LaunchAgents/com.mongodb.mongod.plist
EOF

cat > "$MONGO_DIR/restart.sh" << 'EOF'
#!/bin/bash
launchctl unload ~/Library/LaunchAgents/com.mongodb.mongod.plist
sleep 2
launchctl load ~/Library/LaunchAgents/com.mongodb.mongod.plist
EOF

chmod +x "$MONGO_DIR"/*.sh

echo ""
echo "Setup Complete!"
echo "==============="
echo ""
echo "MongoDB Management:"
echo "  Start:   launchctl load $PLIST_FILE"
echo "           or: $MONGO_DIR/start.sh"
echo ""
echo "  Stop:    launchctl unload $PLIST_FILE"
echo "           or: $MONGO_DIR/stop.sh"
echo ""
echo "  Restart: $MONGO_DIR/restart.sh"
echo ""
echo "  Logs:    tail -f $LOG_DIR/mongod.log"
echo "           tail -f $LOG_DIR/stderr.log"
echo ""
echo "  Connect: mongosh --port $PORT"
echo ""
echo "MongoDB will auto-start on login"
echo ""
echo "To disable auto-start:"
echo "  launchctl unload -w $PLIST_FILE"
echo ""

