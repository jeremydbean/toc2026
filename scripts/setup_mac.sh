#!/bin/bash

echo "Setting up Times of Chaos development environment..."

# 1. Install Homebrew
if ! command -v brew &> /dev/null; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add brew to path for immediate use (standard locations)
    if [ -f "/opt/homebrew/bin/brew" ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -f "/usr/local/bin/brew" ]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
else
    echo "Homebrew is already installed."
fi

# 2. Install Git
if ! command -v git &> /dev/null; then
    echo "Installing Git..."
    brew install git
else
    echo "Git is already installed."
fi

# 3. Install Docker
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    brew install --cask docker
    echo "Docker installed. Please open 'Docker' from your Applications folder to finish setup."
else
    echo "Docker is already installed."
fi

# 4. Install VS Code
if ! command -v code &> /dev/null; then
    echo "Installing VS Code..."
    brew install --cask visual-studio-code
else
    echo "VS Code is already installed."
fi

echo "----------------------------------------------------------------"
echo "Setup Complete!"
echo "1. Open 'Docker' from Applications if not running."
echo "2. Open Terminal and navigate to this folder."
echo "3. Run: docker build -t toc ."
echo "4. Run: docker run -it -p 9000:9000 -p 9001:9001 -v \$(pwd)/player:/app/player -v \$(pwd)/log:/app/log toc"
echo "----------------------------------------------------------------"
