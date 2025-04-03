import asyncio
import time
from codrone_edu.drone import *

async def monitor_position(drone):
    for i in range(20):
        # print(drone.get_pos_x())
        distance = drone.get_front_range('cm')
        print(distance)
        await asyncio.sleep(0.2)

async def main():
    drone = None
    try:
        # Initialize drone
        drone = Drone()
        drone.pair()
        
        # Start the monitoring task
        task = asyncio.create_task(monitor_position(drone))
        
        # Perform drone movements
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, drone.takeoff)
        await loop.run_in_executor(None, lambda: drone.keep_distance(10, 30))
        
        # Allow monitoring to complete (or cancel after movements)
        try:
            await asyncio.wait_for(task, timeout=5.0)
        except asyncio.TimeoutError:
            task.cancel()
            
        # Land and close connection
        if drone:
            drone.land()
            drone.close()
            
    except Exception as e:
        print('fail')
        print(e)
        if drone:
            drone.land()
            drone.close()

asyncio.run(main())