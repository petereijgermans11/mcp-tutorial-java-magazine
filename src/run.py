import subprocess
import sys

# Build the command as a list
cmd = [
    sys.executable, "-m", "uvicorn",
    "src.main:app_instance",
    "--reload",
    "--port", "8003"
]
 

# Start the server in a non-blocking way
process = subprocess.Popen(cmd)

print("Uvicorn server started!")
# Your script can continue here, or you can add logic to monitor/stop the server if needed