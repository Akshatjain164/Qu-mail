Set WshShell = WScript.CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

strDesktop = WshShell.SpecialFolders("Desktop")
strProjectRoot = FSO.GetParentFolderName(WScript.ScriptFullName)

strShortcutPath = strDesktop & "\QuMail.lnk"
strTargetPath = strProjectRoot & "\qumail_launcher.bat"
strIconPath = strProjectRoot & "\frontend\assets\icon.ico"
strWorkingDir = strProjectRoot

Set oShortcut = WshShell.CreateShortcut(strShortcutPath)
oShortcut.TargetPath = strTargetPath
oShortcut.WorkingDirectory = strWorkingDir
oShortcut.IconLocation = strIconPath & ",0"
oShortcut.Description = "QuMail - Quantum Secure Email Client"
oShortcut.WindowStyle = 1
oShortcut.Save

WScript.Echo "QuMail shortcut created on your Desktop!"
WScript.Quit
