import machine
import neopixel
import time
import random

# --- Config ---
NUM_BUTTONS = 10
LEDS_PER_BANK = 12

BUTTON_PINS = [10, 11, 12, 13, 14, 15, 17, 16, 18, 9]
LED_PINS = [0, 1, 2, 3, 4, 5, 6, 20, 22, 19]

# Combine the pin lists into pairs (BUTTON_PIN, LED_PIN) to ensure alignment.
PIN_PAIRS = list(zip(BUTTON_PINS, LED_PINS))

# Colors
COLOR_PALETTE = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255),
    (255, 255, 0), (255, 0, 255), (0, 255, 255),
    (255, 128, 0), (255, 255, 255), (128, 0, 128),
    (0, 128, 255),
]

SOUND_PIN = 21
FAIL_SOUND = 8
SUCCESS_SOUND = 27
WIN_SOUND = 7

# --- Hardware setup ---
# Create the button objects using the first pin in each pair
buttons = [
    machine.Pin(button_pin, machine.Pin.IN, machine.Pin.PULL_UP)
    for button_pin, led_pin in PIN_PAIRS
]

# Create the NeoPixel strip objects using the second pin in each pair
strips = [
    neopixel.NeoPixel(machine.Pin(led_pin), LEDS_PER_BANK)
    for button_pin, led_pin in PIN_PAIRS
]

# Sound pin setup
sound_trigger_pin = machine.Pin(SOUND_PIN, machine.Pin.OUT)
sound_trigger_pin.value(1)
fail_trigger_pin = machine.Pin(FAIL_SOUND, machine.Pin.OUT)
fail_trigger_pin.value(1)
success_trigger_pin = machine.Pin(SUCCESS_SOUND, machine.Pin.OUT)
success_trigger_pin.value(1)
win_trigger_pin = machine.Pin(WIN_SOUND, machine.Pin.OUT)
win_trigger_pin.value(1)


# --- State ---
def generate_random_bank_colors():
    """Generates a list of random colors, one for each button/bank."""
    return [random.choice(COLOR_PALETTE) for _ in range(NUM_BUTTONS)]


bank_colors = generate_random_bank_colors()

# Global variable used by blink_bank to communicate button press status
button_pressed_during_blink = -1


# --- Helpers ---
def fill_bank(bank_index, color):
    strip = strips[bank_index]
    for i in range(LEDS_PER_BANK):
        strip[i] = color
    strip.write()


def update_all_banks(color):
    for strip in strips:
        for i in range(LEDS_PER_BANK):
            strip[i] = color
        strip.write()
    time.sleep(1.2)


def shuffle_list(data):
    length = len(data)
    for i in range(length - 1, 0, -1):
        j = random.randrange(i + 1)
        data[i], data[j] = data[j], data[i]


def blink_bank(bank_index, color, times=4, delay=0.1):
    global button_pressed_during_blink

    button_pin = buttons[bank_index]
    delay_ms = int(delay * 1000)

    for _ in range(times):
        # 1. Turn ON and Check
        fill_bank(bank_index, color)
        start_time = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start_time) < delay_ms:
            if not button_pin.value():
                # Button pressed during 'ON' time!
                button_pressed_during_blink = bank_index
                return True

        # 2. Turn OFF and Check
        fill_bank(bank_index, (0, 0, 0))
        start_time = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start_time) < delay_ms:
            if not button_pin.value():
                # Button pressed during 'OFF' time!
                button_pressed_during_blink = bank_index
                return True

    # Ensure it's off after the loop completes
    strips[bank_index].write()
    return False  # No press was detected


def wheel(pos):
    if pos < 0 or pos > 255:
        return (0, 0, 0)
    if pos < 85:
        return (255 - pos * 3, pos * 3, 0)
    if pos < 170:
        pos -= 85
        return (0, 255 - pos * 3, pos * 3)
    pos -= 170
    return (pos * 3, 0, 255 - pos * 3)


def rainbow_chase(cycles, wait, speed):
    for j in range(0, 256 * cycles, speed):
        for bank_index in range(NUM_BUTTONS):
            strip = strips[bank_index]
            for pixel_index in range(LEDS_PER_BANK):
                pos = (pixel_index * 256 // LEDS_PER_BANK) + j
                strip[pixel_index] = wheel(pos & 255)
            strip.write()


def play_sound():
    print("Triggering BooTunes sound...")
    sound_trigger_pin.value(0)
    time.sleep_ms(100)
    sound_trigger_pin.value(1)
    print("Sound trigger complete.")


def success_sound():
    print("playing success sound")
    success_trigger_pin.value(0)
    time.sleep_ms(100)
    success_trigger_pin.value(1)


def win_sound():
    print("playing win sound")
    win_trigger_pin.value(0)
    time.sleep_ms(100)
    win_trigger_pin.value(1)


def game_reset():
    global bank_colors
    # Generate new random colors for the next cycle
    bank_colors = generate_random_bank_colors()
    # Turn off all banks to start the new round cleanly
    for i in range(NUM_BUTTONS):
        fill_bank(i, (0, 0, 0))
    print("Game has reset. Starting new cycle.")


# --- Main Game Loop ---

print("Game Ready: Press any button while it's blinking to win the round.")

# Initialize the game colors and turn off all LEDs
game_reset()

# List of indexes used to control the random sequence
button_indexes = list(range(NUM_BUTTONS))

while True:
    # SHUFFLE: Randomize the order of the button indexes for the new cycle
    shuffle_list(button_indexes)

    # ITERATE: Cycle through the buttons in the new random order
    for i in button_indexes:
        # 'i' is the current bank index (0-9) to check

        # 1. BLINK & CHECK: Highlight the current bank and check its button
        color_to_blink = bank_colors[i]

        # blink_bank returns True if a press occurred during the blink time
        win_condition_met = blink_bank(i, color_to_blink, times=4, delay=0.1)

        if win_condition_met:
            print(f"Button {i} pressed! WIN!")
            success_sound()

            # 2. WIN SEQUENCE
            target_color = bank_colors[i]
            # All banks turn the pressed color
            update_all_banks(target_color)
            time.sleep(0.5)
            win_sound()
            # Play the rainbow animation
            rainbow_chase(cycles=8, wait=0.002, speed=19)

            # 3. GAME RESET
            # time.sleep_ms(100)
            # play_sound()
            # time.sleep_ms(300)
            game_reset()

            # Break out of the inner FOR loop to restart the WHILE TRUE loop (and re-shuffle)
            break

        # 4. Clean up: Ensure the bank is off before moving to the next one
        fill_bank(i, (0, 0, 0))
        time.sleep_ms(10)

    # Small delay between full cycles of all 10 buttons if no win occurred
    time.sleep_ms(50)

