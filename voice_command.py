import codrone_edu
import speech_recognition as sr
import openai
import os
import json
import time
import threading
import queue
from dotenv import load_dotenv # Optional: for loading API key from .env file

# --- Configuration ---
load_dotenv() # Load environment variables from .env file if it exists
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OpenAI API key not found. Set the OPENAI_API_KEY environment variable.")

openai.api_key = OPENAI_API_KEY
client = openai.OpenAI(api_key=OPENAI_API_KEY) # Use the new client

# CoDrone EDU commands we want ChatGPT to recognize
# Keep this list relatively simple and clear
ALLOWED_COMMANDS = [
    "takeoff", "land", "hover", "emergency_stop",
    "move_forward", "move_backward", "move_left", "move_right",
    "turn_left", "turn_right", "move_up", "move_down",
    "set_throttle", "set_yaw", "set_roll", "set_pitch" # More advanced
]

# --- ChatGPT Interaction ---
def get_drone_command_from_text(text):
    """Sends text to ChatGPT and asks for a structured drone command."""
    print(f"Sending to ChatGPT: '{text}'")
    try:
        # This system prompt is CRUCIAL for getting reliable JSON output
        system_prompt = f"""
You are an AI assistant interpreting voice commands for a CoDrone EDU drone.
The available commands are: {', '.join(ALLOWED_COMMANDS)}.
Some commands take parameters:
- move_forward, move_backward, move_left, move_right, turn_left, turn_right, move_up, move_down: require 'duration' (float, seconds, default 1.0).
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
            model="gpt-3.5-turbo-1106", # Or gpt-4 if preferred. Newer models often better at following instructions
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"}, # Enforce JSON output if model supports it
            temperature=0.2, # Lower temperature for more deterministic command interpretation
            max_tokens=100
        )

        # response_content = response.choices[0].message.content
        response_content = response.choices[0].message.content
        print(f"ChatGPT Response: {response_content}")

        # Clean potential markdown backticks if model ignores response_format
        if response_content.startswith("```json"):
            response_content = response_content[7:-3].strip()
        elif response_content.startswith("```"):
             response_content = response_content[3:-3].strip()


        command_data = json.loads(response_content)

        # Validate basic structure
        if isinstance(command_data, dict) and "command" in command_data:
             # Further validation: check if command is allowed
             if command_data["command"] in ALLOWED_COMMANDS or command_data["command"] == "unknown":
                return command_data
             else:
                print(f"Warning: ChatGPT proposed an disallowed command: {command_data['command']}")
                return {"command": "unknown", "parameters": {}}
        else:
            print(f"Warning: Invalid JSON structure from ChatGPT: {command_data}")
            return {"command": "unknown", "parameters": {}}

    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from ChatGPT response: {response_content}")
        return {"command": "unknown", "parameters": {}}
    except openai.APIError as e:
        print(f"OpenAI API Error: {e}")
        return {"command": "error", "parameters": {}}
    except Exception as e:
        print(f"An unexpected error occurred during ChatGPT interaction: {e}")
        return {"command": "error", "parameters": {}}


# --- Drone Command Execution ---
def execute_drone_command(drone, command_data):
    """Executes the corresponding CoDrone EDU command."""
    command = command_data.get("command", "unknown")
    params = command_data.get("parameters", {})

    print(f"Attempting to execute: {command} with params: {params}")

    try:
        if command == "takeoff":
            print("Executing: Takeoff")
            drone.takeoff()
            drone.hover(1) # Hover briefly after takeoff
        elif command == "land":
            print("Executing: Land")
            drone.land()
        elif command == "hover":
            duration = float(params.get("duration", 3.0)) # Default hover 3s
            print(f"Executing: Hover for {duration}s")
            drone.hover(duration)
        elif command == "emergency_stop":
            print("Executing: Emergency Stop")
            drone.emergency_stop()
        elif command == "move_forward":
            duration = float(params.get("duration", 1.0))
            print(f"Executing: Move Forward for {duration}s")
            drone.move_forward(duration)
        elif command == "move_backward":
            duration = float(params.get("duration", 1.0))
            print(f"Executing: Move Backward for {duration}s")
            drone.move_backward(duration)
        elif command == "move_left":
            duration = float(params.get("duration", 1.0))
            print(f"Executing: Move Left for {duration}s")
            drone.move_left(duration)
        elif command == "move_right":
            duration = float(params.get("duration", 1.0))
            print(f"Executing: Move Right for {duration}s")
            drone.move_right(duration)
        elif command == "turn_left":
            duration = float(params.get("duration", 1.0)) # Duration based turning might be less precise
            # Alternative: Turn by degrees if library supports it well, requires different ChatGPT prompt
            # degrees = int(params.get("degrees", 90))
            # drone.turn_left(degrees)
            power = 50 # Default power for timed turn
            print(f"Executing: Turn Left (timed {duration}s)")
            drone.set_yaw(power * -1)
            time.sleep(duration)
            drone.set_yaw(0) # Stop turning
            drone.hover(0.5) # Stabilize
        elif command == "turn_right":
            duration = float(params.get("duration", 1.0))
            # degrees = int(params.get("degrees", 90))
            # drone.turn_right(degrees)
            power = 50
            print(f"Executing: Turn Right (timed {duration}s)")
            drone.set_yaw(power)
            time.sleep(duration)
            drone.set_yaw(0)
            drone.hover(0.5)
        elif command == "move_up":
            duration = float(params.get("duration", 1.0))
            print(f"Executing: Move Up for {duration}s")
            drone.move_up(duration)
        elif command == "move_down":
            duration = float(params.get("duration", 1.0))
            print(f"Executing: Move Down for {duration}s")
            drone.move_down(duration)
        elif command == "set_throttle":
            power = int(params.get("power", 0))
            print(f"Executing: Set Throttle to {power}")
            drone.set_throttle(max(-100, min(100, power))) # Clamp power
        elif command == "set_yaw":
            power = int(params.get("power", 0))
            print(f"Executing: Set Yaw to {power}")
            drone.set_yaw(max(-100, min(100, power)))
        elif command == "set_roll":
            power = int(params.get("power", 0))
            print(f"Executing: Set Roll to {power}")
            drone.set_roll(max(-100, min(100, power)))
        elif command == "set_pitch":
            power = int(params.get("power", 0))
            print(f"Executing: Set Pitch to {power}")
            drone.set_pitch(max(-100, min(100, power)))
        elif command == "unknown":
            print("Command not understood or not recognized.")
        elif command == "error":
            print("An error occurred communicating with ChatGPT.")
        else:
            print(f"Command '{command}' is not implemented.")

    except codrone_edu.CoDroneError as e:
        print(f"CoDrone Error executing '{command}': {e}")
    except ValueError as e:
         print(f"Parameter Error for command '{command}': {e}. Params: {params}")
    except Exception as e:
        print(f"An unexpected error occurred during drone command execution: {e}")
        print("Executing emergency land for safety.")
        try:
            drone.land() # Attempt to land safely on unexpected errors
        except Exception as land_e:
            print(f"Failed to execute emergency land: {land_e}")


# --- Speech Recognition Thread ---
def listen_and_transcribe(recognizer, audio_queue, stop_event):
    """Listens for audio, transcribes it, and puts text into a queue."""
    while not stop_event.is_set():
        print("\nListening for command...")
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5) # Adjust for noise
            try:
                # Listen for the first phrase and extract it
                # Timeout: How long to wait for phrase to start
                # Phrase time limit: Max duration of a phrase
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            except sr.WaitTimeoutError:
                print("No speech detected within timeout.")
                continue # Continue listening

        if stop_event.is_set():
            break

        try:
            print("Got audio, recognizing...")
            # Use Google Web Speech API for potentially better accuracy (requires internet)
            text = recognizer.recognize_google(audio)
            # Alternative: Offline recognition (less accurate, needs setup)
            # text = recognizer.recognize_sphinx(audio)
            print(f"You said: {text}")
            if text:
                audio_queue.put(text) # Put recognized text into the queue

        except sr.UnknownValueError:
            print("Speech Recognition could not understand audio")
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {e}")
        except Exception as e:
            print(f"An error occurred during speech recognition: {e}")

        time.sleep(0.1) # Small pause to prevent tight loop on errors


# --- Main Execution ---
if __name__ == "__main__":
    drone = codrone_edu.CoDrone()
    is_flying = False
    command_queue = queue.Queue() # Queue for commands from listening thread
    stop_listening = threading.Event()

    try:
        print("Attempting to pair with CoDrone EDU...")
        drone.pair()
        print("Paired successfully!")

        # Initialize recognizer
        r = sr.Recognizer()
        # Optional: Adjust energy threshold if mic is too sensitive/insensitive
        # r.energy_threshold = 4000

        # Start the listening thread
        listener_thread = threading.Thread(target=listen_and_transcribe, args=(r, command_queue, stop_listening))
        listener_thread.daemon = True # Allows main program to exit even if thread is running
        listener_thread.start()

        print("\nSetup complete. Ready for voice commands.")
        print("Say 'take off' to start flying.")
        print("Say 'land' to land the drone.")
        print("Press Ctrl+C to exit.")

        while True:
            try:
                # Wait for a command from the listener thread (with timeout)
                transcribed_text = command_queue.get(timeout=1.0) # Check queue every second

                if transcribed_text:
                    # Get structured command from ChatGPT
                    command_data = get_drone_command_from_text(transcribed_text)

                    # Update flying state BEFORE executing potentially blocking commands
                    command_name = command_data.get("command")
                    if command_name == "takeoff":
                        is_flying = True
                    elif command_name in ["land", "emergency_stop"]:
                         is_flying = False

                    # Execute the command
                    execute_drone_command(drone, command_data)

                    # If a set_* command was used, hover briefly to let it take effect?
                    # Optional, might interfere with continuous control
                    # if command_name and command_name.startswith("set_"):
                    #    drone.hover(0.2)

            except queue.Empty:
                # No command received in the last second, just continue looping
                # You could add drone state checks here (battery, etc.) if needed
                # print(".", end="", flush=True) # Optional: indicator that it's alive
                pass
            except KeyboardInterrupt:
                print("\nCtrl+C detected. Landing and exiting.")
                break
            except Exception as e:
                print(f"\nAn error occurred in the main loop: {e}")
                # Consider landing or emergency stop here too
                break

    except codrone_edu.CoDroneError as e:
        print(f"CoDrone connection error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during setup or main loop: {e}")
    finally:
        print("Shutting down...")
        stop_listening.set() # Signal the listener thread to stop
        if listener_thread.is_alive():
             listener_thread.join(timeout=2) # Wait briefly for thread cleanup

        if drone.is_connected():
            if is_flying: # Check if drone THINKS it's flying
                 print("Landing drone before closing...")
                 try:
                     drone.land()
                     time.sleep(2) # Give it time to land
                 except Exception as land_e:
                     print(f"Error during final landing: {land_e}. Attempting emergency stop.")
                     try:
                        drone.emergency_stop()
                     except Exception as stop_e:
                        print(f"Error during final emergency stop: {stop_e}")

            print("Closing drone connection.")
            drone.close()
        print("Program finished.")