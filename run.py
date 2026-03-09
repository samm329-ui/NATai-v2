import uvicorn

if __name__ == "__main__":
    print("==================================================")
    print("Starting N.A.T. AI Assistant (Natasha)...")
    print("==================================================")
    # This tells Python to look inside the 'app' folder for 'main.py' 
    # and run the 'app' variable inside it.
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
