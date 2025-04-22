# main.py
import codrone_edu
from codrone_edu.drone import *
import speech_recognition as sr
import openai
import os
import json
import time
import threading
import queue
import io
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from typing import Union # <--- IMPORT THIS

# --- Configuration ---
# ... (rest of your config code remains the same) ...

# --- Global State ---
# WARNING: Global state can be tricky in web apps, especially with scaling.
# For this single-drone scenario, it's manageable.
drone: Union[Drone, None] = None # <--- USE Union HERE
drone_command_queue = queue.Queue()
drone_processor_stop_event = threading.Event()
drone_processor_thread = None
# Track drone state (simple version) - needs careful synchronization if accessed/modified outside processor thread
drone_state = {"connected": False, "flying": False}

# ... (rest of your code remains the same) ...


# --- ChatGPT Interaction (Keep as is, but add error handling for client init) ---
def get_drone_command_from_text(text):
    """Sends text to ChatGPT and asks for a structured drone command."""
    if not client:
         print("Error: OpenAI client not initialized.")
         return {"command": "error", "parameters": {"message": "OpenAI client not available"}}

    print(f"Sending to ChatGPT: '{text}'")
    try:
        system_prompt = f"""
        You are an AI assistant interpreting voice commands for a CoDrone EDU drone.
        The available commands are: {', '.join(ALLOWED_COMMANDS)}.
        Some commands take parameters:
        - move_forward, move_backward, move_left, move_right, turn_left, turn_right, move_up, move_down: require 'distance' (float, default 50.0), 'unit' (string, default cm), and 'speed' (float, default 1.0).
        - set_throttle, set_yaw, set_roll, set_pitch: require 'power' (int, -100 to 100).

        Analyze the user's text and determine the single most likely drone command.
        Respond ONLY with a JSON object containing the 'command' (string) and any necessary 'parameters' (object).
        Example 1: User says "fly forward for 2 seconds" -> {{"command": "move_forward", "parameters": {{"duration": 2.0}}}}
        Example 2: User says "take off" -> {{"command": "takeoff", "parameters": {{}}}}
        Example 3: User says "turn left" -> {{"command": "turn_left", "parameters": {{"duration": 1.0}}}}
        Example 4: User says "stop everything" -> {{"command": "emergency_stop", "parameters": {{}}}}
        Example 5: User says "increase altitude" -> {{"command": "move_up", "parameters": {{"duration": 1.0}}}}
        Example 6: User says "set throttle to 50" -> {{"command": "set_throttle", "parameters": {{"power": 50}}}}

        If the command is unclear or not on the allowed list, respond with: {{"command": "unknown", "parameters": {{}}}}
        Do not add any explanations outside the JSON structure.
        """
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=100
        )

        response_content = response.choices[0].message.content
        print(f"ChatGPT Response: {response_content}")

        # Clean potential markdown backticks
        if response_content.startswith("```json"):
            response_content = response_content[7:-3].strip()
        elif response_content.startswith("```"):
            response_content = response_content[3:-3].strip()

        command_data = json.loads(response_content)

        if isinstance(command_data, dict) and "command" in command_data:
             print('Command data:', command_data)
             if command_data["command"] in ALLOWED_COMMANDS or command_data["command"] == "unknown":
                return command_data
             else:
                print(f"Warning: ChatGPT proposed a disallowed command: {command_data['command']}")
                return {"command": "unknown", "parameters": {}}
        else:
            print(f"Warning: Invalid JSON structure from ChatGPT: {command_data}")
            return {"command": "unknown", "parameters": {}}

    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from ChatGPT response: {response_content}")
        return {"command": "unknown", "parameters": {}}
    except openai.APIError as e:
        print(f"OpenAI API Error: {e}")
        return {"command": "error", "parameters": {"message": f"OpenAI API Error: {e}"}}
    except Exception as e:
        print(f"An unexpected error occurred during ChatGPT interaction: {e}")
        return {"command": "error", "parameters": {"message": f"ChatGPT Error: {e}"}}


