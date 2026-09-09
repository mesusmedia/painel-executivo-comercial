Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\oluca\painel-executivo-comercial"
WshShell.Run """C:\Users\oluca\AppData\Local\Programs\Python\Python310\pythonw.exe"" ""C:\Users\oluca\painel-executivo-comercial\run_background_sync.py""", 0, False
