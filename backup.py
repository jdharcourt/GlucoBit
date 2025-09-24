import board
import audiobusio
import touchio
from audiocore import WaveFile

# I2S pin mapping for XIAO ESP32-S3
BCLK = board.D5
LRCLK = board.D6
DIN = board.D4

# Create I2SOut for MAX98357A
audio = audiobusio.I2SOut(bit_clock=BCLK, word_select=LRCLK, data=DIN)

# Touch sensor
touch = touchio.TouchIn(board.D0)

def play_file_until_touched(filename):
    print("Playing file until touched:", filename)
    with open(filename, "rb") as wave_file:
        wave = WaveFile(wave_file)
        
        # Loop until touch
        while not touch.value:
            audio.play(wave)
            # Wait while playing or stop immediately if touched
            while audio.playing and not touch.value:
                pass

    # Stop permanently once touched
    if audio.playing:
        audio.stop()
    print("Finished")

# Main loop
play_file_until_touched("audio/amplified.wav")  # Plays until D0 touched, then stops forever
