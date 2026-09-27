#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../scripts/telegram_test_alert.sh"
install_test_failure_alert "Simulation quick test"

# ============================================
# QUICK TEST - Simulation System
# ============================================

echo "🎮 Quick Test - ML Monitoring Simulation"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# ============================================
# Check Python
# ============================================
echo -e "${BLUE}Step 1: Check Python${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}✓ $PYTHON_VERSION${NC}"
else
    echo -e "${RED}✗ Python 3 not found${NC}"
    exit 1
fi
echo ""

# ============================================
# Check Services
# ============================================
echo -e "${BLUE}Step 2: Check Services${NC}"

# API
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ API running (port 8000)${NC}"
else
    echo -e "${RED}✗ API not accessible${NC}"
    echo "   Start with: docker-compose up -d api"
    exit 1
fi

# Evidently
if curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Evidently running (port 8001)${NC}"
else
    echo -e "${YELLOW}⚠ Evidently not accessible (optional)${NC}"
fi
echo ""

# ============================================
# Install Dependencies
# ============================================
echo -e "${BLUE}Step 3: Check Dependencies${NC}"
if python3 -c "import requests; import numpy; import pandas; import tqdm; import colorama" 2>/dev/null; then
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${YELLOW}⚠ Installing dependencies...${NC}"
    pip3 install -q -r requirements.txt
    echo -e "${GREEN}✓ Dependencies installed${NC}"
fi
echo ""

# ============================================
# Run Quick Test
# ============================================
echo -e "${BLUE}Step 4: Run Test Simulation${NC}"
echo ""
echo "Running 20 test requests..."
echo ""

python3 run_simulation.py -n 20 -r 5 -s normal

echo ""
echo "════════════════════════════════════════════════"
echo -e "${GREEN}✅ Quick Test Complete!${NC}"
echo "════════════════════════════════════════════════"
echo ""
echo "🎯 Next Steps:"
echo ""
echo "1. Run more requests:"
echo "   python3 run_simulation.py -n 100 -s normal"
echo ""
echo "2. Test drift detection:"
echo "   python3 run_simulation.py -n 100 -s moderate_drift --analyze"
echo ""
echo "3. Run traffic pattern:"
echo "   python3 run_simulation.py -p burst -s normal"
echo ""
echo "4. Run pre-configured scenario:"
echo "   python3 scenarios.py 2"
echo ""
echo "5. View Grafana dashboard:"
echo "   http://localhost:3000/d/evidently-drift"
echo ""
echo "📚 Full documentation: README.md"
echo ""
