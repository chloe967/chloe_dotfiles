#!/bin/bash
set -e

DOTFILES_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing dotfiles from $DOTFILES_DIR"

# Backup existing files (only real files, not existing symlinks)
for file in .zshrc .zprofile; do
    if [ -f "$HOME/$file" ] && [ ! -L "$HOME/$file" ]; then
        echo "Backing up ~/$file -> ~/${file}.backup"
        cp "$HOME/$file" "$HOME/${file}.backup"
    fi
done

# Create symlinks
ln -sf "$DOTFILES_DIR/zshrc" "$HOME/.zshrc"
ln -sf "$DOTFILES_DIR/zprofile" "$HOME/.zprofile"

# Make greeting executable
chmod +x "$DOTFILES_DIR/greeting.sh"

echo ""
echo "Done! Dotfiles installed:"
echo "  ~/.zshrc    -> $DOTFILES_DIR/zshrc"
echo "  ~/.zprofile -> $DOTFILES_DIR/zprofile"
echo ""
echo "Open a new terminal to see your squid!"
