from codrone_edu.drone import Drone
import time
import threading
import sys
import signal
import ctypes

# Function to forcefully terminate a thread
def terminate_thread(thread):
    if not thread.is_alive():
        return
    
    exc = ctypes.py_object(SystemExit)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(thread.ident), exc)
    if res == 0:
        raise ValueError("Invalid thread ID")
    elif res != 1:
        # If more than one thread was affected, revert the call
        ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(thread.ident), None)
        raise SystemError("PyThreadState_SetAsyncExc failed")

# Modified Drone class to handle thread termination
class BetterDrone(Drone):
    def close(self):
        # First, get a reference to the receiver thread before closing
        if hasattr(self, '_thread') and self._thread.is_alive():
            thread_to_kill = self._thread
        else:
            thread_to_kill = None
            
        # Now close the drone normally
        super().close()
        
        # Wait a moment for natural cleanup
        time.sleep(0.5)
        
        # If the thread is still alive, force terminate it
        if thread_to_kill and thread_to_kill.is_alive():
            print("Forcefully terminating receiver thread...")
            terminate_thread(thread_to_kill)

# Signal handler for clean exit
def signal_handler(sig, frame):
    print("\nInterrupted, shutting down...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

try:
    # Use our improved drone class
    drone = BetterDrone()
    
    # Connect and fly
    drone.pair()
    print("Taking off...")
    drone.takeoff()
    
    # Your flight code here
    
    print("Landing...")
    drone.land()
    time.sleep(1.5)  # Wait for landing to complete
    
finally:
    # Clean shutdown
    if 'drone' in locals():
        print("Closing drone connection...")
        drone.close()
    
    # Final check for any remaining threads
    drone_threads = [t for t in threading.enumerate() 
                   if t != threading.current_thread() and "Thread-" in t.name]
    
    for t in drone_threads:
        print(f"Found remaining thread {t.name}, attempting to terminate...")
        try:
            terminate_thread(t)
        except:
            pass