#Python code
from codrone_edu.drone import *
import time
import asyncio

def emergency_shutdown():
    drone = Drone()
    drone.pair()
    drone.land()
    drone.close()


async def print_message():
    print("Drone is keeping distance...")

async def maintain_distance(drone):
    drone.keep_distance(3, 60)  # Maintain 60 cm for 10 seconds
    await asyncio.sleep(3)  # Wait for the keep_distance to complete


async def main():
  try:
    #connect
    drone = Drone()
    drone.pair()
    # drone.close()

    drone.takeoff()
    # drone.set_pitch(50)
    print('starting')
    # drone.move(3)
    drone.move_forward(50, 'cm', 2)
    # print('here')
    # print(drone.get_flow_velocity_x())
    # print(drone.get_pos_x())
    # print('ok')
    # time.sleep(1)
    # # drone.set_pitch(-50)
    # print('newprint')
    # print(drone.get_flow_velocity_x())
    # print(drone.get_pos_x())
    # time.sleep(1)
    # print('newprint')
    # print(drone.get_flow_velocity_x())
    # print(drone.get_pos_x())

    #land
    print('Successfully executed flight.')
    drone.land()
    drone.close()
  except Exception as e:
    print('except triggered')
    print(e)
    drone.land()
    drone.close()


if __name__ == "__main__":
    print('running!')
    asyncio.run(main())