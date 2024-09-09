#!/bin/bash

# Default values for flags
soft_delete=false

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --soft-delete) soft_delete=true ;;
        # add other flags here
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

# Function to retrieve all commits since the last push, filtering out any intermediate amended commits
get_latest_commits_since_last_push() {
    git rev-list --no-merges --reverse origin/$(git symbolic-ref --short HEAD)..HEAD
}

# Function to check if a script was added or changed in a commit
was_script_changed() {
    local commit=$1
    local file=$2
    git diff-tree --no-commit-id --name-status -r "$commit" | grep -E "^A|^M" | grep -q "$file"
}

# Function to check if a script was deleted in a commit
was_script_deleted() {
    local commit=$1
    local file=$2
    git diff-tree --no-commit-id --name-status -r "$commit" | grep -E "^D" | grep -q "$file"
}

# Retrieve only the latest commits since the last push
commits=$(get_latest_commits_since_last_push)

# Loop through each commit
for commit in $commits; do

    # Get the list of files changed in the commit
    changed_files=$(git diff-tree --no-commit-id --name-only -r "$commit")

    for file in $changed_files; do
        # Handle added/changed scripts
        if was_script_changed "$commit" "$file"; then
            id=$(jast scripts push --file "$file")
            jast history new --id "$id" --commit "$commit"
        fi

        # Handle deleted scripts
        if was_script_deleted "$commit" "$file"; then
            id=$(basename "$file")  # Assuming the file name corresponds to the script ID
            delete_command="jast scripts delete --id \"$id\" --force"
            if [ "$soft_delete" = true ]; then
                delete_command+=" --soft-delete"
            fi
            $delete_command
        fi
    done

done

exit 0
