import machine
import neopixel
import time
import random

# --- Config ---
NUM_BUTTONS = 10
LEDS_PER_BANK = 12
TOTAL_LEDS = NUM_BUTTONS * LEDS_PER_BANK  # Total number of LEDs for the chase effect
DEBOUNCE_MS = 120  # debounce interval (ms)

# Pin assignments for buttons and NeoPixel data lines (kept as your original)
BUTTON_PINS = [10, 11, 12, 13, 14, 15, 17, 16, 18, 9]
LED_PINS = [0, 1, 2, 3, 4, 5, 6, 20, 22, 19]

# Colors (10 distinct colors for 10 buttons)
COLOR_PALETTE = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255),  # Red, Green, Blue
    (255, 255, 0), (255, 120, 120), (255, 69, 1),  # Yellow, Pink, Orange
    (94, 249, 32), (255, 255, 255), (108, 0, 108),  # Light Green, White, Purple
    (100, 255, 255),  # Light Blue
]
BLACK = (0, 0, 0)

# Sound trigger pins (Assuming active-low triggers for BooTunes/MP3 modules)
SOUND_PIN = 21  # General Start Sound
FAIL_SOUND = 8
SUCCESS_SOUND = 27
WIN_SOUND = 7

# --- Game State Variables (MODIFIED) ---
WAITING_FOR_COLOR_SELECT = 0
COLOR_FILL_GAME = 1
WIN_STATE = 2  # New state for when all buttons are lit

game_state = WAITING_FOR_COLOR_SELECT
target_color = BLACK  # The color the user needs to achieve
initial_button_index = -1  # Stores the button index pressed to choose the target color
start_display_ready = False  # Tracks if the initial display setup has run

# Track the status of the banks in the new game
is_filled = [False] * NUM_BUTTONS  # Tracks which banks are successfully turned to target_color

# Track previous button pressed state (for edge detection)
button_was_pressed = [False] * NUM_BUTTONS
# Track last accepted press time for debounce
last_press_time = [0] * NUM_BUTTONS

bank_colors = [BLACK] * NUM_BUTTONS  # Current colors displayed on the banks

# --- Fire flicker globals (can be removed as flicker is no longer used, but kept for completeness if needed) ---
fire_current_brightness = [0.18] * NUM_BUTTONS
fire_target_brightness = [0.18] * NUM_BUTTONS
fire_last_update = [time.ticks_ms()] * NUM_BUTTONS

# --- Hardware setup ---
buttons = [machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_UP) for pin in BUTTON_PINS]
strips = [neopixel.NeoPixel(machine.Pin(pin), LEDS_PER_BANK) for pin in LED_PINS]

# Initialize sound pins high (assuming active-low trigger)
sound_trigger_pin = machine.Pin(SOUND_PIN, machine.Pin.OUT)
sound_trigger_pin.value(1)
fail_trigger_pin = machine.Pin(FAIL_SOUND, machine.Pin.OUT)
fail_trigger_pin.value(1)
success_trigger_pin = machine.Pin(SUCCESS_SOUND, machine.Pin.OUT)
success_trigger_pin.value(1)
win_trigger_pin = machine.Pin(WIN_SOUND, machine.Pin.OUT)
win_trigger_pin.value(1)


# --- Utility Functions (Custom shuffle for MicroPython) ---
# NOTE: shuffle_list is no longer strictly needed but kept as an example
def shuffle_list(data):
    length = len(data)
    for i in range(length - 1, 0, -1):
        j = random.randrange(i + 1)
        data[i], data[j] = data[j], data[i]


# --- LED Helpers (Kept the same) ---
def fill_bank(bank_index, color):
    strip = strips[bank_index]
    for i in range(LEDS_PER_BANK):
        strip[i] = color
    strip.write()


def fill_all(color):
    for i in range(NUM_BUTTONS):
        fill_bank(i, color)


def black_out_all():
    fill_all(BLACK)


def update_all_banks():
    for i, color in enumerate(bank_colors):
        fill_bank(i, color)


def blink_all(color, times=3, delay=0.3):
    for _ in range(times):
        fill_all(color)
        time.sleep(delay)
        black_out_all()
        time.sleep(delay)


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


