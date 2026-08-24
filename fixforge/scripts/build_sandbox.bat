@echo off
echo Building FixForge Docker Sandbox Image...
docker build -t fixforge-sandbox:latest -f sandbox/Dockerfile.sandbox .
echo Build Complete!
