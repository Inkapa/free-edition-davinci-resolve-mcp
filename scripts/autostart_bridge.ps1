# Starts the bridge in DaVinci Resolve without a click (Windows).
#
# The free edition runs no script at launch and accepts no external scripting, so this watcher
# clicks Workspace > Scripts > Claude_MCP_Bridge through Windows UI Automation instead. It acts only
# when a Resolve with a project open has never had a bridge: the bridge session recorded in
# Fusion.prefs belongs to another process. A bridge stopped on purpose in this Resolve stays stopped.
#
# install.py --autostart registers it as a scheduled task that starts at logon; it can also be run
# by hand:  powershell -ExecutionPolicy Bypass -File scripts\autostart_bridge.ps1
param(
    [int]$PollSeconds = 5,     # how often to look for Resolve
    [int]$GraceSeconds = 10,   # wait after a project window appears, so Resolve has finished loading
    [int]$MaxTries = 3         # clicks per Resolve process before giving up on it
)

Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$Auto = [System.Windows.Automation.AutomationElement]
$Support = Join-Path $env:APPDATA "Blackmagic Design\DaVinci Resolve\Support"
$Prefs = Join-Path $Support "Fusion\Profiles\Default\Fusion.prefs"
$Log = Join-Path $Support "ClaudeMCP\autostart.log"

function Write-Log([string]$Message) {
    try { "$(Get-Date -Format s) $Message" | Add-Content -Path $Log } catch { }
}

# Process id of the Resolve that last started the bridge, from CMCP_Session in Fusion.prefs.
function Get-BridgePid {
    try {
        $stream = [System.IO.File]::Open($Prefs, 'Open', 'Read', 'ReadWrite, Delete')
        $text = (New-Object System.IO.StreamReader($stream)).ReadToEnd()
        $stream.Close()
    } catch { return $null }
    $match = [regex]::Match($text, 'CMCP_Session\s*=\s*"([0-9a-fA-F]+)"')
    if (-not $match.Success) { return $null }
    $hex = $match.Groups[1].Value
    $bytes = [byte[]]::new($hex.Length / 2)
    for ($i = 0; $i -lt $bytes.Length; $i++) { $bytes[$i] = [Convert]::ToByte($hex.Substring(2 * $i, 2), 16) }
    try { return ([System.Text.Encoding]::UTF8.GetString($bytes) | ConvertFrom-Json).pid } catch { return $null }
}

# The first menu item called $Name under $Scope, waiting up to 3 s for a menu to open.
function Find-MenuItem($Scope, [string]$Name) {
    $isItem = New-Object System.Windows.Automation.PropertyCondition($Auto::ControlTypeProperty, [System.Windows.Automation.ControlType]::MenuItem)
    $named = New-Object System.Windows.Automation.PropertyCondition($Auto::NameProperty, $Name)
    $both = New-Object System.Windows.Automation.AndCondition($isItem, $named)
    for ($i = 0; $i -lt 20; $i++) {
        $item = $Scope.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $both)
        if ($item) { return $item }
        Start-Sleep -Milliseconds 150
    }
    return $null
}

function Open-MenuItem($Item) {
    $pattern = $null
    if ($Item.TryGetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern, [ref]$pattern)) { $pattern.Expand(); return $true }
    if ($Item.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$pattern)) { $pattern.Invoke(); return $true }
    return $false
}

function Start-Bridge($Resolve) {
    $window = $Auto::FromHandle($Resolve.MainWindowHandle)
    # the Scripts submenu and its entries open as top-level popups, so they are searched from the desktop
    foreach ($step in @(@($window, "Workspace"), @($Auto::RootElement, "Scripts"), @($Auto::RootElement, "Claude_MCP_Bridge"))) {
        $item = Find-MenuItem $step[0] $step[1]
        if (-not $item -or -not (Open-MenuItem $item)) { return "no menu item '$($step[1])'" }
    }
    return $null
}

Write-Log "watching for Resolve"
$tries = @{}
$seen = @{}
while ($true) {
    $resolve = Get-Process Resolve -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowTitle -like "DaVinci Resolve - *" } | Select-Object -First 1
    if ($resolve -and (Get-BridgePid) -ne $resolve.Id) {
        if (-not $seen.ContainsKey($resolve.Id)) { $seen[$resolve.Id] = Get-Date }
        $ready = ((Get-Date) - $seen[$resolve.Id]).TotalSeconds -ge $GraceSeconds
        if ($ready -and $tries[$resolve.Id] -lt $MaxTries) {
            $tries[$resolve.Id] = $tries[$resolve.Id] + 1
            $problem = Start-Bridge $resolve
            if ($problem) { Write-Log "Resolve $($resolve.Id): $problem" }
            else { Write-Log "Resolve $($resolve.Id): started the bridge" }
            Start-Sleep -Seconds 10  # give the bridge time to record its session
        }
    }
    Start-Sleep -Seconds $PollSeconds
}
