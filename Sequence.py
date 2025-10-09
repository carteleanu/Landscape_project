import machine
import neopixel
import time
import random

# --- Config ---
NUM_BUTTONS = 10
LEDS_PER_BANK = 12
WAIT_DELAY_FRAMES = 50

BUTTON_PINS = [10, 11, 12, 13, 14, 15, 17, 16, 18, 9]
LED_PINS = [0, 1, 2, 3, 4, 5, 6, 20, 22, 19]

COLOR_PALETTE = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255),
    (255, 255, 0), (255, 0, 255), (0, 255, 255),
    (255, 128, 0), (255, 255, 255), (128, 0, 128),
    (0, 128, 255),
]

GREEN_FLASH = (0, 255, 0)
RED_FLASH = (255, 0, 0)
START_CUE_COLOR = (0, 0, 50)

SOUND_PIN = 21
FAIL_SOUND = 8
SUCCESS_SOUND = 27
WIN_SOUND = 7

buttons = [machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_UP) for pin in BUTTON_PINS]
strips = [neopixel.NeoPixel(machine.Pin(pin), LEDS_PER_BANK) for pin in LED_PINS]

sound_trigger_pin = machine.Pin(SOUND_PIN, machine.Pin.OUT)
sound_trigger_pin.value(1)
fail_trigger_pin = machine.Pin(FAIL_SOUND, machine.Pin.OUT)
fail_trigger_pin.value(1)
success_trigger_pin = machine.Pin(SUCCESS_SOUND, machine.Pin.OUT)
success_trigger_pin.value(1)
win_trigger_pin = machine.Pin(WIN_SOUND, machine.Pin.OUT)
win_trigger_pin.value(1)

# --- State ---
game_state = "WAIT_FOR_START"
game_color = (0, 0, 0)
sequence_order = []
current_step_index = 0

button_was_pressed = [False] * NUM_BUTTONS

# state variables for non-blocking WAIT_FOR_START animation
wait_anim_index = 0
wait_anim_frame_counter = 0


# --- Helper functions ---
def fill_bank(bank_index, color):
    """Sets all LEDs in one bank to a single color and updates the strip."""
    strip = strips[bank_index]
    for i in range(LEDS_PER_BANK):
        strip[i] = color
    strip.write()


def turn_off_all():
    for i in range(NUM_BUTTONS):
        fill_bank(i, (0, 0, 0))


def blink_bank(bank_index, color, times=1, delay=0.1):
    for _ in range(times):
        fill_bank(bank_index, color)
        time.sleep(delay)
        fill_bank(bank_index, (0, 0, 0))
        time.sleep(delay)


def micro_shuffle(list_to_shuffle):
    n = len(list_to_shuffle)
    for i in range(n - 1, 0, -1):
        j = random.randint(0, i)
        list_to_shuffle[i], list_to_shuffle[j] = list_to_shuffle[j], list_to_shuffle[i]


def play_sound():
    sound_trigger_pin.value(0)
    time.sleep_ms(100)
    sound_trigger_pin.value(1)


def fail_sound():
    fail_trigger_pin.value(0)
    time.sleep_ms(100)
    fail_trigger_pin.value(1)


def success_sound():
    success_trigger_pin.value(0)
    time.sleep_ms(100)
    success_trigger_pin.value(1)


def win_sound():
    win_trigger_pin.value(0)
    time.sleep_ms(100)
    win_trigger_pin.value(1)


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


