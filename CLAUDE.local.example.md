# Garvis Coach -- Local configuration

> Copy this file to `CLAUDE.local.md` and fill in your values.
> CLAUDE.local.md is gitignored -- it stays private to your setup.

## Network

- Server IP: YOUR_IP (e.g. 192.168.1.100)
- InfluxDB: http://YOUR_IP:8087
- Grafana: http://YOUR_IP:3000
- MCP garmin-coach: http://YOUR_IP:8765/mcp
- MCP garmin-toolbox: http://YOUR_IP:8770/mcp
- MCP grafana: http://YOUR_IP:8768/mcp

## SSH access (if running on a remote server/NAS)

- SSH alias: `ssh your-server`
- Docker commands need `sudo` prefix

## Athlete profile

- HR Max: XXX bpm
- HR Rest: XX bpm
- LTHR: XXX bpm
- FTP: XXX W
- Weight: XX kg
- Age: XX
- Timezone: Europe/Paris (or your timezone)

## Paths

- Docker project root: /path/to/garvis-coach/
- SMB share (if applicable): \\\\YOUR_IP\\docker\\projects\\garvis-coach\\
- Activity dumps: ./data/activities/

## Training plan context

- Current plan: (describe your current training focus)
- Current cycle/week: Cycle X, Week Y
- Key constraints: (injuries, schedule, terrain, etc.)

## Health notes (private -- never commit)

- (Any relevant health context for training decisions)
