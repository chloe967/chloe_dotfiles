export PATH="/opt/homebrew/opt/mysql-client/bin:$HOME/.local/bin:$PATH"
export FIREFOX_PATH=/Applications/Firefox.app/Contents/MacOS/firefox
export GECKODRIVER_PATH=/opt/homebrew/bin/geckodriver
export APP_POSITION_X=0
export APP_POSITION_Y=-1200

# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="$('/opt/homebrew/Caskroom/miniconda/base/bin/conda' 'shell.zsh' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__conda_setup"
else
    if [ -f "/opt/homebrew/Caskroom/miniconda/base/etc/profile.d/conda.sh" ]; then
        . "/opt/homebrew/Caskroom/miniconda/base/etc/profile.d/conda.sh"
    else
        export PATH="/opt/homebrew/Caskroom/miniconda/base/bin:$PATH"
    fi
fi
unset __conda_setup
# <<< conda initialize <<<


export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# Quick git push
gp() { git add -A && git commit -m "i just need to lock in" && git push -u origin HEAD }

# Aliases
alias rr='source ~/.zshrc'
alias g='cd ~/Development/gym'
alias cdg='cd ~/git'
alias cdd='cd ~/Development'
alias cds='cd ~/Development/seed'
alias ga='git add .'
alias gb='git checkout -b'
alias gc='git checkout main'
alias gm='git commit -m'
alias gwip='git add . && git commit -m "wip" --no-verify'
alias gps='git push origin'
alias gr='git rebase -i origin/main'
alias gr2='git rebase -i HEAD~2'
alias gr3='git rebase -i HEAD~3'
alias gs='git status'
alias py='python3'
alias python='python3'
alias ca='conda activate deeptune311'
alias dr='doppler run --'
alias dra='doppler run -- bash ./recorder/image/start-compose.sh'
alias drs='doppler run -- bash ./recorder/image/start-compose.sh'
alias drr='doppler run -- python -m recorder.main'
alias drss='doppler run -- python -m recorder.test_snapshot'
alias drb='doppler run -- bash'
alias drp='doppler run -- python -m'
alias drd='doppler run -- ./dashboard/start-dev.sh'
alias drt='doppler run -- bash core/anthropic/mcp_client/start-taiga.sh'
alias dre='doppler run -- python -m core.anthropic.lib.export_problems.app --project_id'
alias drdp='doppler run -- python -m core.anthropic.computer_mcp.deploy.build_and_deploy --problem_export_id'
alias dred='doppler run -- python -m core.anthropic.lib.export_and_deploy.app'
alias dri='doppler run -- python -m core.anthropic.lib.import_evals.main'
alias drsm='doppler run -- python -m recorder.test_simulate'
alias drsmt='doppler run -- python -m recorder.test_simulate_tasks'
alias ssht='ssh -i /Users/mao/Development/ssh/tim-downloader.pem ubuntu@ec2-54-84-134-209.compute-1.amazonaws.com'
alias sshm='ssh -i /Users/mao/Development/ssh/michelle-ec2-keys.pem ubuntu@ec2-3-82-232-202.compute-1.amazonaws.com'
alias ec2s='aws ec2 start-instances --instance-ids i-09a5dada59f487d1a'
alias ec2sp='aws ec2 stop-instances --instance-ids i-09a5dada59f487d1a'
alias iosv='cd core/anthropic/ios_mcp/src/ios_app/viewer && npm start'
alias csp='claude --dangerously-skip-permissions'
alias dclaude='claude --dangerously-skip-permissions'
alias cursor-ssh='cursor --remote ssh-remote+ben-gym-ssh /home/ubuntu'

# Dotfiles directory
DOTFILES_DIR="$(dirname "$(readlink -f ~/.zshrc)" 2>/dev/null || dirname "$(perl -e 'use Cwd "abs_path"; print abs_path(shift)' ~/.zshrc)")"

# Load secrets (tokens, etc.) - not tracked in git
[ -f "$DOTFILES_DIR/.secrets" ] && source "$DOTFILES_DIR/.secrets"

# Greeting
source "$DOTFILES_DIR/greeting.sh"
