import machine
import neopixel
import time
import random

# --- Config ---
NUM_BUTTONS = 10
LEDS_PER_BANK = 12

# Pin assignments for buttons and NeoPixel data lines
BUTTON_PINS = [10, 11, 12, 13, 14, 15, 17, 16, 18, 9]
LED_PINS = [0, 1, 2, 3, 4, 5, 6, 20, 22, 19]

# Colors (10 distinct colors for 10 buttons)
COLOR_PALETTE = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255),  # Red, Green, Blue
    (255, 255, 0), (255, 0, 255), (0, 255, 255),  # Yellow, Magenta, Cyan
    (255, 128, 0), (255, 255, 255), (128, 0, 128),  # Orange, White, Purple
    (0, 128, 255),  # Light Blue
]
BLACK = (0, 0, 0)

# Sound trigger pins (Assuming active-low triggers for BooTunes/MP3 modules)
SOUND_PIN = 21  # General Start Sound (Used for initial "Game Ready")
FAIL_SOUND = 8
SUCCESS_SOUND = 27  # Not used in this game mode, but kept for completeness
WIN_SOUND = 7

# --- Game State Variables ---
WAITING_FOR_START = 0  # Initial state, choosing target color
MEMORIZE_PHASE = 1  # Flashing and showing the pattern
WAITING_FOR_GUESS = 2  # Blackout phase, waiting for guess

game_state = WAITING_FOR_START
target_color = BLACK  # The color the user needs to find
correct_guess_index = -1  # The index (position) of the target color in the last display phase
initial_button_index = -1  # Stores the button index pressed to choose the target color
start_display_ready = False  # NEW FLAG: Tracks if the initial display setup has run

# New state variable to track if a button was pressed in the last loop (for debouncing)
button_was_pressed = [False] * NUM_BUTTONS
bank_colors = [BLACK] * NUM_BUTTONS  # Current colors displayed on the banks

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
    """
    Performs an in-place Fisher-Yates shuffle.
    Used as a replacement for random.shuffle, which is often missing in MicroPython.
    """
    length = len(data)
    for i in range(length - 1, 0, -1):
        # Pick a random index from 0 to i
        j = random.randrange(i + 1)
        # Swap data[i] with data[j]
        data[i], data[j] = data[j], data[i]


# --- LED Helpers ---

def fill_bank(bank_index, color):
    """Fills all LEDs in a single bank with one color."""
    strip = strips[bank_index]
    for i in range(LEDS_PER_BANK):
        strip[i] = color
    strip.write()


def fill_all(color):
    """Fills all LEDs across all banks with one color."""
    for i in range(NUM_BUTTONS):
        fill_bank(i, color)


def black_out_all():
    """Turns off all LEDs immediately."""
    fill_all(BLACK)


def update_all_banks():
    """Sets the color of each bank based on the current bank_colors list."""
    for i, color in enumerate(bank_colors):
        fill_bank(i, color)


def blink_all(color, times=3, delay=0.3):
    """Flashes all banks simultaneously."""
    for _ in range(times):
        fill_all(color)
        time.sleep(delay)
        black_out_all()
        time.sleep(delay)


def wheel(pos):
    """Converts a position (0-255) to an RGB color for rainbow effect."""
    if pos < 0 or pos > 255:
        return (0, 0, 0)
    if pos < 85:
        return (255 - pos * 3, pos * 3, 0)
    if pos < 170:
        pos -= 85
        return (0, 255 - pos * 3, pos * 3)
    pos -= 170
    return (pos * 3, 0, 255 - pos * 3)


