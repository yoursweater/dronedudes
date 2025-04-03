#Python code
# from codrone_edu.drone import *

# drone = Drone()
# drone.pair()


# drone.load_color_data()
# color_data = drone.get_color_data()
# color = drone.predict_colors(color_data)
# print(color)


# drone.close()


import asyncio
import time
from codrone_edu.drone import *

async def monitor_position(drone):
    try:
      for i in range(40):
          drone.load_color_data()
          color_data = drone.get_color_data()
          print('sensor data acquired?')
          color = drone.predict_colors(color_data)
          print(color_data)
          print(f'predicted color: {color}')

          await asyncio.sleep(0.5)
    except Exception as e:
        print('monitoring failed')
        print(e)


async def main():
    try:
        # Initialize drone
        drone = Drone()
        drone.pair()

        # Start the monitoring task
        task = asyncio.create_task(monitor_position(drone))
        

        try:
            await asyncio.wait_for(task, timeout=20.0)
        except asyncio.TimeoutError:
            task.cancel()
            

            
    except Exception as e:
        print('fail')
        print(e)

asyncio.run(main())