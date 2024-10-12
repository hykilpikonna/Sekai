param (
    [int]$serialNumber
)

# Validate the input
if ($serialNumber -lt 1 -or $serialNumber -gt 3) {
    Write-Host "Please provide a valid argument: 1, 2, or 3."
    exit
}

# Set ADB Serial based on the input
$adbSerial = "emulator-55" + (54 + ($serialNumber - 1) * 2)  # 5554 for 1, 5556 for 2, 5558 for 3
$env:ADB_SERIAL = $adbSerial
$env:MODE = "helper"
$env:CONFIG_PATH = "config-clover.toml"

while ($true) {
    python -m automata
}
