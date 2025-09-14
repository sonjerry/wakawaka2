import time
from board import SCL, SDA
import busio
from adafruit_servokit import ServoKit

# Initialize I2C bus and ServoKit
try:
    i2c = busio.I2C(SCL, SDA)
    kit = ServoKit(channels=16, i2c=i2c)
    print("PCA9685 initialized successfully.")
except Exception as e:
    print(f"❌ Error: PCA9685 not found or initialization failed. Check I2C connection.")
    print(e)
    exit()

# --- Channel Configuration ---
SERVO_CHANNEL = 0
ESC_CHANNEL = 1

# --- ESC Pulse Width Configuration ---
# This range (1000µs to 2000µs) is standard for most hobbyist ESCs.
kit.servo[ESC_CHANNEL].set_pulse_width_range(1800, 2200)
print(f"ESC pulse width range set for channel {ESC_CHANNEL}.")

def arm_esc():
    """
    Arms the ESC. This is a safety feature to prevent the motor
    from starting unexpectedly. It typically involves sending the
    neutral signal (90 degrees).
    """
    print("\nArming ESC...")
    # Most ESCs arm by receiving a neutral signal (stop).
    # Sending a 90-degree angle corresponds to a 1500µs pulse, the standard neutral position.
    kit.servo[ESC_CHANNEL].angle = 90
    print("✅ ESC Arming complete. Motor is ready.")
    time.sleep(1) # Wait a moment for the ESC to process the signal

def main():
    """Main execution function"""
    try:
        # 1. Arm the ESC on startup
        arm_esc()

        while True:
            # 2. Get user input
            try:
                choice = int(input(
                    "\nEnter a channel to control:\n"
                    "  '0' for Servo Motor\n"
                    "  '1' for ESC (Motor)\n"
                    " '-1' to exit\n"
                    "Choice: "
                ))
            except ValueError:
                print("Invalid input. Please enter a number.")
                continue

            # --- Servo Motor Control ---
            if choice == SERVO_CHANNEL:
                try:
                    angle_input = input(f"Enter angle for Servo on channel {SERVO_CHANNEL} (0-180): ")
                    angle = int(angle_input)
                    if 0 <= angle <= 180:
                        kit.servo[SERVO_CHANNEL].angle = angle
                        print(f"✅ Servo on channel {SERVO_CHANNEL} set to {angle} degrees.")
                    else:
                        print("❌ Error: Angle must be between 0 and 180.")
                except ValueError:
                    print("❌ Invalid input. Please enter a number for the angle.")

            # --- ESC Control ---
            elif choice == ESC_CHANNEL:
                try:
                    angle_input = input(f"Enter speed/direction for ESC on channel {ESC_CHANNEL} (0-180, 90=stop): ")
                    angle = int(angle_input)
                    if 0 <= angle <= 180:
                        print(f"Running motor at {angle} degrees for 2 seconds...")
                        kit.servo[ESC_CHANNEL].angle = angle
                        time.sleep(2)
                        # Optionally, you can stop the motor automatically after the duration
                        # kit.servo[ESC_CHANNEL].angle = 90
                        print(f"✅ Motor control complete. Ready for next command.")
                    else:
                        print("❌ Error: Angle must be between 0 and 180.")
                except ValueError:
                    print("❌ Invalid input. Please enter a number for the angle.")

            # --- Exit Program ---
            elif choice == -1:
                print("Exiting program.")
                break

            else:
                print("Invalid channel selected. Please try again.")

    except KeyboardInterrupt:
        print("\nProgram interrupted by user.")
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")
    finally:
        # Safety measure: ensure the motor is stopped on exit.
        print("🛑 Stopping motor for safety.")
        kit.servo[ESC_CHANNEL].angle = 90
        print("🎉 Program finished.")


if __name__ == '__main__':
    main()