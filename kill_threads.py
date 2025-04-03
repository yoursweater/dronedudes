import threading

# Get a list of all active threads
active_threads = threading.enumerate()

# Filter out the main thread (you typically don't want to terminate this one)
threads_to_terminate = [t for t in active_threads if t != threading.current_thread()]

# Set a flag to signal threads to exit (if they check for this)
# This assumes your threads have a 'should_exit' attribute
for thread in threads_to_terminate:
    if hasattr(thread, 'should_exit'):
        thread.should_exit = True

# Join all threads to wait for them to finish
for thread in threads_to_terminate:
    if thread.is_alive():
        thread.join(timeout=1.0)  # Wait up to 1 second for each thread