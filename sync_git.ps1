$ProjectDir = $PSScriptRoot
$LogFile = "$ProjectDir\logs\sync.log"
$Interval = 60

# Create logs folder
if (!(Test-Path "$ProjectDir\logs")) {
    New-Item -ItemType Directory -Path "$ProjectDir\logs" -Force | Out-Null
}

function Log {
    param([string]$msg)
    $t = Get-Date -Format "yyyy.MM.dd HH:mm:ss"
    "$t - $msg" | Out-File -FilePath $LogFile -Append -Encoding UTF8
    Write-Host "$t - $msg"
}

Log "This script tracks project files every $Interval seconds and updates it if needed."

while ($true) {
    try {
        Set-Location $ProjectDir

        # === CHECK GIT REPO ===
        if (!(Test-Path "$ProjectDir\.git")) {
            Log "ERROR: No .git folder found in $ProjectDir"
            Log "Fix: Move this script + project files into the cloned repo folder."
            Log "For adding this script to Windows Autostart, use .bat file from ./additional"
            Start-Sleep -Seconds $Interval
            continue
        }

        # === RESTORE DELETED FILES ===
        $status = git status --porcelain 2>$null
        if ($status) {
            Log "Changes detected:"
            $status | ForEach-Object { Log "  $_" }
            git restore . 2>&1 | ForEach-Object { Log $_ }
        }

        # === GIT SYNC ===
        git fetch origin main 2>&1 | ForEach-Object { Log $_ }

        $local = git rev-parse HEAD 2>$null
        $remote = git rev-parse origin/main 2>$null

        if ($local -and $remote -and $local -ne $remote) {
            Log "Local:  $local"
            Log "Remote: $remote"
            Log "Update found. Pulling..."
            git pull origin main 2>&1 | ForEach-Object { Log $_ }

            Log "Rebuilding containers..."
            docker compose --profile main --profile tools up -d --build 2>&1 | ForEach-Object { Log $_ }

            Log "Update complete."
        }
    }
    catch {
        Log "ERROR: $($_.Exception.Message)"
    }

    Start-Sleep -Seconds $Interval
}
