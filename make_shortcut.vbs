Set oWS = WScript.CreateObject("WScript.Shell") 
sLinkFile = oWS.SpecialFolders("Desktop") & "\The God Factory Video Editor.lnk" 
Set oLink = oWS.CreateShortcut(sLinkFile) 
oLink.TargetPath = "C:\Users\lokee\Documents\the_god_factory_video\The God Factory Video Editor.bat" 
oLink.WorkingDirectory = "C:\Users\lokee\Documents\the_god_factory_video\" 
oLink.Description = "The God Factory Video Editor" 
oLink.Save 
