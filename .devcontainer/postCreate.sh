#!/bin/sh

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo "${CYAN}📦 Installing dependencies...${NC}"
poetry install --no-interaction
echo ""

echo "${GREEN}🚀 Development environment ready!${NC}"
echo ""

if [ -z "$POETRY_PYPI_TOKEN_PYPI" ]; then 
  echo "${YELLOW}⚠️  WARNING: POETRY_PYPI_TOKEN_PYPI is not set.${NC}"
  echo "${CYAN}📝 To publish to PyPI, add this to .devcontainer/.env:${NC}"
  echo "   ${CYAN}POETRY_PYPI_TOKEN_PYPI=your_token_here${NC}"
  echo ""
fi

echo "${GREEN}✓${NC} Run tests: ${CYAN}poetry run pytest tests/ -v${NC}"
echo "${GREEN}✓${NC} Publish: ${CYAN}./publish.sh${NC}"
