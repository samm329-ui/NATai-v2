"""
Smart Filler System for N.A.T. AI Assistant
Adds immediate responses to make the AI feel faster and more responsive
Uses context-aware fillers based on whether user input is question or statement
"""

import random
import re

# Question patterns
QUESTION_PATTERNS = [
    r'^what\s', r'^how\s', r'^why\s', r'^who\s', r'^where\s', r'^when\s',
    r'^can\s', r'^could\s', r'^would\s', r'^should\s', r'^do\s', r'^does\s',
    r'^is\s', r'^are\s', r'^will\s', r'^have\s', r'^has\s', r'^did\s',
    r'\?$', r'\? ', r'how come', r"what's the", r"what is the"
]

# Statement/command patterns
STATEMENT_PATTERNS = [
    r'^open\s', r'^start\s', r'^launch\s', r'^run\s', r'^execute\s',
    r'^create\s', r'^make\s', r'^delete\s', r'^copy\s', r'^move\s',
    r'^type\s', r'^press\s', r'^click\s', r'^scroll\s', r'^go to\s',
    r'^search\s', r'^find\s', r'^show\s', r'^tell\s', r'^give\s',
    r'^write\s', r'^save\s', r'^send\s', r'^play\s', r'^stop\s',
    r'^turn\s', r'^switch\s', r'^set\s', r'^add\s', r'^remove\s'
]

def is_question(text: str) -> bool:
    """Check if the user message is a question"""
    text_lower = text.lower().strip()
    for pattern in QUESTION_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False

def is_statement_or_command(text: str) -> bool:
    """Check if the user message is a statement/command"""
    text_lower = text.lower().strip()
    for pattern in STATEMENT_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False


FILLER_RESPONSES = {
    # Question fillers - curious, engaging
    "question": [
        "That's a great question, Boss! Let me find that for you...",
        "Interesting question! Looking into it now...",
        "Great question! Searching for the best answer...",
        "Excellent question! Let me research that...",
        "Good one, Boss! Finding the information now...",
        "I love that question! Let me check...",
    ],
    # Action/command fillers - ready to act
    "action": [
        "On it, Boss!",
        "Got it!",
        "Right away, Boss!",
        "Consider it done!",
        "Working on it now!",
        "One moment, Boss!",
        "I'll take care of that!",
        "Let me do that for you!",
    ],
    # Web search specific
    "web_search": [
        "Let me search the web for that, Boss...",
        "Searching the internet now...",
        "One moment! Looking up the best results...",
        "Finding the latest information for you...",
    ],
    "open_web": [
        "Opening that right now, Boss!",
        "Launching it for you!",
        "On it! Opening...",
        "Got it! Starting up...",
    ],
    # File operations
    "create_file": [
        "Creating that file for you, Boss...",
        "Setting up the file now...",
        "Writing the file for you...",
    ],
    "create_folder": [
        "Creating the folder now, Boss...",
        "Making the new folder...",
        "Setting up the folder...",
    ],
    "open_folder": [
        "Opening that folder for you...",
        "Launching the folder now...",
    ],
    "open_file": [
        "Opening that file for you...",
        "Launching the file...",
    ],
    "open_app": [
        "Starting that app now, Boss...",
        "Launching {app}...",
        "Opening the application...",
    ],
    "list_directory": [
        "Checking that directory now...",
        "Looking at what's in there...",
    ],
    # Terminal
    "run_terminal": [
        "Running that command now...",
        "Executing the command...",
        "Working on it...",
    ],
    # Desktop control
    "type_text": [
        "Typing that for you now...",
        "Starting to type...",
    ],
    "press_key": [
        "Pressing that key now...",
    ],
    "hotkey": [
        "Executing that shortcut...",
    ],
    "mouse_move": [
        "Moving the mouse...",
    ],
    "mouse_click": [
        "Clicking that spot...",
    ],
    "mouse_scroll": [
        "Scrolling now...",
    ],
    "screenshot": [
        "Taking a screenshot...",
    ],
    # Chat/General - neutral
    "chat": [
        "Let me think about that, Boss...",
        "Processing your request...",
        "Working on it...",
        "One moment...",
    ],
    "realtime": [
        "Looking that up for you...",
        "Finding the latest information...",
    ],
}

def get_filler(action_type: str = "chat", context: str = None) -> str:
    """Get a smart filler response based on action type and context"""
    
    # Check for specific action types first
    if action_type in FILLER_RESPONSES:
        fillers = FILLER_RESPONSES[action_type]
        filler = random.choice(fillers)
        if context and "{app}" in filler:
            return filler.replace("{app}", context)
        return filler
    
    # Default to question or action based on action_type
    if action_type in ["web_search", "open_web"]:
        return random.choice(FILLER_RESPONSES["web_search"])
    elif action_type in ["type_text", "press_key", "hotkey", "mouse_move", "mouse_click", "mouse_scroll", "screenshot"]:
        return random.choice(FILLER_RESPONSES["action"])
    elif action_type in ["create_file", "create_folder", "open_folder", "open_file", "open_app"]:
        return random.choice(FILLER_RESPONSES["action"])
    else:
        return random.choice(FILLER_RESPONSES["chat"])

def get_filler_for_message(user_message: str, action_type: str = "chat") -> str:
    """Smart filler selection based on user message type and action"""
    message_type = "question" if is_question(user_message) else "action" if is_statement_or_command(user_message) else "chat"
    
    # If it's a specific action, use action-specific filler
    if action_type in FILLER_RESPONSES:
        return get_filler(action_type)
    
    # Otherwise use message-type based filler
    if message_type == "question":
        return random.choice(FILLER_RESPONSES["question"])
    elif message_type == "action":
        return random.choice(FILLER_RESPONSES["action"])
    else:
        return random.choice(FILLER_RESPONSES["chat"])

def get_typing_filler() -> str:
    """Filler while AI is generating response"""
    return random.choice([
        "Let me think about that...",
        "Processing your request...",
        "Working on it, Boss...",
        "One moment...",
    ])