# --- Drone Command Execution (Keep as is, but use global drone_state) ---
def execute_drone_command(drone_instance, command_data):
    """Executes the corresponding CoDrone EDU command."""
    global drone_state # Modify global state

    if not drone_instance or not drone_instance.is_connected():
        print("Error: Drone is not connected.")
        # Optionally update state here if needed, though connect/disconnect should handle it
        # drone_state["connected"] = False
        # drone_state["flying"] = False
        return # Cannot execute if not connected

    command = command_data.get("command", "unknown")
    params = command_data.get("parameters", {})

    print(f"Attempting to execute: {command} with params: {params}")

    try:
        # --- Update drone_state BEFORE executing potentially blocking commands ---
        if command == "takeoff":
            print("Executing: Takeoff")
            drone_instance.takeoff()
            drone_instance.hover(1) # Hover briefly after takeoff
            drone_state["flying"] = True # Update state *after* successful takeoff potentially
        elif command == "land":
            print("Executing: Land")
            drone_instance.land()
            drone_state["flying"] = False
        elif command == "emergency_stop":
            print("Executing: Emergency Stop")
            drone_instance.emergency_stop()
            drone_state["flying"] = False
        elif command == "flip":
            print("Executing: Flip")
            drone_instance.flip()
        elif command == "spiral":
            print("Executing: Spiral")
            drone_instance.spiral()
        elif command == "hover":
            duration = float(params.get("duration", 3.0)) # Default hover 3s
            print(f"Executing: Hover for {duration}s")
            drone_instance.hover(duration)
        elif command == "move_forward":
            distance = float(params.get("distance", 50.0))
            unit = str(params.get("unit", "cm"))
            speed = float(params.get("speed", 1.0))
            print(f"Executing: Move Forward for {distance} {unit} {speed}")
            drone_instance.move_forward(distance, unit, speed)
        elif command == "move_backward":
            distance = float(params.get("distance", 50.0))
            unit = str(params.get("unit", "cm"))
            speed = float(params.get("speed", 1.0))
            print(f"Executing: Move Backward for {distance} {unit} {speed}")
            drone_instance.move_backward(distance, unit, speed)
        elif command == "move_left":
            distance = float(params.get("distance", 50.0))
            unit = str(params.get("unit", "cm"))
            speed = float(params.get("speed", 1.0))
            print(f"Executing: Move Left for {distance} {unit} {speed}")
            drone_instance.move_left(distance, unit, speed)
        elif command == "move_right":
            distance = float(params.get("distance", 50.0))
            unit = str(params.get("unit", "cm"))
            speed = float(params.get("speed", 1.0))
            print(f"Executing: Move Right for {distance} {unit} {speed}")
            drone_instance.move_right(distance, unit, speed)
        elif command == "turn_left":
            duration = float(params.get("duration", 1.0))
            power = 50
            print(f"Executing: Turn Left (timed {duration}s)")
            drone_instance.set_yaw(power * -1)
            time.sleep(duration)
            drone_instance.set_yaw(0)
            drone_instance.hover(0.5)
        elif command == "turn_right":
            duration = float(params.get("duration", 1.0))
            power = 50
            print(f"Executing: Turn Right (timed {duration}s)")
            drone_instance.set_yaw(power)
            time.sleep(duration)
            drone_instance.set_yaw(0)
            drone_instance.hover(0.5)
        elif command == "move_up":
            duration = float(params.get("duration", 1.0))
            print(f"Executing: Move Up for {duration}s")
            # Note: CoDrone EDU move_up/down often take distance, not duration. Adjust if needed.
            # Assuming your library version or custom function uses duration.
            # If it uses distance:
            # distance = float(params.get("distance", 30.0)) # e.g., 30 cm
            # speed = float(params.get("speed", 1.0))
            # drone_instance.move_up(distance, "cm", speed)
            drone_instance.move_up(duration) # Keep original if it works
        elif command == "move_down":
            duration = float(params.get("duration", 1.0))
            print(f"Executing: Move Down for {duration}s")
            # Similar distance/duration note as move_up
            drone_instance.move_down(duration) # Keep original if it works
        elif command == "set_throttle":
            power = int(params.get("power", 0))
            print(f"Executing: Set Throttle to {power}")
            drone_instance.set_throttle(max(-100, min(100, power)))
        elif command == "set_yaw":
            power = int(params.get("power", 0))
            print(f"Executing: Set Yaw to {power}")
            drone_instance.set_yaw(max(-100, min(100, power)))
        elif command == "set_roll":
            power = int(params.get("power", 0))
            print(f"Executing: Set Roll to {power}")
            drone_instance.set_roll(max(-100, min(100, power)))
        elif command == "set_pitch":
            power = int(params.get("power", 0))
            print(f"Executing: Set Pitch to {power}")
            drone_instance.set_pitch(max(-100, min(100, power)))
        elif command == "unknown":
            print("Command not understood or not recognized.")
        elif command == "error":
            print(f"An error occurred communicating with ChatGPT or processing: {params.get('message', 'Unknown error')}")
        else:
            print(f"Command '{command}' is not implemented.")

    except ValueError as e:
         print(f"Parameter Error for command '{command}': {e}. Params: {params}")
    except Exception as e:
        print(f"An unexpected error occurred during drone command execution for '{command}': {e}")
        print("Executing emergency land for safety.")
        drone_state["flying"] = False # Assume it's not flying after error
        try:
            drone_instance.land()
        except Exception as land_e:
            print(f"Failed to execute emergency land: {land_e}")


