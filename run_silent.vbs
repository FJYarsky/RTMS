' ==============================================================================
' RTMS — Real-Time Multicam System
' Lanzador en segundo plano 100% silencioso para Windows (VBScript)
' Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
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
 
