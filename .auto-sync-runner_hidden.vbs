' 静默运行 .auto-sync-runner.bat，不显示任何窗口（被 AutoGitHubSync-R BANK 定时任务调用）
Set objShell = CreateObject("WScript.Shell")
objShell.CurrentDirectory = "k:\Trae CN\R BANK"
objShell.Run """k:\Trae CN\R BANK\.auto-sync-runner.bat""", 0, True