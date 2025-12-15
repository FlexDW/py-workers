#!/bin/bash
set -e

echo "Building and publishing werkpool to PyPI..."
poetry build
poetry publish

echo "✓ Successfully published to PyPI!"
