#!/bin/bash
set -e

DOTFILES_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing dotfiles from $DOTFILES_DIR"

# Backup existing files (only real files, not existing symlinks)
for file in .zshrc .zprofile .bashrc; do
    if [ -f "$HOME/$file" ] && [ ! -L "$HOME/$file" ]; then
        echo "Backing up ~/$file -> ~/${file}.backup"
        cp "$HOME/$file" "$HOME/${file}.backup"
    fi
done

# Create symlinks
ln -sf "$DOTFILES_DIR/zshrc" "$HOME/.zshrc"
ln -sf "$DOTFILES_DIR/zprofile" "$HOME/.zprofile"
ln -sf "$DOTFILES_DIR/bashrc" "$HOME/.bashrc"

# Symlink Claude Code settings (just the file, not the whole ~/.claude dir)
mkdir -p "$HOME/.claude"
if [ -f "$HOME/.claude/settings.json" ] && [ ! -L "$HOME/.claude/settings.json" ]; then
    echo "Backing up ~/.claude/settings.json -> ~/.claude/settings.json.backup"
    cp "$HOME/.claude/settings.json" "$HOME/.claude/settings.json.backup"
fi
ln -sf "$DOTFILES_DIR/.claude/settings.json" "$HOME/.claude/settings.json"
ln -sf "$DOTFILES_DIR/.claude/CLAUDE.md" "$HOME/.claude/CLAUDE.md"
ln -sfn "$DOTFILES_DIR/.claude/skills" "$HOME/.claude/skills"
ln -sfn "$DOTFILES_DIR/.claude/agents" "$HOME/.claude/agents"

# Install MCP servers from .claude/mcp/ definitions
if command -v claude &> /dev/null; then
    # stdio MCP servers (from .claude/mcp/*.json)
    for mcp_file in "$DOTFILES_DIR/.claude/mcp"/*.json; do
        [ -f "$mcp_file" ] || continue
        server_name="$(basename "$mcp_file" .json)"
        echo "Adding MCP server: $server_name"
        claude mcp remove --scope user "$server_name" 2>/dev/null || true
        claude mcp add-json --scope user "$server_name" "$(cat "$mcp_file")"
    done

    # HTTP MCP servers (OAuth-based, require browser auth after install)
    echo "Adding MCP server: granola"
    claude mcp remove --scope user granola 2>/dev/null || true
    claude mcp add granola --transport http https://mcp.granola.ai/mcp --scope user
else
    echo "  (skipping MCP setup — claude not found)"
fi

# Rocky (project-manager Slack bot) as a systemd *user* service.
# It's a resident Socket Mode listener, so it needs supervision that survives
# reboots, crashes and OOM kills. Config lives in slack-bot/rocky.service.
if command -v systemctl &> /dev/null && systemctl --user show-environment &> /dev/null; then
    echo "Installing rocky.service (project-manager Slack bot)"
    # Without lingering, the user manager is torn down with the last login
    # session and nothing restarts at boot. Non-fatal: needs polkit/sudo on
    # some hosts, and everything else here still works without it.
    loginctl enable-linger "$USER" 2>/dev/null \
        || echo "  (warning: could not enable linger; rocky won't survive logout/reboot)"
    mkdir -p "$HOME/.config/systemd/user"
    ln -sf "$DOTFILES_DIR/slack-bot/rocky.service" "$HOME/.config/systemd/user/rocky.service"
    chmod +x "$DOTFILES_DIR/slack-bot/rocky.sh"
    systemctl --user daemon-reload
    systemctl --user enable --now rocky
else
    echo "  (skipping rocky.service — no systemd user session)"
fi

# Make greeting executable
chmod +x "$DOTFILES_DIR/greeting.sh"

echo ""
echo "Done! Dotfiles installed:"
echo "  ~/.zshrc    -> $DOTFILES_DIR/zshrc"
echo "  ~/.zprofile -> $DOTFILES_DIR/zprofile"
echo "  ~/.bashrc   -> $DOTFILES_DIR/bashrc"
echo "  ~/.claude/settings.json -> $DOTFILES_DIR/.claude/settings.json"
echo "  ~/.claude/CLAUDE.md     -> $DOTFILES_DIR/.claude/CLAUDE.md"
echo "  ~/.claude/skills/       -> $DOTFILES_DIR/.claude/skills/"
echo "  ~/.claude/agents/       -> $DOTFILES_DIR/.claude/agents/"
echo "  MCP servers             <- $DOTFILES_DIR/.claude/mcp/*.json"
echo "  rocky.service (systemd) <- $DOTFILES_DIR/slack-bot/rocky.service"
echo ""
echo "Open a new terminal to see your squid!"
