import time
# Assume import Adafruit_PCA9685 or similar; for simulation, we'll mock it

class PCA9685Mock:
    def __init__(self):
        self.channels = [0] * 16

    def set_pwm(self, channel, on, off):
        self.channels[channel] = off  # Simulate setting pulse width

pca = PCA9685Mock()  # Mock for simulation; replace with actual in real use

def arm_esc():
    # Arming sequence on channel 1 (0-indexed? Assuming channel 1 is 1)
    pca.set_pwm(1, 0, 1599)
    time.sleep(1)
    pca.set_pwm(1, 0, 1799)
    time.sleep(1)
    pca.set_pwm(1, 0, 1798)  # Neutral

def map_axis_to_pulse(axis):
    if axis >= 0:
        # 0 to 50 -> 1875 to 2198
        return int(1875 + (axis / 50) * (2198 - 1875))
    else:
        # -50 to 0 -> 1599 to 1798
        return int(1599 + ((axis + 50) / 50) * (1798 - 1599))

# Example usage
if __name__ == "__main__":
    arm_esc()
    print(map_axis_to_pulse(0))  # Should be around 1875 or 1798? Wait, 0 is boundary
    # For axis 0: from positive side 1875, negative 1798. Might need to define neutral as 1798 or adjust.