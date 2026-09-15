' RTMS v2.2.3 Silent Background Launcher
' ==============================================================================
' RTMS v2.2.3 — Lanzador 100% Silencioso en Windows (VBScript)
' Desarrollado y soporte: Joaquín Yarsky - joaquinyarsky@gmail.com - +54 2625-437980
' ==============================================================================

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strPath = fso.GetParentFolderName(WScript.ScriptFullName)

strPythonw = strPath & "\bin\python\pythonw.exe"
strMain = strPath & "\main.py"

If fso.FileExists(strPythonw) Then
    WshShell.CurrentDirectory = strPath
    WshShell.Run """" & strPythonw & """ """ & strMain & """", 0, False
Else
    WshShell.CurrentDirectory = strPath
    WshShell.Run "pythonw """ & strMain & """", 0, False
End If
