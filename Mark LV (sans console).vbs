' MARK LV — lance l'app sans fenetre de console.
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh  = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir
sh.Run """" & dir & "\.venv\Scripts\pythonw.exe"" """ & dir & "\main.py""", 0, False
