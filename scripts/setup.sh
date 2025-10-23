#!/bin/bash
# setup.sh - Complete environment setup for FastAPI backend

set -e  # Exit on error

echo "🚀 FastAPI Backend Setup"
echo "========================"

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | grep -Po '(?<=Python )\d+\.\d+')
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then 
    echo "❌ Python $REQUIRED_VERSION+ required (found $PYTHON_VERSION)"
    exit 1
fi

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip -q

# Install dependencies
echo "📚 Installing dependencies..."
cat > requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
motor==3.3.2
pydantic==2.5.0
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
httpx==0.25.2
python-dotenv==1.0.0
EOF

cat > requirements-dev.txt << 'EOF'
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
ruff==0.1.9
black==23.12.1
mypy==1.8.0
bandit==1.7.6
pre-commit==3.6.0
EOF

pip install -r requirements.txt -r requirements-dev.txt -q

# Create directory structure
echo "📁 Creating project structure..."
mkdir -p app/{api/v1,services,models,db/repositories,middleware,core}
mkdir -p tests/{unit,integration,performance}
mkdir -p scripts reports specs .claude

# Create .env file if not exists
if [ ! -f ".env" ]; then
    echo "🔐 Creating .env file..."
    cat > .env << 'EOF'
# MongoDB
MONGODB_URI=mongodb://localhost:27017
DATABASE_NAME=translation

# JWT
JWT_SECRET_KEY=change-this-in-production-$(openssl rand -hex 32)
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15

# API
API_V1_PREFIX=/api/v1
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

# File Upload
MAX_UPLOAD_SIZE=10485760
EOF
fi

# Setup pre-commit hooks
echo "🪝 Installing pre-commit hooks..."
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix]
  
  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
  
  - repo: local
    hooks:
      - id: pytest-check
        name: pytest-check
        entry: pytest tests/unit -x
        language: system
        pass_filenames: false
        always_run: true
EOF

pre-commit install

# Create basic app structure
echo "🏗️ Creating basic app files..."

# Main app file
cat > app/main.py << 'EOF'
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from motor.motor_asyncio import AsyncIOMotorClient
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.mongodb_client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
    app.mongodb = app.mongodb_client[os.getenv("DATABASE_NAME")]
    print("✅ Connected to MongoDB")
    yield
    # Shutdown
    app.mongodb_client.close()

app = FastAPI(title="Translation API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
EOF

# Test file
cat > tests/integration/test_health.py << 'EOF'
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
EOF

# MongoDB check
echo "🗄️ Checking MongoDB..."
if ! mongosh --eval "db.version()" > /dev/null 2>&1; then
    echo "⚠️  MongoDB not running. Start with: docker run -d -p 27017:27017 mongo:7.0"
else
    echo "✅ MongoDB is running"
fi

# Make scripts executable
chmod +x scripts/*.py scripts/*.sh 2>/dev/null || true

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Start MongoDB (if not running):"
echo "     docker run -d -p 27017:27017 --name mongodb mongo:7.0"
echo ""
echo "  2. Start the server:"
echo "     source .venv/bin/activate"
echo "     uvicorn app.main:app --reload"
echo ""
echo "  3. Run tests:"
echo "     pytest -v"
echo ""
echo "📚 See CLAUDE.md for agent usage and workflows"
