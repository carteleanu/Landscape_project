import machine
import neopixel
import time
import random

# --- Config ---
NUM_BUTTONS = 10
LEDS_PER_BANK = 12

BUTTON_PINS = [10, 11, 12, 13, 14, 15, 17, 16, 18, 9]
LED_PINS = [0, 1, 2, 3, 4, 5, 6, 20, 22, 19]

# Colors
COLOR_PALETTE = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255),
    (255, 255, 0), (255, 0, 255), (0, 255, 255),
    (255, 128, 0), (255, 255, 255), (128, 0, 128),
    (0, 128, 255),
]

# BooTunes trigger pins and their corresponding sounds
# NOTE: You will need to wire these up to different inputs on your BooTunes Amped
GAME_START_PIN = 21 # Corresponds to a sound for game start
FAIL_SOUND_PIN = 22  # Use a new pin for the 'fail' sound
SUCCESS_SOUND_PIN = 23 # Use another new pin for the 'success' sound
WIN_SOUND_PIN = 24  # Use another new pin for the 'win' sound

# --- Hardware setup ---
buttons = [machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_UP) for pin in BUTTON_PINS]
strips  = [neopixel.NeoPixel(machine.Pin(pin), LEDS_PER_BANK) for pin in LED_PINS]

# Set up the new sound trigger pins
game_start_trigger_pin = machine.Pin(GAME_START_PIN, machine.Pin.OUT)
game_start_trigger_pin.value(1)
fail_trigger_pin = machine.Pin(FAIL_SOUND_PIN, machine.Pin.OUT)
fail_trigger_pin.value(1)
success_trigger_pin = machine.Pin(SUCCESS_SOUND_PIN, machine.Pin.OUT)
success_trigger_pin.value(1)
win_trigger_pin = machine.Pin(WIN_SOUND_PIN, machine.Pin.OUT)
win_trigger_pin.value(1)

# --- State ---
def generate_random_bank_colors():
    return [random.choice(COLOR_PALETTE) for _ in range(NUM_BUTTONS)]

bank_colors = generate_random_bank_colors()

# New state variable to track if a button was pressed in the last loop
button_was_pressed = [False] * NUM_BUTTONS

# New state variable for the lockout timer for each button
# The value is the time in milliseconds when the lockout ends.
# A value of 0 means no lockout is active.
button_lockout_end_time = [0] * NUM_BUTTONS

# --- Helpers ---
def fill_bank(bank_index, color):
    strip = strips[bank_index]
    for i in range(LEDS_PER_BANK):
        strip[i] = color
    strip.write()

def update_all_banks():
    for i, color in enumerate(bank_colors):
        fill_bank(i, color)

def blink_bank(bank_index, color, times=2, delay=0.1):
    original_color = bank_colors[bank_index]
    for _ in range(times):
        fill_bank(bank_index, color)
        time.sleep(delay)
        fill_bank(bank_index, (0, 0, 0))
        time.sleep(delay)
    fill_bank(bank_index, original_color)
    strips[bank_index].write()

def blink_all(color, times=3, delay=0.3):
    for _ in range(times):
        for b in range(NUM_BUTTONS):
            fill_bank(b, color)
        time.sleep(delay)
        for b in range(NUM_BUTTONS):
            fill_bank(b, (0, 0, 0))
        time.sleep(delay)

def colors_match(c1, c2):
    return c1 == c2

def all_banks_same_color():
    first = bank_colors[0]
    return all(colors_match(first, c) for c in bank_colors)

def shift_color_towards(current, target, step=40):
    new_color = list(current)
    for i in range(3):
        if new_color[i] < target[i]:
            new_color[i] = min(new_color[i] + step, target[i])
        elif new_color[i] > target[i]:
            new_color[i] = max(new_color[i] - step, target[i])
    return tuple(new_color)

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

def rainbow_chase(cycles=1, wait=0.002):
    for j in range(256 * cycles):
        for bank_index in range(NUM_BUTTONS):
            strip = strips[bank_index]
            for pixel_index in range(LEDS_PER_BANK):
                pos = (pixel_index * 256 // LEDS_PER_BANK) + j
                strip[pixel_index] = wheel(pos & 255)
            strip.write()  
        time.sleep(wait)
        
def play_sound(trigger_pin):
    print(f"Triggering sound on pin {trigger_pin.pin()}")
    trigger_pin.value(0)
    time.sleep_ms(100)
    trigger_pin.value(1)
    print("Sound trigger complete.")
    
update_all_banks()
play_sound(game_start_trigger_pin)
print("Game Ready: Match all buttons to the color of the first button.")

while True:
    for i, button in enumerate(buttons):
        current_time = time.ticks_ms()
        is_pressed_now = not button.value()

        # Check for expired lockouts and revert lights
        if button_lockout_end_time[i] != 0 and time.ticks_diff(current_time, button_lockout_end_time[i]) >= 0:
            print(f"Button {i} lockout expired. Reverting lights.")
            button_lockout_end_time[i] = 0
            fill_bank(i, bank_colors[i])

        # Detect a new press (button just went from released -> pressed)
        if is_pressed_now and not button_was_pressed[i]:
            # Check if the button is currently in a lockout period
            if time.ticks_diff(current_time, button_lockout_end_time[i]) < 0:
                print(f"Button {i} was pressed during lockout. Applying penalty.")
                # Penalty: turn off lights and extend lockout for 2 seconds
                fill_bank(i, (0, 0, 0))
                button_lockout_end_time[i] = time.ticks_add(current_time, 2000)
            else:
                # Button is not in lockout, proceed with normal game logic
                print(f"Button {i} pressed")
                # Set a temporary lockout for 0.5 seconds to prevent rapid presses
                button_lockout_end_time[i] = time.ticks_add(current_time, 500)

                target_color = bank_colors[0]

                if i == 0:
                    # Target button doesn't change
                    print("This is the target button. No change.")
                    play_sound(success_trigger_pin)
                    blink_bank(i, (0, 255, 0))  # green blink
                else:
                    # Shift the bank color one step toward the target
                    bank_colors[i] = shift_color_towards(bank_colors[i], target_color)

                    # Check immediately if it now matches
                    if colors_match(bank_colors[i], target_color):
                        print("✅ Correct! Button now matched.")
                        play_sound(success_trigger_pin)
                        blink_bank(i, (0, 255, 0))  # green blink
                    else:
                        print("❌ Wrong color! Gradually shifting towards the target.")
                        play_sound(fail_trigger_pin)
                        blink_bank(i, (255, 0, 0))  # red blink

                    # Update LEDs to reflect new colors
                    update_all_banks()

                    # After updating, check if all banks are complete
                    if all_banks_same_color():
                        print("🎉 All banks match! You win!")
                        play_sound(win_trigger_pin)
                        rainbow_chase(cycles=1, wait=0.002)
                        time.sleep(1.5)  # pause to celebrate
                        bank_colors = generate_random_bank_colors()
                        update_all_banks()
                        play_sound(game_start_trigger_pin)

        # Store current state for next loop
        button_was_pressed[i] = is_pressed_now

    time.sleep_ms(10)
