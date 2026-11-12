#!/usr/bin/env bash
# Lanzador para Linux y macOS
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "==================================================="
echo "  Iniciando Discretizando el Tiempo Continuo..."
echo "==================================================="

if command -v python3 &>/dev/null; then
    python3 run.py
elif command -v python &>/dev/null; then
    python run.py
else
    echo "[ERROR] No se encontro Python instalado."
    echo "Por favor instala Python 3 en tu sistema (ej: sudo apt install python3 python3-venv o brew install python3)."
    exit 1
fi
