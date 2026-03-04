# Get Work To Do – iOS App

iPad/iPhone app with a lockscreen widget and schedule management.

## Features

- **Lockscreen widget**: Shows schedule summary; tap to open app and ask Gemini
- **Gameplan**: Displays today's and tomorrow's gameplan from your backend
- **Tasks**: Schedule items with completion checkboxes, timers, and manual items
- **Ask Gemini**: Ask questions about your schedule (uses backend `/api/ask_gemini`)
- **Settings**: Configure backend URL (e.g. `https://your-app.railway.app`)

## Setup

1. Open `GetWorkToDo.xcodeproj` in Xcode.
2. Set your **Development Team** in Signing & Capabilities for both targets.
3. Set the **backend URL** in the app Settings (or it will prompt when empty).
4. Build and run on a device or simulator.

## URL scheme

The app registers `getworktodo://ask-gemini` so the widget can open the app directly to the Ask Gemini tab.

## App Group

Both the app and widget use `group.com.getworktodo.app` to share:
- Backend base URL
- Completed task IDs
- Timer sessions
- Manual items
