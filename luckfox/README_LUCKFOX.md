# Luckfox notes (Buildroot)

Golden path (Windows ADB forward)
- RTSP: `adb forward tcp:8554 tcp:554`
- SSH:  `adb forward tcp:2222 tcp:22`
- RTSP URL: `rtsp://127.0.0.1:8554/live/0`
- SSH: `ssh -p 2222 root@127.0.0.1`

Fix SSH (Buildroot UsePAM)
- On device: `luckfox/scripts/fix_sshd.sh`
- Removes `UsePAM` and restarts sshd.

Fix RTSP autostart
- Find binary: `luckfox/scripts/find_rtsp_bin.sh`
- Install init script: `luckfox/scripts/install_rtsp_autostart.sh`

Time sync
- From host: `luckfox/scripts/sync_time_from_host.sh`

Deploy from host (WSL)
- `./scripts/deploy_luckfox.sh`
