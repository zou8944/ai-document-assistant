# 🚀 Full Guide to Using Claude Code

Everything you need to know to crush building anything with Claude Code! This guide takes you from installation through advanced context engineering and parallel agent workflows.

## 📋 Prerequisites

- Terminal/Command line access
- Node.js installed (for Claude Code installation)
- GitHub account (for GitHub CLI integration)
- Text editor (VS Code recommended)

## 🔧 Installation

**macOS/Linux:**
```bash
npm install -g @anthropic-ai/claude-code
```

**Windows (WSL recommended):**
See detailed instructions in [install_claude_code_windows.md](../git-and-claude-code/install_claude_code_windows.md)

**Verify installation:**
```bash
claude --version
```

---

## ✅ TIP 1: CREATE AND OPTIMIZE CLAUDE.md FILES

Set up context files that Claude automatically pulls into every conversation, containing project-specific information, commands, and guidelines.

```bash
mkdir your-folder-name && cd your-folder-name
claude
```

Use the built-in command:
```
/init
```

Or create your own CLAUDE.md file based on the template in this repository. See `CLAUDE.md` for an example structure that includes:
- Project awareness and context rules
- Code structure guidelines
- Testing requirements
- Task completion workflow
- Style conventions
- Documentation standards

### File Placement Strategies

Claude automatically reads CLAUDE.md files from multiple locations:

```bash
# Root of repository (most common)
./CLAUDE.md              # Checked into git, shared with team
./CLAUDE.local.md        # Local only, add to .gitignore

# Parent directories (for monorepos)
root/CLAUDE.md           # General project info
root/frontend/CLAUDE.md  # Frontend-specific context
root/backend/CLAUDE.md   # Backend-specific context

# Home folder (applies to all sessions)
~/.claude/CLAUDE.md      # Personal preferences and global settings

# Child directories (pulled on demand)
root/components/CLAUDE.md  # Component-specific guidelines
root/utils/CLAUDE.md       # Utility function patterns
```

Claude reads files in this order:
1. Current directory
2. Parent directories (up to repository root)  
3. Home directory ~/.claude/

---

## ✅ TIP 2: SET UP PERMISSION MANAGEMENT

Configure tool allowlists to streamline development while maintaining security for file operations and system commands.

**Method 1: Interactive Allowlist**
When Claude asks for permission, select "Always allow" for common operations.

**Method 2: Use /permissions command**
```
/permissions
```
Then add:
- `Edit` (for file edits)
- `Bash(git commit:*)` (for git commits)
- `Bash(npm:*)` (for npm commands)

**Method 3: Create project settings file**
Create `.claude/settings.local.json`:
```json
{
  "allowedTools": [
    "Edit",
    "Bash(git add:*)",
    "Bash(git commit:*)",
    "Bash(npm:*)"
  ]
}
```

---

## ✅ TIP 3: INSTALL AND CONFIGURE GITHUB CLI

Set up the GitHub CLI to enable Claude to interact with GitHub for issues, pull requests, and repository management.

```bash
# Install GitHub CLI (if not already installed)
# Visit: https://github.com/cli/cli?tab=readme-ov-file#installation
# On Linux or Windows in WSL, see: https://github.com/cli/cli/blob/trunk/docs/install_linux.md

# Authenticate
gh auth login  # WSL - you'll have to copy the URL and visit it manually

# Verify setup
gh repo list
```

Claude can now use commands like:
- `gh issue create`
- `gh pr create`
- `gh pr merge`
- `gh issue list`
- `gh repo clone`

**Custom GitHub Issue Fix Command:**
Use the custom fix-github-issue slash command to automatically analyze and fix GitHub issues:

```bash
/fix-github-issue 1
```

This command will:
1. Fetch issue details using `gh issue view`
2. Analyze the problem and search relevant code
3. Implement the fix with proper testing
4. Create a commit and pull request

---

## ✅ TIP 4: SAFE YOLO MODE WITH DEV CONTAINERS

