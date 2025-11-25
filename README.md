# Times of Chaos (ToC) MUD

Welcome to the **Times of Chaos** project. This is a text-based MUD (Multi-User Dungeon) server based on the Merc/ROM codebase, modernized with a Docker container environment and a Python-based Web Administration interface.

## 🚀 Quick Start (Automated)

We have provided scripts to automatically install the required tools (Git, Docker, VS Code) for your operating system.

### Windows
1. Open **PowerShell** as Administrator.
2. Navigate to this folder.
3. Run:
   ```powershell
   .\scripts\setup_windows.ps1
   ```
4. **Restart your computer** if Docker was installed.
5. Launch **Docker Desktop** from the Start Menu.

### macOS
1. Open **Terminal**.
2. Navigate to this folder.
3. Run:
   ```bash
   chmod +x scripts/setup_mac.sh
   ./scripts/setup_mac.sh
   ```
4. Open **Docker** from your Applications folder to finish initialization.

### Linux (Ubuntu/Debian)
1. Open **Terminal**.
2. Navigate to this folder.
3. Run:
   ```bash
   chmod +x scripts/setup_linux.sh
   sudo ./scripts/setup_linux.sh
   ```
4. Log out and log back in to apply Docker group permissions.

---

## 🛠 Manual Installation

If you prefer to install tools manually, follow these steps for a clean OS installation.

### 1. Install Docker
Docker allows the server to run in a consistent environment regardless of your OS.

*   **Windows**: Download [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop). Install and ensure WSL 2 integration is enabled.
*   **macOS**: Download [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop). Drag to Applications and run it.
*   **Linux**:
    ```bash
    sudo apt update
    sudo apt install -y docker.io
    sudo usermod -aG docker $USER
    # Log out and back in
    ```

### 2. Install Git
*   **Windows**: Download [Git for Windows](https://git-scm.com/download/win).
*   **macOS**: `brew install git` (requires Homebrew) or install Xcode Command Line Tools.
*   **Linux**: `sudo apt install -y git`

### 3. Clone the Repository
```bash
git clone https://github.com/jeremydbean/tocGPT.git
cd tocGPT
```

---

## 🎮 Building and Running the Server

Once Docker is installed and running, you can build and start the game server with two commands.

### 1. Build the Docker Image
This compiles the C code and sets up the Python web server environment.
```bash
docker build -t toc .
```

### 2. Run the Container
This starts the server, mapping the game port (9000) and web admin port (9001) to your host machine. It also mounts the `player` and `log` directories so your data persists even if you delete the container.

**Mac / Linux:**
```bash
docker run -it --rm \
  -p 9000:9000 \
  -p 9001:9001 \
  -v $(pwd)/player:/app/player \
  -v $(pwd)/log:/app/log \
  toc
```

**Windows PowerShell:**
```powershell
docker run -it --rm `
  -p 9000:9000 `
  -p 9001:9001 `
  -v "${PWD}\player:/app/player" `
  -v "${PWD}\log:/app/log" `
  toc
```

---

## 🌐 Connecting to the Game

### Game Client (Telnet)
Connect to the MUD using any Mud Client (Mudlet, MUSHclient, or raw Telnet).
*   **Host**: `localhost`
*   **Port**: `9000`

### Web Administration
Open your web browser to access the admin dashboard.
*   **URL**: [http://localhost:9001](http://localhost:9001)
*   **Features**:
    *   View real-time server logs.
    *   Browse Mobs, Objects, and Rooms.
    *   Send "Wizinfo" broadcasts to players.
    *   Execute server commands.
    *   **Best Gear Finder**: Optimize your character's equipment.

---

## 💻 Development

### Project Structure
*   `src/`: C source code for the game server (`merc`).
*   `area/`: Game world data files (`.are`).
*   `webadmin/`: Python source code for the web interface (`server.py`).
*   `player/`: Player save files (persisted via Docker volume).
*   `log/`: Server logs (persisted via Docker volume).

### Rebuilding
After making changes to `src/` or `webadmin/`, you must rebuild the container:
```bash
docker build -t toc .
```
Then stop the running container (Ctrl+C) and run the `docker run` command again.

### VS Code Recommended Extensions
*   **C/C++** (Microsoft) - For editing the game server.
*   **Python** (Microsoft) - For editing the web admin.
*   **Docker** (Microsoft) - For editing Dockerfiles.

---

## 🆘 Troubleshooting

*   **"Bind for 0.0.0.0:9000 failed: port is already allocated"**: The server is already running. Check `docker ps` and stop the existing container.
*   **"exec format error"**: You might be trying to run a binary built for a different architecture. Always run `docker build -t toc .` locally to ensure compatibility.
*   **Web Admin not connecting**: Ensure you included `-p 9001:9001` in your `docker run` command.
