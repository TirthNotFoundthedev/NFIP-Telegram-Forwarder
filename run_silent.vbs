Set WshShell = CreateObject("WScript.Shell")
' Run the main.py script silently (0 = hide window)
WshShell.Run "python main.py", 0
Set WshShell = Nothing
