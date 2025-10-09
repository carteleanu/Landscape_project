import machine
import neopixel
import time
import random

# --- Config ---
NUM_BUTTONS = 10
LEDS_PER_BANK = 12
TOTAL_LEDS = NUM_BUTTONS * LEDS_PER_BANK  # Added: Total number of LEDs for the chase effect
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
SOUND_PIN = 21  # General Start Sound (Used for initial "Game Ready")
FAIL_SOUND = 8
SUCCESS_SOUND = 27
WIN_SOUND = 7

# --- Game State Variables ---
WAITING_FOR_START = 0
MEMORIZE_PHASE = 1
WAITING_FOR_GUESS = 2

game_state = WAITING_FOR_START
target_color = BLACK  # The color the user needs to find
correct_guess_index = -1  # The index (position) of the target color in the last display phase
initial_button_index = -1  # Stores the button index pressed to choose the target color
start_display_ready = False  # Tracks if the initial display setup has run

# Track previous button pressed state (for edge detection)
button_was_pressed = [False] * NUM_BUTTONS
# Track last accepted press time for debounce
last_press_time = [0] * NUM_BUTTONS

bank_colors = [BLACK] * NUM_BUTTONS  # Current colors displayed on the banks

# --- Fire flicker globals (localized per-bank) ---
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
def shuffle_list(data):
    length = len(data)
    for i in range(length - 1, 0, -1):
        j = random.randrange(i + 1)
        data[i], data[j] = data[j], data[i]


# --- LED Helpers ---
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


def alert_lights_fail(bank_index, flashes=4, delay=0.1):
    for _ in range(flashes):
        fill_bank(bank_index, (255, 0, 0))  # Red
        time.sleep(delay)
        fill_bank(bank_index, (0, 0, 255))  # White
        time.sleep(delay)
    fill_bank(bank_index, (0, 0, 0))  # Turn off


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
    # HUE_STEP_PER_PIXEL ensures the color pattern transitions smoothly across banks.
    HUE_STEP_PER_PIXEL = 256 / TOTAL_LEDS

    for j in range(0, 256 * cycles, speed):
        for bank_index in range(NUM_BUTTONS):
            strip = strips[bank_index]
            for pixel_index in range(LEDS_PER_BANK):
                global_pixel_index = (bank_index * LEDS_PER_BANK) + pixel_index
                pos = int(global_pixel_index * HUE_STEP_PER_PIXEL + j) & 255
                strip[pixel_index] = wheel(pos)
            strip.write()
        time.sleep(wait)


# --- Game Logic Helpers ---

def fire_flicker():
    global fire_current_brightness, fire_target_brightness, fire_last_update

    now = time.ticks_ms()

    for i in range(NUM_BUTTONS):
        # occasionally pick a new target brightness for this bank (randomized interval)
        if time.ticks_diff(now, fire_last_update[i]) > random.randint(70, 160):
            fire_last_update[i] = now
            fire_target_brightness[i] = random.uniform(0.06, 0.28)

        # smooth easing toward target brightness
        fire_current_brightness[i] += (fire_target_brightness[i] - fire_current_brightness[i]) * 0.18

        # slight per-bank color variation for depth
        r = random.randint(200, 255)
        g = random.randint(60, 130)
        b = random.randint(0, 25)

        brightness = fire_current_brightness[i]
        color = (int(r * brightness), int(g * brightness), int(b * brightness))

        # apply to entire bank
        strip = strips[i]
        for j in range(LEDS_PER_BANK):
            strip[j] = color
        strip.write()


def setup_target_display():
    global bank_colors

    temp_colors = list(COLOR_PALETTE)
    shuffle_list(temp_colors)
    bank_colors = temp_colors[:NUM_BUTTONS]  # Use up to NUM_BUTTONS colors
    update_all_banks()
    print("Game Ready: Press any button to select your target color.")


def setup_guess_display(target_color):
    global bank_colors

    new_colors = list(COLOR_PALETTE)
    shuffle_list(new_colors)
    try:
        correct_index = new_colors.index(target_color)
    except ValueError:
        print("CRITICAL ERROR: Target color missing after shuffle.")
        correct_index = -1

    bank_colors = new_colors
    update_all_banks()
    return correct_index


# --- Sound Helpers ---
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


# --- Button handling (edge detect + debounce) ---
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


# --- Main Game Loop Functions ---
def run_game_loop():
    global game_state, target_color, correct_guess_index, initial_button_index, start_display_ready

    # --- State 0: WAITING_FOR_START ---
    if game_state == WAITING_FOR_START:
        if not start_display_ready:
            setup_target_display()
            start_display_ready = True

        button_index = handle_button_press()

        if button_index != -1:
            # User presses button_index to set the target color
            target_color = bank_colors[button_index]
            initial_button_index = button_index
            print(f"Target color set: {target_color} on button {button_index}. Target position will be RANDOMIZED.")

            game_state = MEMORIZE_PHASE
            start_display_ready = False
            time.sleep(0.5)  # short pause before memorize phase

    # --- State 1: MEMORIZE_PHASE ---
    elif game_state == MEMORIZE_PHASE:
        print("Starting MEMORIZE_PHASE: Chase, Display Pattern, Blackout.")
        # play chase animation
        rainbow_chase(cycles=10, wait=0.01, speed=35)
        black_out_all()
        time.sleep(0.6)

        correct_guess_index = setup_guess_display(target_color)
        print(f"Target color ({target_color}) is now at index: {correct_guess_index}")
        time.sleep(1.0)

        black_out_all()
        game_state = WAITING_FOR_GUESS

    # --- State 2: WAITING_FOR_GUESS ---
    elif game_state == WAITING_FOR_GUESS:
        button_index = handle_button_press()
        if button_index == -1:
            # No button pressed → show a single frame of flicker and return quickly
            fire_flicker()
            # small pacing to allow visible flicker but keep responsiveness
            time.sleep_ms(30)
            return  # keep main loop cycling frequently

        # If we reach here, a new button press was detected
        print(f"Guess received: Button {button_index}")

        if button_index == correct_guess_index:
            # WIN CONDITION
            print("🎉 CORRECT GUESS! YOU WIN!")
            win_sound()
            blink_all(target_color, times=12, delay=0.2)

            # Reset game to start over
            target_color = BLACK
            correct_guess_index = -1
            initial_button_index = -1
            game_state = WAITING_FOR_START
            time.sleep(1.0)

        else:
            # INCORRECT GUESS (Retry)
            print("❌ WRONG COLOR! Retrying the pattern.")
            fail_sound()
            # Briefly show the pressed button in Red to indicate failure
            alert_lights_fail(button_index)
            time.sleep(0.5)
            black_out_all()
            game_state = MEMORIZE_PHASE


# --- Program Entry Point ---
game_state = WAITING_FOR_START

while True:
    try:
        run_game_loop()
    except Exception as e:
        print(f"An error occurred: {e}")
        time.sleep(1)
    # small idle sleep to reduce busy-looping when run_game_loop returns quickly
    time.sleep_ms(10)

