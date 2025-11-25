#!/bin/bash

echo "Setting up Times of Chaos development environment..."

# Check for sudo
if [ "$EUID" -ne 0 ]; then 
  echo "Please run as root (sudo ./scripts/setup_linux.sh)"
  exit
fi

# 1. Update and Install Git & Docker
echo "Updating package lists..."
apt-get update

if ! command -v git &> /dev/null; then
    echo "Installing Git..."
    apt-get install -y git
else
    echo "Git is already installed."
fi

if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    apt-get install -y docker.io
    systemctl enable --now docker
    usermod -aG docker $SUDO_USER
    echo "Added $SUDO_USER to docker group. You may need to log out and back in."
else
    echo "Docker is already installed."
fi

# 2. Install VS Code (Snap is easiest on Ubuntu/Debian)
if ! command -v code &> /dev/null; then
    if command -v snap &> /dev/null; then
        echo "Installing VS Code via Snap..."
        snap install code --classic
    else
        echo "Snap not found. Skipping VS Code auto-install. Please install manually."
    fi
else
    echo "VS Code is already installed."
fi

echo "----------------------------------------------------------------"
echo "Setup Complete!"
echo "1. If you are not in the 'docker' group yet, log out and log back in."
echo "2. Navigate to this folder."
echo "3. Run: docker build -t toc ."
echo "4. Run: docker run -it -p 9000:9000 -p 9001:9001 -v \$(pwd)/player:/app/player -v \$(pwd)/log:/app/log toc"
echo "----------------------------------------------------------------"