def rainbow_chase(cycles=1, wait=0.01):
    """
    A high-speed, full-color chase effect.
    The chase flows across the LEDs of each strip AND across the strips themselves.
    The default wait time is now 10ms, which is usually visible.
    """
    for j in range(56 * cycles):
        for bank_index in range(NUM_BUTTONS):
            strip = strips[bank_index]
            for pixel_index in range(LEDS_PER_BANK):
                # Bank offset makes the pattern flow from strip to strip
                bank_offset = (bank_index * 256 // NUM_BUTTONS)

                # Combine offsets for a flowing effect across all 10 strips and within each strip
                # The total value is wrapped with & 255 (equivalent to modulo 256)
                pos = ((pixel_index * 256 // LEDS_PER_BANK) + j + bank_offset) & 255

                strip[pixel_index] = wheel(pos)
            strip.write()
        time.sleep(wait)  # Wait before calculating the next step 'j'


# --- Game Logic Helpers ---

def setup_target_display():
    """
    Sets up the initial display where the user chooses their target color.
    Each button lights up with a unique color from the palette.
    """
    global bank_colors

    # Create a mutable copy of the color palette to shuffle
    temp_colors = list(COLOR_PALETTE)

    # Shuffle the palette using our custom function to ensure MicroPython compatibility
    shuffle_list(temp_colors)

    bank_colors = temp_colors[:NUM_BUTTONS]  # Use up to 10 colors
    update_all_banks()
    # This print statement now only runs once when the game is ready to start.
    print("Game Ready: Press any button to select your target color.")


def setup_guess_display(target_color):
    """
    Generates a new display pattern for the guessing phase,
    ensuring the target color is present exactly once at a NEW, RANDOM position.
    """
    global bank_colors

    # 1. Start with a mutable copy of the full color palette (guaranteed 10 unique colors)
    new_colors = list(COLOR_PALETTE)

    # 2. Shuffle the entire list. This randomizes the position of the target color.
    shuffle_list(new_colors)

    # 3. Find the NEW, randomized index of the target color
    try:
        correct_index = new_colors.index(target_color)
    except ValueError:
        # Should not happen since target_color is selected from COLOR_PALETTE
        print("CRITICAL ERROR: Target color missing after shuffle.")
        correct_index = -1  # Indicate error

    # Assign and update
    bank_colors = new_colors
    update_all_banks()

    return correct_index


# --- Sound Helpers ---
# NOTE: These assume active-low triggers.

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


# --- Main Game Loop Functions ---

def handle_button_press():
    """Checks for a button press and handles debouncing."""
    for i, button in enumerate(buttons):
        # Read the current state of the button (PULL_UP means 0 is pressed)
        is_pressed_now = not button.value()

        # Detect a new press (button just went from released → pressed)
        if is_pressed_now and not button_was_pressed[i]:
            # Store the index of the button pressed
            button_index = i
            # Update debouncing state
            button_was_pressed[i] = is_pressed_now
            return button_index

        # Update debouncing state for released buttons
        button_was_pressed[i] = is_pressed_now

    return -1  # No new button pressed


def run_game_loop():
    """The primary state machine loop."""
    global game_state, target_color, correct_guess_index, initial_button_index, start_display_ready

    # --- State 0: WAITING_FOR_START ---
    if game_state == WAITING_FOR_START:

        # Only call setup_target_display once when entering this state (if the flag is False)
        if not start_display_ready:
            setup_target_display()
            start_display_ready = True  # Set flag to True so this block is skipped in subsequent loops

        button_index = handle_button_press()

        if button_index != -1:
            # 1. User presses button_index to set the target color
            target_color = bank_colors[button_index]
            initial_button_index = button_index  # Store the initial button pressed (used only for reference now)
            print(f"Target color set: {target_color} on button {button_index}. Target position will be RANDOMIZED.")

            # Transition to the flash/memorize phase
            game_state = MEMORIZE_PHASE
            start_display_ready = False  # Reset flag for when we eventually return to WAITING_FOR_START
            time.sleep(0.2)  # Short pause before the flash

    # --- State 1: MEMORIZE_PHASE ---
    elif game_state == MEMORIZE_PHASE:
        print("Starting MEMORIZE_PHASE: Flash, Display Pattern, Blackout.")

        # 2. Reaction Full Color Flash (Distraction)
        # Using cycles=2 and wait=0.01 (the default) to create a longer, more visible chase effect.
        rainbow_chase(cycles=2, wait=0.01)
        black_out_all()
        time.sleep(0.5)  # Blackout 1

        # 3. Show All Buttons in Different Colors (Memorize the pattern)
        # The correct_guess_index is now determined randomly inside this function
        correct_guess_index = setup_guess_display(target_color)
        print(f"Target color ({target_color}) is now at index: {correct_guess_index}")
        time.sleep(0.9)  # Give the user time to memorize

        # 4. Blackout
        black_out_all()

        # Transition to the guessing phase
        game_state = WAITING_FOR_GUESS

    # --- State 2: WAITING_FOR_GUESS ---
    elif game_state == WAITING_FOR_GUESS:
        button_index = handle_button_press()

        if button_index != -1:
            print(f"Guess received: Button {button_index}")

            if button_index == correct_guess_index:
                # WIN CONDITION
                print("🎉 CORRECT GUESS! YOU WIN!")
                win_sound()
                blink_all(target_color, times=11, delay=0.2)

                # Reset game to start over
                target_color = BLACK
                correct_guess_index = -1
                initial_button_index = -1  # Reset the initial index
                game_state = WAITING_FOR_START
                time.sleep(1.0)  # Pause after win effect

            else:
                # INCORRECT GUESS (Retry)
                print("❌ WRONG COLOR! Retrying the pattern.")
                fail_sound()
                # Briefly show the pressed button in Red to indicate failure
                fill_bank(button_index, (255, 0, 0))
                time.sleep(0.5)
                black_out_all()

                # Immediately re-enter the memorize phase to show a new pattern
                # The target color will remain fixed at the initial_button_index
                game_state = MEMORIZE_PHASE


# --- Program Entry Point ---
# The initial setup is now handled inside run_game_loop
game_state = WAITING_FOR_START

while True:
    try:
        run_game_loop()
    except Exception as e:
        print(f"An error occurred: {e}")
        time.sleep(1)  # Simple error handling to prevent crash

    time.sleep_ms(10)  # Loop delay for responsive button checking

