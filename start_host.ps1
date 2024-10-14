$env:MODE = "host"
$env:CONFIG_PATH = "config.toml"
$env:LOG_PATH = "log-host"

while ($true) {
    python -m automata
}