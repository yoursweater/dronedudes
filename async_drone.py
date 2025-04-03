import asyncio
import time
from codrone_edu.drone import *

async def monitor_position(drone):
    try:
      for i in range(40):
          # print(drone.get_pos_x())
          distance = drone.get_front_range('cm')
          print(f'distance: {distance}')

          drone.load_color_data()
          color_data = drone.get_color_data()
          print('sensor data acquired?')
          color = drone.predict_colors(color_data)
          print(color_data)
          print(f'predicted color: {color}')
          if distance < 150 and i > 20:
              drone.set_drone_LED(255, 0, 0, 100)
              # drone.start_drone_buzzer(500)
          await asyncio.sleep(0.2)
    except Exception as e:
        print('monitoring failed')
        print(e)
        drone.land()
        drone.close()

async def main():
    try:
        # Initialize drone
        drone = Drone()
        drone.pair()
        loop = asyncio.get_running_loop()
        drone.set_drone_LED(0, 0, 255, 100)

        
        # drone.stop_drone_buzzer()
        
        # Start the monitoring task
        task = asyncio.create_task(monitor_position(drone))
        
        # Perform drone movements
        # await loop.run_in_executor(None, drone.takeoff)
        # await loop.run_in_executor(None, lambda: drone.move_distance(0, 0, 0.25, 1))
        # await loop.run_in_executor(None, lambda: drone.keep_distance(8, 10))
        
        # Allow monitoring to complete (or cancel after movements)
        try:
            await asyncio.wait_for(task, timeout=20.0)
        except asyncio.TimeoutError:
            task.cancel()
            
        # Land and close connection
        if drone:
            drone.set_drone_LED(0, 0, 255, 100)
            # drone.stop_drone_buzzer()
            drone.land()
            drone.close()
            
    except Exception as e:
        print('fail')
        print(e)
        if drone:
            drone.land()
            drone.close()

asyncio.run(main())