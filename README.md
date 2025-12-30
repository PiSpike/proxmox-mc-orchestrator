Proxmox Virtualized Minecraft Orchestrator (PvMO)
A full-stack Infrastructure-as-a-Service (IaaS) platform designed to automate the lifecycle of Minecraft server instances. This project transforms a Proxmox cluster into a self-service hosting environment by orchestrating Linux Containers (LXC), DNS records, and internal routing.

🚀 Features
Automated Provisioning: Instant cloning of Ubuntu-based LXC templates via the Proxmox API.

Dynamic Metadata Injection: Custom-built injection system that pushes server configurations (Seeds, Game Modes, Whitelists) directly into containers using pct push via SSH.

Smart Networking: Automatic IP assignment using VMID offsets (10.0.10.vmid-200) and dynamic Velocity Proxy routing.

Asynchronous Orchestration: Background threading handles long-running tasks (Cloning, DNS propagation, Emailing) to ensure a zero-latency UI experience.

DNS Automation: Integration with the Cloudflare API to automatically generate subdomains for new instances.

Non-Destructive Configuration: Bash-based init scripts utilizing jq to append data to system-critical JSON files (ops, whitelists) without overwriting existing entries.

🛠️ Tech Stack
Backend: Python (Flask), Gunicorn

Virtualization: Proxmox VE (LXC)

Scripting: Bash, Linux Systemd

Database: SQLite

Networking: Cloudflare API, Velocity Proxy

Communication: SMTP (Email Notifications)

🏗️ Architecture & Logic Flow
Request Layer: Admin approves a request via the Flask Dashboard.

Orchestration Layer: * A background thread is spawned.

The Proxmox API clones the master template.

DNS records are created via Cloudflare.

Velocity Proxy is updated to recognize the new backend IP.

Injection Layer: * Metadata is pushed to /root/metadata.txt inside the LXC.

The container boots and runs mc-init.sh.

Init Layer:

The script calculates its own IP, modifies server.properties, and appends the owner to the whitelist using jq.

The Java server process starts.

🔧 Installation & Setup
Proxmox Host: Ensure SSH access is enabled and a base LXC template (ID 128) is prepared with jq installed.

Web App:

Bash

git clone https://github.com/yourusername/proxmox-mc-orchestrator.git
cd proxmox-mc-orchestrator
pip install -r requirements.txt
Environment Variables: Create a .env file with your Proxmox API keys, Cloudflare Token, and SSH credentials.

Deployment: Run via Gunicorn to handle production traffic:

Bash

gunicorn --timeout 120 --workers 3 app:app
🛡️ Challenges Overcome
API Limitations: Solved the 501 Not Implemented error by pivoting from exec API calls to a robust Host-to-Container file push strategy.

Race Conditions: Implemented a retry-loop in the Bash init script to ensure configuration files are fully injected before the Minecraft server attempts to start.

Process Timeouts: Migrated from synchronous requests to asynchronous threading to bypass Gunicorn worker timeouts during infrastructure heavy-lifting.
