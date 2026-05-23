taskkill /f /im python.exe
schtasks /delete /tn "WindowsSystemHelper" /f
rd /s /q "%APPDATA%\WindowsHelper"
