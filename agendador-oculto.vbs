' Prospector Standalone - roda o agendador sem janela (tarefa agendada)
Set fso = CreateObject("Scripting.FileSystemObject")
pasta = fso.GetParentFolderName(WScript.ScriptFullName)
cmd = "python """ & pasta & "\agendador.py"""
CreateObject("Wscript.Shell").Run cmd, 0, False
