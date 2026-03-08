import subprocess
import time
import sys
import os
import socket

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def kill_port(port: int):
    """Kill any process listening on the given port (Windows)."""
    try:
        result = subprocess.run(
            f"netstat -ano | findstr :{port}",
            shell=True, capture_output=True, text=True
        )
        for line in result.stdout.strip().splitlines():
            parts = line.strip().split()
            if parts and parts[0] == 'TCP':
                pid = parts[-1]
                subprocess.run(f"taskkill /PID {pid} /F", shell=True, capture_output=True)
        time.sleep(1)
    except Exception as e:
        print(f"  (Could not kill port {port}: {e})")

def run_demo():
    print("🚀 Starting Document Intelligence Refinery Demo...")

    BACKEND_PORT = 8000

    if is_port_in_use(BACKEND_PORT):
        print(f"⚠️  Port {BACKEND_PORT} is in use. Killing existing process...")
        kill_port(BACKEND_PORT)

    # 1. Start Backend
    print(f"📡 Starting FastAPI Backend on http://localhost:{BACKEND_PORT}...")
    backend_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", str(BACKEND_PORT)],
        cwd=os.getcwd()
    )

    # Wait for backend to be ready
    print("⏳ Waiting for backend to start (this may take 1-2 minutes)...")
    for _ in range(120):
        if is_port_in_use(BACKEND_PORT):
            break
        time.sleep(1)
    else:
        print("❌ Backend failed to start in time. Check for errors above.")
        backend_process.terminate()
        return

    # 2. Start Frontend
    print("💻 Starting Vite Frontend...")
    frontend_process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=os.path.join(os.getcwd(), "frontend"),
        shell=True if os.name == 'nt' else False
    )

    time.sleep(3)

    print("\n✅ Demo environment is ready!")
    print(f"👉 Access the interface at: http://localhost:5173")
    print(f"👉 Backend API docs at: http://localhost:{BACKEND_PORT}/docs")
    print("\nPress Ctrl+C to stop both servers.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping servers...")
        backend_process.terminate()
        frontend_process.terminate()
        print("Done.")

if __name__ == "__main__":
    run_demo()

