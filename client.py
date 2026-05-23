cd C:\Windows\system32

taskkill /f /im python.exe
taskkill /f /im WindowsSystemHelper.exe

schtasks /delete /tn "WindowsSystemHelper" /f

del /f /q client.py
del /f /q WindowsSystemHelper.exe

rd /s /q "%APPDATA%\WindowsHelper"

echo RAT has been force removed.