# --- Speech Recognition Adaptation ---
def transcribe_audio_data(audio_bytes: bytes) -> Union[str, None]:
    """Transcribes audio bytes using SpeechRecognition."""
    recognizer = sr.Recognizer()
    # The audio bytes need to be wrapped in an AudioFile-like object
    # We assume the uploaded file is in a format recognizer.recognize_google understands
    # Often WAV is best. If using other formats (MP3, OGG), you might need
    # libraries like pydub to convert first.
    # Let's try directly with AudioData
    # NOTE: recognize_google needs WAV data usually. If this fails, conversion is needed.
    # Need sample rate and width if creating AudioData manually. Let's try letting sr handle it.

    # A more robust way using AudioFile context manager with BytesIO
    audio_segment = None
    try:
        # Wrap bytes in a file-like object
        audio_file = io.BytesIO(audio_bytes)
        with sr.AudioFile(audio_file) as source:
             # Optional: adjust for ambient noise if needed, though less relevant for file
             # recognizer.adjust_for_ambient_noise(source)
             print("Reading audio data from bytes...")
             audio_segment = recognizer.record(source) # Read the entire file
    except ValueError as e:
        print(f"Error reading audio file data (might be format issue): {e}")
        # Common issue: "Audio file could not be read as PCM WAV, AIFF/AIFF-C, or Native FLAC"
        # If this happens, you need to convert the uploaded audio to WAV first.
        return None
    except Exception as e:
         print(f"An unexpected error occurred reading audio bytes: {e}")
         return None

    if not audio_segment:
        print("Could not create audio segment from bytes.")
        return None

    try:
        print("Audio data loaded, recognizing...")
        text = recognizer.recognize_google(audio_segment)
        print(f"Recognized: {text}")
        return text
    except sr.UnknownValueError:
        print("Speech Recognition could not understand audio")
        return None
    except sr.RequestError as e:
        print(f"Could not request results from Google Speech Recognition service; {e}")
        return None
    except Exception as e:
        print(f"An error occurred during speech recognition: {e}")
        return None


# --- Drone Command Processor Thread ---
def drone_command_processor():
    """Runs in a separate thread, processing commands from the queue."""
    global drone, drone_state # Access global drone object and state

    print("Drone command processor thread started.")
    while not drone_processor_stop_event.is_set():
        try:
            # Wait for a command with a timeout to allow checking the stop event
            command_data = drone_command_queue.get(timeout=1.0)

            if drone and drone_state["connected"]:
                 execute_drone_command(drone, command_data)
            else:
                 print("Command skipped: Drone not connected.")

            drone_command_queue.task_done() # Signal that the task is complete

        except queue.Empty:
            # Queue was empty, loop again to check stop event
            continue
        except Exception as e:
            print(f"Error in drone command processor loop: {e}")
            # Avoid crashing the thread, maybe add a small sleep
            time.sleep(1)

    print("Drone command processor thread stopping.")


# --- FastAPI Application ---
app = FastAPI(title="CoDrone Voice Control API")

@app.on_event("startup")
async def startup_event():
    """Connects to the drone and starts the command processor thread on app startup."""
    global drone, drone_processor_thread, drone_state
    print("FastAPI app starting up...")
    drone = Drone() # Use Drone instead of codrone_edu.CoDrone() if that's correct
    try:
        print("Attempting to pair with CoDrone EDU...")
        drone.pair()
        print("Paired successfully!")
        drone_state["connected"] = True
        drone_state["flying"] = False # Assume not flying initially

        # Start the background thread for executing commands
        print("Starting drone command processor thread...")
        drone_processor_stop_event.clear()
        drone_processor_thread = threading.Thread(target=drone_command_processor, daemon=True)
        drone_processor_thread.start()


    except Exception as e:
        print(f"Fatal: An unexpected error occurred during startup: {e}")
        drone = None
        drone_state["connected"] = False

