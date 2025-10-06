import machine
import neopixel
import time
import random

# --- Config ---
NUM_BUTTONS = 10
LEDS_PER_BANK = 12

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

SOUND_PIN = 21
FAIL_SOUND = 8
SUCCESS_SOUND = 27
WIN_SOUND = 7

# --- Hardware setup ---
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
game_state = "SETUP"
game_color = (0, 0, 0)
sequence_order = []
sequence_index = 0
button_was_pressed = [False] * NUM_BUTTONS

# --- Helper functions ---
def fill_bank(bank_index, color):
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

# --- Game logic ---
def setup_game():
    global game_color, sequence_order, sequence_index, game_state
    turn_off_all()
    game_color = random.choice(COLOR_PALETTE)
    sequence_order = list(range(NUM_BUTTONS))
    micro_shuffle(sequence_order)
    sequence_index = 1
    game_state = "SHOW_SEQUENCE"
    play_sound()
    time.sleep(0.5)

def show_sequence_intro():
    global game_state
    turn_off_all()
    for idx in sequence_order:
        fill_bank(idx, game_color)
        time.sleep(0.3)
    turn_off_all()
    # Light first button as hint
    fill_bank(sequence_order[0], game_color)
    game_state = "PLAYER_TURN"

def handle_player_turn(pressed_idx):
    global sequence_index, game_state
    # Check if sequence_index is valid
    if sequence_index >= NUM_BUTTONS:
        sequence_index = 0
        game_state = "SETUP"
        return

    expected_idx = sequence_order[sequence_index]

    if pressed_idx == expected_idx:
        blink_bank(pressed_idx, GREEN_FLASH)
        success_sound()
        fill_bank(pressed_idx, game_color)
        sequence_index += 1
        if sequence_index >= NUM_BUTTONS:
            game_state = "WIN"
    else:
        blink_bank(pressed_idx, RED_FLASH, times=2)
        fail_sound()
        #turn_off_all()
        #sequence_index = 0
        #fill_bank(sequence_order[0], game_color)

def handle_win():
    global game_state, sequence_index
    win_sound()
    for j in range(3):
        for i in range(NUM_BUTTONS):
            fill_bank(i, random.choice(COLOR_PALETTE))
        time.sleep(3)
    turn_off_all()
    sequence_index = 0
    game_state = "SETUP"

# --- Main loop ---
while True:
    if game_state == "SETUP":
        setup_game()
    elif game_state == "SHOW_SEQUENCE":
        show_sequence_intro()
    elif game_state == "PLAYER_TURN":
        for i, btn in enumerate(buttons):
            pressed = not btn.value()
            if pressed and not button_was_pressed[i]:
                handle_player_turn(i)
            button_was_pressed[i] = pressed
    elif game_state == "WIN":
        handle_win()
    time.sleep_ms(10)