def rainbow_chase(cycles=5, wait=0, speed=10):
    for j in range(0, 256 * cycles, speed):
        for bank_index in range(NUM_BUTTONS):
            strip = strips[bank_index]
            for pixel_index in range(LEDS_PER_BANK):
                pos = (pixel_index * 256 // LEDS_PER_BANK) + j
                strip[pixel_index] = wheel(pos & 255)
            strip.write()

        if wait > 0:
            time.sleep(wait)


# --- Game logic ---
def setup_game():
    global game_color, sequence_order, current_step_index, game_state

    turn_off_all()

    # Choose a random color for this round
    game_color = random.choice(COLOR_PALETTE)
    # Generate a shuffled sequence of button indices (0-9)
    sequence_order = list(range(NUM_BUTTONS))
    micro_shuffle(sequence_order)

    current_step_index = 0

    game_state = "SHOW_STEP"
    play_sound()
    time.sleep(0.5)


def show_current_step():
    global game_state

    turn_off_all()

    # The button index we need to light up
    target_bank = sequence_order[current_step_index]
    fill_bank(target_bank, game_color)

    game_state = "PLAYER_TURN"


def handle_player_turn(pressed_idx):
    global current_step_index, game_state

    expected_idx = sequence_order[current_step_index]

    if pressed_idx == expected_idx:
        # --- CORRECT PRESS ---
        blink_bank(pressed_idx, GREEN_FLASH, times=1, delay=0.05)
        success_sound()

        current_step_index += 1

        if current_step_index >= NUM_BUTTONS:
            game_state = "WIN"
        else:
            game_state = "SHOW_STEP"
    else:
        # --- INCORRECT PRESS (FAIL) ---
        blink_bank(pressed_idx, RED_FLASH, times=2, delay=0.1)
        fail_sound()
        game_state = "FAIL"  # Transition to FAIL state


def handle_fail():
    global game_state, wait_anim_index, wait_anim_frame_counter

    turn_off_all()

    # Flash ALL lights red for Game Over cue
    for i in range(NUM_BUTTONS):
        fill_bank(i, RED_FLASH)
    time.sleep(1.0)

    turn_off_all()
    # Reset animation variables when returning to wait state
    wait_anim_index = 0
    wait_anim_frame_counter = 0
    game_state = "WAIT_FOR_START"


def handle_win():
    global game_state, current_step_index, wait_anim_index, wait_anim_frame_counter

    win_sound()
    rainbow_chase(cycles=5, wait=0, speed=10)

    turn_off_all()
    current_step_index = 0
    # Reset animation variables when returning to wait state
    wait_anim_index = 0
    wait_anim_frame_counter = 0
    game_state = "WAIT_FOR_START"


# --- Main loop ---
while True:
    if game_state == "WAIT_FOR_START":

        # --- 1. Non-Blocking Animation Update ---
        wait_anim_frame_counter += 1

        if wait_anim_frame_counter >= WAIT_DELAY_FRAMES:
            wait_anim_frame_counter = 0

            turn_off_all()

            # Light up the next button in the cycle
            fill_bank(wait_anim_index, random.choice(COLOR_PALETTE))

            wait_anim_index = (wait_anim_index + 1) % NUM_BUTTONS

        # --- 2. Button Check (looking for any raw press to start) ---
        start_pressed_now = False
        for btn in buttons:
            if not btn.value():  # Check for any raw press (active low)
                start_pressed_now = True
                break

        if start_pressed_now:
            turn_off_all()
            # Transition to the consuming state to wait for release
            game_state = "CONSUME_START_PRESS"

    elif game_state == "CONSUME_START_PRESS":
        # NEW ROBUST STATE: Block here (non-blocking in the main loop sense) until the user releases the button.
        all_released = True
        for btn in buttons:
            if not btn.value():  # Button is pressed (value is 0)
                all_released = False
                break

        if all_released:
            # Once released, reset button history and jump to game setup
            button_was_pressed = [False] * NUM_BUTTONS
            game_state = "SETUP"

    elif game_state == "SETUP":
        setup_game()
    elif game_state == "SHOW_STEP":
        show_current_step()
    elif game_state == "PLAYER_TURN":
        # Check all buttons for press activity
        for i, btn in enumerate(buttons):
            pressed = not btn.value()  # True if currently pressed

            if pressed and not button_was_pressed[i]:
                # Detected a *new* button press (edge detection)
                handle_player_turn(i)
                # Break to ensure only one button is processed per frame
                break

                # Update history for debouncing
            button_was_pressed[i] = pressed

    elif game_state == "WIN":
        handle_win()
    elif game_state == "FAIL":
        handle_fail()

    # The core loop delay (10ms) is essential for the non-blocking state machine
    time.sleep_ms(10)

