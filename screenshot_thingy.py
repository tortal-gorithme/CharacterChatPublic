from mss import mss
from datetime import datetime
import keyboard
import time
from os import rename

output_folder = "screenshots/"

obs_screenshot_source = "screenshots/obs_screenshot.png"

sct = mss()
#sct.shot(output = "wesh.png")

def TakeTheShot(screen = 'full') :
    now = datetime.now()
    filename = now.strftime('%m_%d_%Y-_%H_%M_%S')
    full_filename = output_folder + filename + ".png"
    if screen == 'obs' :                         # Prendre un screenshot de l'output d'OBS plutôt que de l'écran
        keyboard.press('ctrl+alt+f11')
        time.sleep(0.5)
        keyboard.release('ctrl+alt+f11')
        time.sleep(0.5)
        renamed = False
        time_spent = 0.5
        while (renamed == False) and (time_spent < 5.0) :      
            try :
                rename(obs_screenshot_source,full_filename)
                renamed = True
            except :
                time.sleep(0.5)
                time_spent += 0.5
                print(time_spent)
        if time_spent == 5.0 :
            return None
    else :
        sct.shot(output = full_filename)
    return full_filename

if __name__ == '__main__':
    TakeTheShot(screen='full')
