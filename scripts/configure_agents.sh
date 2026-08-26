#!/bin/bash
echo "==================================="
echo "Configurando Agentes para MCP"
echo "==================================="
echo ""

# Check Kilo
echo "[1/4] Verificando Kilo..."
if command -v kilo &> /dev/null; then
    echo "Kilo encontrado: $(which kilo)"
else
    echo "WARN: Kilo no encontrado"
fi

# Check Cline
echo "[2/4] Verificando Cline..."
if command -v cline &> /dev/null; then
    echo "Cline encontrado: $(which cline)"
else
    echo "WARN: Cline no encontrado"
    echo "Instala: npm install -g @anthropic-ai/cline"
fi

# Check Hermes
echo "[3/4] Verificando Hermes..."
if command -v hermes &> /dev/null; then
    echo "Hermes encontrado: $(which hermes)"
else
    echo "WARN: Hermes no encontrado"
fi

# Check Python MCP server
echo "[4/4] Verificando servidor MCP..."
if [ -f ".venv/bin/python" ]; then
    echo "Python venv encontrado"
else
    echo "WARN: Ejecuta scripts/setup_mcp.sh primero"
fi

echo ""
echo "==================================="
echo "Configuracion completada!"
echo ""
echo "Variables de entorno en .env:"
echo "  MAOQ_KILO_BIN - Ruta a Kilo CLI"
echo "  MAOQ_CLINE_BIN - Ruta a Cline CLI"
echo "  MAOQ_HERMES_BIN - Ruta a Hermes CLI"
echo "  MAOQ_MAX_WORKERS - Workers paralelos (default: 3)"
echo "  MAOQ_HARNESS_MAX_TIMEOUT - Timeout maximo (default: 3600s)"
echo "==================================="
