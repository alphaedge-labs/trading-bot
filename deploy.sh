#!/bin/bash

API_PROFILE="trading-bot"

echo "🚀 Starting the build process for profile: $API_PROFILE..."
docker compose --profile $API_PROFILE build
if [ $? -eq 0 ]; then
  echo "✅ Build completed successfully for profile: $API_PROFILE!"
else
  echo "❌ Build failed for profile: $API_PROFILE. Please check the errors above. 💔"
  exit 1
fi

echo "🛑 Shutting down any running containers for profile: $API_PROFILE..."
docker compose --profile $API_PROFILE down
if [ $? -eq 0 ]; then
  echo "✅ Containers stopped successfully for profile: $API_PROFILE! 🧹"
else
  echo "❌ Failed to stop containers for profile: $API_PROFILE. Please check for issues. 😢"
  exit 1
fi

echo "🔧 Starting up containers in detached mode for profile: $API_PROFILE..."
docker compose --profile $API_PROFILE up -d
if [ $? -eq 0 ]; then
  echo "🎉 Containers are up and running for profile: $API_PROFILE! 🌟"
  echo "🌐 Visit your application to check if everything is working as expected!"
else
  echo "❌ Failed to start containers for profile: $API_PROFILE. Please troubleshoot. 🛠️"
  exit 1
fi

echo "✨ Deployment completed successfully for profile: $API_PROFILE! 🎉"