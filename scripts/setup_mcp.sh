#!/bin/bash
echo "==================================="
echo "Multi-Agente Orquestado - Setup MCP"
echo "==================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 no encontrado. Instala Python 3.11+ primero."
    exit 1
fi

# Create virtual environment
echo "[1/4] Creando entorno virtual..."
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
echo "[2/4] Instalando dependencias..."
pip install -e ".[mcp]"

# Setup database
echo "[3/4] Configurando base de datos..."
mkdir -p data/plans

# Copy env file
echo "[4/4] Configurando variables de entorno..."
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp .env.example .env
    echo "Archivo .env creado desde .env.example"
    echo "IMPORTANTE: Edita .env con tus API keys"
fi

echo ""
echo "==================================="
echo "Setup completado!"
echo ""
echo "Para iniciar el servidor MCP:"
echo "  source .venv/bin/activate"
echo "  python -m orchestrator.interfaces.mcp.server"
echo ""
echo "Para ejecutar tests:"
echo "  pytest tests/ -v"
echo "==================================="
