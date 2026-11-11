' SHIV Database Silent 24/7 Service Launcher
' Launches watchdog_runner.py completely hidden in background without any visible CMD window

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

strScriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)

' Command to execute batch/python
strCommand = "cmd.exe /c cd /d """ & strScriptDir & """ && python watchdog_runner.py"

' Run with window style 0 (hidden) and bWaitOnReturn = False (async)
objShell.Run strCommand, 0, False
