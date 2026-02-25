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

# Symlink Claude Code settings (just the file, not the whole ~/.claude dir)
mkdir -p "$HOME/.claude"
if [ -f "$HOME/.claude/settings.json" ] && [ ! -L "$HOME/.claude/settings.json" ]; then
    echo "Backing up ~/.claude/settings.json -> ~/.claude/settings.json.backup"
    cp "$HOME/.claude/settings.json" "$HOME/.claude/settings.json.backup"
fi
ln -sf "$DOTFILES_DIR/.claude/settings.json" "$HOME/.claude/settings.json"

# Install MCP servers from .claude/mcp/ definitions
if command -v claude &> /dev/null; then
    for mcp_file in "$DOTFILES_DIR/.claude/mcp"/*.json; do
        [ -f "$mcp_file" ] || continue
        server_name="$(basename "$mcp_file" .json)"
        echo "Adding MCP server: $server_name"
        claude mcp remove --scope user "$server_name" 2>/dev/null || true
        claude mcp add-json --scope user "$server_name" "$(cat "$mcp_file")"
    done
else
    echo "  (skipping MCP setup — claude not found)"
fi

# Make greeting executable
chmod +x "$DOTFILES_DIR/greeting.sh"

echo ""
echo "Done! Dotfiles installed:"
echo "  ~/.zshrc    -> $DOTFILES_DIR/zshrc"
echo "  ~/.zprofile -> $DOTFILES_DIR/zprofile"
echo "  ~/.claude/settings.json -> $DOTFILES_DIR/.claude/settings.json"
echo "  MCP servers             <- $DOTFILES_DIR/.claude/mcp/*.json"
echo ""
echo "Open a new terminal to see your squid!"
