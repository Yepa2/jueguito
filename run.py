#!/usr/bin/env python3
"""
Lanzador Universal para Discretizando el Tiempo Continuo.
Funciona en Windows, macOS y Linux sin configuración previa.
"""
import sys
import os
import subprocess
import socket
import webbrowser
import threading
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def log(msg):
    print(f"[AUTO-LAUNCH] {msg}")

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def dependencies_installed(python_exe):
    check_code = "import django, cv2, PIL, numpy, dj_database_url; print('OK')"
    try:
        res = subprocess.run([python_exe, "-c", check_code], capture_output=True, text=True)
        return "OK" in res.stdout
    except Exception:
        return False

def get_or_create_env():
    # Si el Python actual ya tiene todo instalado, usarlo directamente
    if dependencies_installed(sys.executable):
        return sys.executable

    venv_dir = BASE_DIR / ".venv"
    if sys.platform == "win32":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"

    if not venv_python.exists():
        log("Creando entorno virtual en .venv...")
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])

    if not dependencies_installed(str(venv_python)):
        log("Instalando dependencias desde requirements.txt (puede tardar un momento)...")
        req_file = BASE_DIR / "requirements.txt"
        try:
            subprocess.check_call([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])
            subprocess.check_call([str(venv_python), "-m", "pip", "install", "-r", str(req_file)])
        except subprocess.CalledProcessError:
            # Si psycopg2-binary falla (comun en ciertos sistemas o arquitecturas), instalar resto
            log("Aviso: Reintentando sin dependencias nativas opcionales...")
            subprocess.check_call([
                str(venv_python), "-m", "pip", "install",
                "django", "dj-database-url", "pillow", "opencv-python-headless", "numpy"
            ])

    return str(venv_python)

def abrir_navegador(url):
    time.sleep(1.2)
    try:
        webbrowser.open(url)
    except Exception:
        pass

def main():
    os.chdir(BASE_DIR)
    python_exe = get_or_create_env()

    log("Preparando base de datos...")
    subprocess.run([python_exe, "manage.py", "migrate", "--noinput"], check=True)

    log("Verificando personajes y usuario administrador...")
    subprocess.run([python_exe, "poblar_personajes.py"], check=True)

    local_ip = get_local_ip()
    url_local = "http://localhost:8000/"
    url_red = f"http://{local_ip}:8000/"

    print("\n" + "=" * 65)
    print(" 🎮  DISCRETIZANDO EL TIEMPO CONTINUO - SERVIDOR ACTIVO")
    print("=" * 65)
    print(f" 👉 En tu navegador local:      {url_local}")
    print(f" 📱 Desde tu celular / tablet:   {url_red}")
    print("    (debe estar conectado a la misma red Wi-Fi)")
    print(" 👤 Usuario admin:               alumno")
    print(" 🔑 Contraseña admin:            usm1234")
    print("=" * 65)
    print(" Para detener el servidor presiona Ctrl + C\n")

    threading.Thread(target=abrir_navegador, args=(url_local,), daemon=True).start()

    try:
        subprocess.run([python_exe, "manage.py", "runserver", "0.0.0.0:8000"])
    except KeyboardInterrupt:
        print("\nServidor detenido. ¡Hasta pronto!")

if __name__ == "__main__":
    main()
