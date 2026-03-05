$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c E:\projects\creative_bot\auto_push.bat"

$trigger = New-ScheduledTaskTrigger -Daily -At "23:00"

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName "CreativeWorkoutBotAutoPush" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -RunLevel Highest `
    -Force

Write-Host "Done! Auto-push scheduled daily at 23:00"
