#!/bin/bash
# Creates the Zettelkasten vault structure recommended by:
# https://github.com/lucasrosati/claude-code-memory-setup

set -e

VAULT="${OBSIDIAN_VAULT_PATH:?Set OBSIDIAN_VAULT_PATH in your .env}"
PROJECT="${OBSIDIAN_PROJECT_NAME:?Set OBSIDIAN_PROJECT_NAME in your .env}"

echo "Creating vault at: $VAULT"

mkdir -p "$VAULT"/{permanent,inbox,fleeting,templates,logs,references}
mkdir -p "$VAULT/$PROJECT"/{architecture,pipeline,data,features,logs}
mkdir -p "$VAULT"/chats/{code,web}
mkdir -p "$VAULT"/graphify/"$PROJECT"

# Default note template
cat > "$VAULT/templates/default-note.md" << 'EOF'
---
title: {{title}}
tags: []
created: {{date}}
updated: {{date}}
status: draft
type: permanent
---

# {{title}}

## Context

## Details

## Related links
EOF

# Starter architecture note
cat > "$VAULT/$PROJECT/architecture/decisions.md" << EOF
---
title: Architecture Decisions
tags: [$PROJECT, architecture]
created: $(date +%Y-%m-%d)
updated: $(date +%Y-%m-%d)
status: active
type: permanent
---

# Architecture Decisions — $PROJECT

## Stack

## Key Decisions

## Patterns to Follow

## Things to Avoid
EOF

# CLAUDE.md for the vault
cat > "$VAULT/CLAUDE.md" << 'EOF'
# Vault — Instructions for Claude Code

## What is this vault
Centralized knowledge base for all projects.
Persistent memory across sessions.

## Zettelkasten Rules

### Note creation
- Use wikilinks: [[note-name]]
- Mandatory YAML frontmatter on every note
- Filenames in kebab-case
- 1 concept per permanent note
- Minimum 2 wikilinks per note

### Standard frontmatter
---
title: Note Name
tags: [project, topic]
created: YYYY-MM-DD
updated: YYYY-MM-DD
status: active
type: permanent
---

### Never do
- Don't delete notes without asking
- Don't use markdown links for internal notes (use wikilinks)
- Don't create notes without frontmatter
EOF

echo ""
echo "Vault ready at: $VAULT"
echo ""
echo "Next steps:"
echo "  1. pip install graphifyy && graphify install"
echo "  2. cd your-repo && graphify . --obsidian --obsidian-dir $VAULT/graphify/$PROJECT"
echo "  3. Fill in $VAULT/$PROJECT/architecture/decisions.md with your project context"