# NEW: Initial display for color selection
def setup_color_select_display():
    global bank_colors

    # Ensure all buttons have distinct colors to choose from
    bank_colors = list(COLOR_PALETTE[:NUM_BUTTONS])
    update_all_banks()
    print("Game Ready: Press any button to select your target color.")


# NEW: Setup after the target color is chosen
def setup_color_fill_game(initial_index, target_color):
    global bank_colors, is_filled

    black_out_all()  # Turn all off

    # Initialize all banks as not filled
    is_filled = [False] * NUM_BUTTONS

    # The initial pressed button stays on with the target color
    bank_colors = [BLACK] * NUM_BUTTONS
    bank_colors[initial_index] = target_color
    is_filled[initial_index] = True

    fill_bank(initial_index, target_color)  # Light up the initial button

    print(f"Target color set: {target_color} on button {initial_index}. Start filling the rest.")


# --- Sound Helpers (Kept the same) ---
def fail_sound():
    print("Playing fail sound")
    fail_trigger_pin.value(0)
    time.sleep_ms(100)
    fail_trigger_pin.value(1)


def win_sound():
    print("Playing win sound")
    win_trigger_pin.value(0)
    time.sleep_ms(100)
    win_trigger_pin.value(1)


# --- Button handling (edge detect + debounce) (Kept the same) ---
def handle_button_press():
    now = time.ticks_ms()
    for i, button in enumerate(buttons):
        pressed_now = not button.value()  # PULL_UP: 0 means pressed
        # Edge: released -> pressed
        if pressed_now and not button_was_pressed[i]:
            # debounce interval check
            if time.ticks_diff(now, last_press_time[i]) > DEBOUNCE_MS:
                last_press_time[i] = now
                button_was_pressed[i] = True
                return i
            else:
                # treat as bounce; record state but don't return
                button_was_pressed[i] = True
        elif not pressed_now:
            # release resets edge detection
            button_was_pressed[i] = False
    return -1


# --- Main Game Loop Functions (MODIFIED) ---
def run_game_loop():
    global game_state, target_color, initial_button_index, start_display_ready, is_filled, bank_colors

    # --- State 0: WAITING_FOR_COLOR_SELECT ---
    if game_state == WAITING_FOR_COLOR_SELECT:
        if not start_display_ready:
            setup_color_select_display()
            start_display_ready = True

        button_index = handle_button_press()

        if button_index != -1:
            # User presses button_index to set the target color
            target_color = bank_colors[button_index]
            initial_button_index = button_index

            # Transition to the fill game state
            game_state = COLOR_FILL_GAME
            setup_color_fill_game(initial_button_index, target_color)
            start_display_ready = False  # Reset for next time

    # --- State 1: COLOR_FILL_GAME ---
    elif game_state == COLOR_FILL_GAME:
        button_index = handle_button_press()

        if button_index != -1:
            if is_filled[button_index]:
                # Button already lit, do nothing, or play a success sound
                print(f"Button {button_index} already filled.")

            else:
                # Button not lit: turn it the target color
                print(f"Button {button_index} pressed. Filling with {target_color}.")
                bank_colors[button_index] = target_color
                is_filled[button_index] = True
                fill_bank(button_index, target_color)  # Update light immediately

                # Check for win condition
                if all(is_filled):
                    game_state = WIN_STATE
                    print("All buttons filled! Transitioning to WIN_STATE.")
                else:
                    pass

    # --- State 2: WIN_STATE (New) ---
    elif game_state == WIN_STATE:
        win_sound()
        print("🎉 All buttons lit! Playing Rainbow Chase and Win Sound!")
        rainbow_chase(cycles=5, wait=0.005, speed=19)

        time.sleep(1.5)

        target_color = BLACK
        initial_button_index = -1
        is_filled = [False] * NUM_BUTTONS
        game_state = WAITING_FOR_COLOR_SELECT
        black_out_all()
        time.sleep(0.2)


# --- Program Entry Point ---
game_state = WAITING_FOR_COLOR_SELECT

while True:
    try:
        run_game_loop()
    except Exception as e:
        print(f"An error occurred: {e}")
        time.sleep(1)
    # small idle sleep to reduce busy-looping when run_game_loop returns quickly
    time.sleep_ms(10)
