#!/bin/bash
# Build Tailwind CSS for production

echo "Building Tailwind CSS..."

# Detect architecture
if [[ $(uname -m) == "arm64" ]]; then
    TAILWIND_BIN="./tailwindcss-macos-arm64"
else
    TAILWIND_BIN="./tailwindcss-macos-x64"
fi

# Build CSS
$TAILWIND_BIN build ./static/css/input.css -o ./static/css/output.css --minify

echo "Done! CSS built to ./static/css/output.css"
