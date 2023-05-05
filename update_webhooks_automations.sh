#!/bin/bash

# Find all yaml files recursively
find . -type f -name "*.yaml" | while read filename
do
    # Find all lines containing "webhook_id:"
    grep -q "webhook_id:" "$filename"

    if [ $? -eq 0 ]; then
        # Insert "local_only: false" on the next line with an additional indentation level
        sed -i -e '/webhook_id:/a\        local_only: false' "$filename"
    fi
done