@app.on_event("shutdown")
async def shutdown_event():
    """Signals the command processor to stop, lands the drone, and closes the connection."""
    global drone, drone_processor_thread, drone_state
    print("FastAPI app shutting down...")

    # Signal the processor thread to stop and wait for it
    if drone_processor_thread and drone_processor_thread.is_alive():
        print("Stopping drone command processor thread...")
        drone_processor_stop_event.set()
        # Ensure all queued commands are processed before potentially landing/closing
        # Wait for the queue to be empty
        print("Waiting for command queue to empty...")
        drone_command_queue.join()
        # Wait for the thread itself to finish
        drone_processor_thread.join(timeout=5.0) # Wait max 5 seconds
        if drone_processor_thread.is_alive():
             print("Warning: Drone processor thread did not stop gracefully.")

    if drone and drone.is_connected():
        if drone_state["flying"]:
            print("Landing drone before closing...")
            try:
                # Use execute_drone_command for consistency? Or direct land? Direct is simpler here.
                drone.land()
                time.sleep(2) # Give it time to land
            except Exception as land_e:
                print(f"Error during final landing: {land_e}. Attempting emergency stop.")
                try:
                    drone.emergency_stop()
                except Exception as stop_e:
                    print(f"Error during final emergency stop: {stop_e}")
        print("Closing drone connection.")
        try:
            drone.close()
        except Exception as close_e:
            print(f"Error closing drone connection: {close_e}")

    drone_state["connected"] = False
    drone_state["flying"] = False
    print("Shutdown complete.")


@app.post("/command_audio/")
async def command_drone_via_audio(audio: UploadFile = File(...)):
    """
    Receives an audio file, transcribes it, gets a command from ChatGPT,
    and queues the command for the drone.
    """
    if not drone or not drone_state["connected"]:
        raise HTTPException(status_code=503, detail="Drone is not connected or available.")

    if not client:
         raise HTTPException(status_code=503, detail="OpenAI client is not available.")

    print(f"Received audio file: {audio.filename}, content type: {audio.content_type}")

    # Read audio data
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="No audio data received.")

    # 1. Transcribe Audio
    # Consider running this in a threadpool if transcription is slow
    # from fastapi.concurrency import run_in_threadpool
    # transcribed_text = await run_in_threadpool(transcribe_audio_data, audio_bytes)
    transcribed_text = transcribe_audio_data(audio_bytes) # Run sync for now

    if transcribed_text is None:
        raise HTTPException(status_code=400, detail="Failed to transcribe audio. Check audio format (WAV preferred) or content.")

    # 2. Get Command from ChatGPT
    # This involves network I/O, ideally run async or in threadpool if using sync client
    # command_data = await run_in_threadpool(get_drone_command_from_text, transcribed_text) # If using threadpool
    command_data = get_drone_command_from_text(transcribed_text) # Run sync for now

    command_name = command_data.get("command", "error") # Default to error if structure is wrong

    if command_name == "error":
        error_msg = command_data.get("parameters", {}).get("message", "Failed to get command from LLM.")
        # Decide appropriate status code based on error source if possible
        raise HTTPException(status_code=500, detail=error_msg)

    # 3. Queue Command for Execution
    print(f"Queueing command: {command_data}")
    drone_command_queue.put(command_data)

    # Return success response immediately after queuing
    return JSONResponse(content={
        "status": "success",
        "message": "Command received and queued for execution.",
        "recognized_text": transcribed_text,
        "queued_command": command_data
    })

@app.get("/drone_status/")
async def get_drone_status():
    """Returns the current known status of the drone."""
    # Reading global state - generally safe if only processor thread modifies 'flying'
    return JSONResponse(content=drone_state)


# --- Main Execution (for running with uvicorn) ---
if __name__ == "__main__":
    print("Starting FastAPI server...")
    # Use --host 0.0.0.0 to make it accessible on your network
    # Use --reload for development to auto-restart on code changes
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

    # Note: Reloading might cause issues with drone pairing/state if not handled carefully
    # in startup/shutdown. For production, run without --reload.