Allow Claude Code to perform any action while maintaining safety through containerization. This enables rapid development without destructive behavior on your host machine. Anthropic documentation for this is [here](https://docs.anthropic.com/en/docs/claude-code/dev-container).

**Prerequisites:**
- Install [Docker](https://www.docker.com/) and VS Code (or a VS Code fork like Windsurf/Cursor)

**🛡️ Security Features:**
The dev container in this repository provides:
- **Network isolation**: Custom firewall restricts outbound connections to whitelisted domains only
- **Essential tools**: Pre-installed with Claude Code, GitHub CLI, and development tools
- **Secure environment**: Built on Node.js 20 with ZSH and developer-friendly tools

**Setup Process:**

1. **Open project in VS Code**
2. **Activate the dev container:**
   - Press `F1` or `Ctrl/Cmd + Shift + P` to open Command Palette
   - Type and select "Dev Containers: Reopen in Container"
   - OR click the blue button in bottom-left corner → "Reopen in Container"
3. **Wait for container to build** (first time takes a few minutes)
4. **Open a new termainl** - Ctrl + J or Terminal → New Terminal
5. **Authenticate with Claude Code** - You'll have to set up Claude Code and authenticate again in the container
6. **Run Claude in YOLO mode:**
   ```bash
   claude --dangerously-skip-permissions
   ```

Note - when you authenticate with Claude Code in the container, copy the auth URL and go to it manually in your browser instead of having it open the link automatically. That won't work since you're in the container!

**Configuration Details:**
The `.devcontainer/` folder contains:
- `devcontainer.json`: VS Code container configuration with extensions and settings
- `Dockerfile`: Container image with Node.js 20, development tools, and Claude Code pre-installed
- `init-firewall.sh`: Security script that allows only necessary domains (GitHub, Anthropic API, npm registry)

This setup enables rapid prototyping while preventing access to unauthorized external services.

---

## ✅ TIP 5: INTEGRATE MCP SERVERS

Connect Claude Code to Model Context Protocol (MCP) servers for enhanced functionality like browser automation and database management. Learn more in the [MCP documentation](https://docs.anthropic.com/en/docs/claude-code/mcp).

**Add MCP servers:**
```bash
# Stdio server (real example)
claude mcp add puppeteer npx @modelcontextprotocol/server-puppeteer

# SSE server (add your own server)
claude mcp add --transport sse myserver https://example.com/sse

# HTTP server (add your own server)
claude mcp add --transport http myserver https://example.com/api
```

For Puppeteer, also run the command to install necessary dependencies:

```bash
sudo apt-get install -y libnss3-dev libxss1 libxtst6 libxrandr2 libasound2t64 libpangocairo-1.0-0 libatk1.0-0t64 libcairo-gobject2 libgtk-3-0t64 libgdk-pixbuf2.0-0
```

**Manage MCP servers:**
```bash
# List all configured servers
claude mcp list

# Get details about a specific server
claude mcp get puppeteer

# Remove a server
claude mcp remove puppeteer
```

**Test MCP integration:**
> "Use puppeteer to visit https://docs.anthropic.com/en/docs/claude-code/hooks and get me a high level overview of Claude Code Hooks."

**Configuration scopes:**
- **Local**: Project-specific, private configuration
- **Project**: Shared via `.mcp.json`, team collaboration  
- **User**: Available across all projects (`~/.claude/mcp.json`)

**Popular MCP servers:**
- **Puppeteer**: Browser automation and screenshots
- **Supabase**: Database management and real-time features
- **Neon**: Serverless PostgreSQL database operations
- **Sentry**: Error monitoring and performance tracking
- **Slack**: Team communication and notifications
- **Archon**: AI agent builder framework ([coming soon](https://github.com/coleam00/Archon))

**Advanced features:**
- Reference MCP resources using `@` mentions in your prompts
- Execute MCP prompts as slash commands
- OAuth 2.0 support for remote servers

---

## ✅ TIP 6: CONTEXT ENGINEERING

Transform your development workflow from simple prompting to comprehensive context engineering - providing AI with all the information needed for end-to-end implementation.

*Note: While your initial feature request is usually a comprehensive document outlining what you want, we provide a simpler template here to get started.*

### Quick Start

```bash
# 1. Use the provided template for your feature request
# Edit INITIAL.md (or copy INITIAL_EXAMPLE.md as a starting point)

# 2. Generate a comprehensive PRP (Product Requirements Prompt)
/generate-prp INITIAL.md

# 3. Execute the PRP to implement your feature
/execute-prp PRPs/your-feature-name.md
```

### The Context Engineering Workflow

**1. Create Your Initial Feature Request**
Use `INITIAL_EXAMPLE.md` as a template. The INITIAL.md file should contain:
- **FEATURE**: Specific description of what you want to build
- **EXAMPLES**: References to example files showing patterns to follow
- **DOCUMENTATION**: Links to relevant docs, APIs, or resources
- **OTHER CONSIDERATIONS**: Important details, gotchas, requirements

**2. Generate the PRP**
The `/generate-prp` command will:
- Research your codebase for patterns
- Search for relevant documentation
- Create a comprehensive blueprint in `PRPs/` folder
- Include validation gates and test requirements

**3. Execute the PRP**
The `/execute-prp` command will:
- Read all context from the PRP
- Create a detailed task list using TodoWrite
- Implement each component with validation
- Run tests and fix any issues
- Ensure all requirements are met

### Custom Slash Commands

The `.claude/commands/` folder contains reusable workflows:
- `generate-prp.md` - Researches and creates comprehensive PRPs
- `execute-prp.md` - Implements features from PRPs

These commands use the `$ARGUMENTS` variable to receive whatever you pass after the command name.

---

## ✅ TIP 7: PARALLEL DEVELOPMENT WITH GIT WORKTREES

Use Git worktrees to enable multiple Claude instances working on independent tasks simultaneously without conflicts.

### Manual Worktree Setup

```bash
# Create worktrees for different features
git worktree add ../project-feature-a feature-a
git worktree add ../project-feature-b feature-b

# Launch Claude in each worktree
cd ../project-feature-a && claude  # Terminal tab 1
cd ../project-feature-b && claude  # Terminal tab 2
```

**Benefits:**
- Independent tasks don't interfere
- No merge conflicts during development
- Isolated file systems for each task
- Share same Git history

**Cleanup when finished:**
```bash
git worktree remove ../project-feature-a
git branch -d feature-a
```

---

## ✅ TIP 8: AUTOMATED PARALLEL CODING AGENTS

Use automated commands to spin up multiple agents working on the same feature in parallel, then pick the best implementation.

### Setup Parallel Worktrees

```bash
/prep-parallel simple-cli 3
```

This creates three folders:
- `trees/simple-cli-1`
- `trees/simple-cli-2`
- `trees/simple-cli-3`

### Execute Parallel Implementations

1. Create a plan file (e.g., `plan.md`) describing the feature
2. Execute the parallel agents:

```bash
/execute-parallel simple-cli plan.md 3
```

Claude Code will:
- Kick off multiple agents in parallel
- Each tackles the same feature independently
- Different implementations due to LLM non-determinism
- Each saves results in `RESULTS.md` in their workspace

**Why this works:**
AI coding assistants make mistakes, so multiple attempts increase chances of success. You can review all implementations and merge the best one.

### Merge the Best Implementation

After reviewing the different implementations:

1. **Choose the best implementation:**
```bash
# Review each result
cat trees/simple-cli-1/RESULTS.md
cat trees/simple-cli-2/RESULTS.md
cat trees/simple-cli-3/RESULTS.md
```

2. **Merge the selected branch:**
```bash
# If you chose implementation #2
git checkout main
git merge simple-cli-2
git push origin main
```

3. **Clean up all worktrees:**
```bash
git worktree remove trees/simple-cli-1
git worktree remove trees/simple-cli-2
git worktree remove trees/simple-cli-3
git branch -d simple-cli-1
git branch -d simple-cli-2
git branch -d simple-cli-3
```

---

## 🎯 Quick Command Reference

| Command | Purpose |
|---------|---------|
| `/init` | Generate initial CLAUDE.md |
| `/permissions` | Manage tool permissions |
| `/clear` | Clear context between tasks |
| `ESC` | Interrupt Claude |
| `Shift+Tab` | Enter planning mode |
| `/generate-prp INITIAL.md` | Create implementation blueprint |
| `/execute-prp PRPs/feature.md` | Implement from blueprint |
| `/prep-parallel [feature] [count]` | Setup parallel worktrees |
| `/execute-parallel [feature] [plan] [count]` | Run parallel implementations |

---

## 📚 Additional Resources

- [Claude Code Documentation](https://docs.anthropic.com/en/docs/claude-code)
- [Claude Code Best Practices](https://www.anthropic.com/engineering/claude-code-best-practices)
- [MCP Server Library](https://github.com/modelcontextprotocol)
- [Context Engineering Guide](contextengineering.md)

---

## 🚀 Next Steps

1. Set up your CLAUDE.md file with project-specific context
2. Configure permissions for smooth workflow
3. Try context engineering with a small feature
4. Experiment with parallel agent development
5. Integrate MCP servers for your tech stack

Remember: Claude Code is most powerful when you provide clear context, specific instructions, and iterative feedback. Happy coding! 🎉