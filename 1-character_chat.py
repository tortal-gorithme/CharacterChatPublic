import time
import os
import ast
from datetime import datetime, timedelta
import keyboard
from rich import print
import asyncio
import pygame
import logging                                                  #########
import threading                                                #########
from azure_speech_to_text import SpeechToTextManager
import googletrans                                      # Utilisé pour la traduction si nécessaire
from llama_chat import LlamaManager                     # Comprend les fonctions pour l'API local (koboldcpp) - pas forcément llama donc mais n'importe quel modèle compatible
from google_chat import GoogleManager                   # Comprend les fonctions pour l'API Google
from azure_text_to_speech import AzureManager
from obs_websockets import OBSWebsocketsManager
from audio_player import AudioManager
import character_prompts as prompts                     # Comprend les prompts pour les personnages

###### Initialisation des paramètres : Switch entre Llama et Google api, + choix de traduire ou pas les inputs
model = "google"
# -> valeurs possibles : "google", "llama"
tts_model = "azure"
translate_toggle = False                # Si actif, on fait FR -> EN -> inference -> FR (pas nécessaire avec un modèle performant style Google)
modular_context_toggle = False          # Expérimental et pas prêt pour la version Google du programme
twitch_chat_toggle = False
visual_interface = "None"                # La version de base affiche l'image dans OBS, mais peut fonctionner en rajoutant d'autres techniques (par exemple pygame)
# -> valeurs possibles : "OBS", "pygame" (expérimental), "None" (uniquement son)
thinkythink = False                     # Activer le mode thinking par défaut, non-recommandé car pas pratique pour une conversation

##############################################################################################################

speechtotext_manager = SpeechToTextManager()
audio_manager = AudioManager()
if model == "llama" :
    llama_manager = LlamaManager()
if model == "google" :
    google_manager = GoogleManager()
if visual_interface == "OBS" :
    obswebsockets_manager = OBSWebsocketsManager()

#### CHOOSE CHARACTER
character = prompts.fr_johnny                                    ### Le personnage choisi est une liste définie dans le fichier character_prompts
character_prompt = character['prompt']
character_name = character['name']                               # Comment appeler l'IA si on est en mode chat Twitch
character_voice = character['voice']
character_ref = character['ref']                                 # Si jamais on veut différencier deux versions d'un même personnage pour le backup

#####################

# Définir les fichiers locaux

BACKUP_FILE = "ChatHistoryBackup_" + character_name + ".txt"
if os.path.exists(BACKUP_FILE) :
    with open(BACKUP_FILE, "r", encoding="utf-8") as file :
        BACKUP_FILE_LOAD = file.read()
else :
    BACKUP_FILE_LOAD = ''
current_TTS_file = "tts.mp3"

#############################


# Définir la coroutine pour la traduction, si nécessaire
mic_result = ""
mic_result_en = ""
message_utilisateur = ""
message_utilisateur_en = ""
ai_result = ""
ai_result_fr = ""
text_trad = ""

async def translate_input(language = "en"):
    async with googletrans.Translator() as translator:
        global mic_result
        global mic_result_en
        result = await translator.translate(mic_result, dest = language)
        mic_result_en = result.text

async def translate_chat_input(language = "en"):
    async with googletrans.Translator() as translator:
        global message_utilisateur
        global message_utilisateur_en
        result = await translator.translate(message_utilisateur, dest = language)
        message_utilisateur_en = result.text

async def translate_output(language = "fr"):
    async with googletrans.Translator() as translator:
        global ai_result
        global ai_result_fr
        result = await translator.translate(ai_result, dest = language)
        ai_result_fr = result.text

async def translate_text(text, language = "en"):
    async with googletrans.Translator() as translator:
        global text_trad
        result = await translator.translate(text, dest = language)
        text_trad = result.text                                      

########################################################

############## Initialiser le(s) modèle(s) avec le system prompt + le contexte modulaire si actif

if model == "llama" :
    FIRST_SYSTEM_MESSAGE = {"role": "system", "content": character_prompt}
    llama_manager.chat_history.append(FIRST_SYSTEM_MESSAGE)
elif model == "google" :
    FIRST_SYSTEM_MESSAGE = character_prompt
    FIRST_SYSTEM_MESSAGE_TEMP = FIRST_SYSTEM_MESSAGE

OPTIONAL_CONTEXT_LIST = []
if modular_context_toggle == True :
    if translate_toggle == True :
        Optional_context_base = "\n Here is some additional information that your character knows : \n"
        Jean_context = ["jean", "Jean's birthday is on July 26. \n"]
    elif translate_toggle == False :
        Optional_context_base = "\n Voici quelques informations supplémentaires que ton personnage connaît : \n"
        Jean_context = ["jean", "L'anniversaire de Jean est le 26 juillet. \n"]
    OPTIONAL_CONTEXT_LIST.append(Jean_context)

#################################################################################################

############ Lancer un thread avec une instance pygame
thread_running = False

def playsound(file):
    global thread_running
    logging.info("Thread %s: starting", file)
    thread_running = True
    audio_manager.play_audio(current_TTS_file, True, True, True)
    logging.info("Thread %s: finishing", file)
    thread_running = False

######################################################

###### Définir des fonctions à utiliser pendant la boucle (pour la rendre plus lisible)

def ShowAndPlay(image_to_show = 'ambroise', file_to_play = current_TTS_file, visual_interface = visual_interface) :
    if visual_interface == "OBS" :
        obswebsockets_manager.set_source_visibility("Scène AI", "ambroise", True)        # Montrer l'image du bot
        obswebsockets_manager.set_source_visibility("Scène webcam", "ambroise", True)
        obswebsockets_manager.set_source_visibility("Nested AI", "ambroise", True)
        audio_manager.play_audio(file_to_play, True, True, True)                    # Jouer le son
        obswebsockets_manager.set_source_visibility("Scène AI", "ambroise", False)      # Cacher l'image du bot
        obswebsockets_manager.set_source_visibility("Scène webcam", "ambroise", False)
        obswebsockets_manager.set_source_visibility("Nested AI", "ambroise", False)
    elif visual_interface == "pygame" :
        pygame.init()
        (width, height) = (720, 480)
        screen = pygame.display.set_mode((width, height))
        image_personnage = pygame.image.load("images\\" + image_to_show + ".png").convert_alpha()
        (image_width, image_height) = image_personnage.get_size()
        scale = 1
        while scale * (image_width * image_height) > 1000000 :
            scale = scale * 0.75
            print(scale)
        image_personnage_scaled = pygame.transform.smoothscale_by(image_personnage,scale)
        (scaled_width, scaled_height) = image_personnage_scaled.get_size()
        screen = pygame.display.set_mode((scaled_width, scaled_height))
        pygame.display.flip()
        clock = pygame.time.Clock()
        running = True
        pygame.display.set_caption('Discussion IA')
        x = threading.Thread(target=playsound, args=(1,), daemon=True)
        x.start()
        while running:
            # On check à chaque frame si l'écran doit se fermer
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            screen.fill(color=("grey"))
            screen.blit(image_personnage_scaled, (0, 0))
            # affiche l'écran
            pygame.display.flip()
            if thread_running == False :
                running = False
            clock.tick(60)  # limite les FPS à 60
        pygame.quit()
    elif visual_interface == "None" :
        audio_manager.play_audio(file_to_play, True, True, True)
    return

def MakeAndPlayAISound(voice_to_use = character_voice, TTS_api = "azure", output_file = current_TTS_file, text_to_read = "") :     # Créer le fichier mp3 et le jouer dans le périphérique voulu
    if text_to_read == "" :
        if translate_toggle == True :
            asyncio.run(translate_output())
            text_to_read = ai_result_fr
        else :
            text_to_read = ai_result
    if TTS_api == "azure" :
        TTS_SSML = AzureManager.GenTTS_SSML(text_to_read, pitch= '0%', rate= '0%', voice=voice_to_use)
        AzureManager.GenTTS_to_file(TTS_SSML,output_file)
        ShowAndPlay(file_to_play=output_file)
    elif TTS_api == "google" :
        pass                # Pas implémenté
    elif TTS_api == "eleven labs" :
        pass                # Pas implémenté
    return


def CheckMessage(message_content, message_username) :                        # Cacher tous les triggers qui peuvent venir du chat Twitch dans cette fonction
    pass        #WIP
    return

#######################################################################################

if __name__ == "__main__":

    startdate = datetime.now()
    First_load = True
    print("[green]Starting the loop, press F4 or send message in twitch chat to begin")
    while True:
        FIRST_SYSTEM_MESSAGE_TEMP = FIRST_SYSTEM_MESSAGE
        thinkythink = False
        if First_load == True :
            backup = BACKUP_FILE_LOAD
        else :
            backup = ''
        # La boucle d'écoute ne démarre que quand l'utilisateur appuie sur f4, sinon on cherche un trigger dans le chat log
        # Eventuellement, on peut changer le trigger d'écoute, par exemple si on est sur une interface web et qu'on veut qu'un bouton active l'écoute
        if keyboard.read_key() != "f4":
            time.sleep(0.1)
            if twitch_chat_toggle == True :
                log = open("0_chat.log", "r", encoding='utf-8')
                # Check si question dans le chat
                for line in log :
                    #print("Trouvé une ligne")
                    msg_date = line.split()[0].strip()
                    msg_date = datetime.strptime(msg_date, '%Y-%m-%d_%H:%M:%S')
                    if msg_date <= startdate :                         # Pour éviter de relire de vieux messages
                        pass
                    else :
                        username_message = line.split()[2:]
                        username = username_message[0]
                        message = username_message[2:]
                        msg = ' '.join(message)
                        startdate = msg_date
                        if (modular_context_toggle == True) and (msg[0:14].lower() == character_name + " retiens") :                       # Exemple : "Johnny retiens Jean - Jean est le père d'Erkyos"
                            try :
                                split_msg = msg[15:].split("-")
                                trigger = split_msg[0].lower().strip()
                                content_fr = split_msg[1].strip()
                                if translate_toggle == True :
                                    asyncio.run(translate_text(content_fr, language="en"))
                                    content = text_trad
                                elif translate_toggle == False :
                                    content = content_fr
                                OPTIONAL_CONTEXT_LIST.append([trigger, content])
                                print(OPTIONAL_CONTEXT_LIST)
                            except :
                                print("Wrong format for optional context")
                        elif msg[0:len(character_name)+3].lower() == "ok " + character_name :
                            print("[green]User called AI! Now generating answer:")
                            if modular_context_toggle == True :
                                OPTIONAL_CONTEXT = ""
                                for i in OPTIONAL_CONTEXT_LIST :
                                    print(i[0])
                                    if i[0] in msg.lower() :
                                        print(i[0] + " was found in message ! Adding to context")
                                        print("Optional context has been called !")
                                        if OPTIONAL_CONTEXT == [] :
                                            OPTIONAL_CONTEXT += Optional_context_base
                                        OPTIONAL_CONTEXT += i[1]
                                    if model == "llama" :
                                        llama_manager.chat_history[0]['content'] += OPTIONAL_CONTEXT
                                    elif model == "google" :
                                        FIRST_SYSTEM_MESSAGE_TEMP = FIRST_SYSTEM_MESSAGE + OPTIONAL_CONTEXT

                            message_utilisateur = msg[len(character_name)+3:]
                            if translate_toggle == True :
                                asyncio.run(translate_chat_input())
                                print(f"[blue] input translates to : {message_utilisateur_en}")
                            elif translate_toggle == False :
                                print(f"[blue] input : {message_utilisateur}")
                    
                            # Envoyer le message à l'API locale ou l'API Google
                            if model == "llama" :
                                if translate_toggle == True :
                                    ai_result = llama_manager.chat_with_history(username + " : " + message_utilisateur_en)
                                elif translate_toggle == False :
                                    ai_result = llama_manager.chat_with_history(username + " : " + message_utilisateur)
                                if (ai_result[0:7].lower() == character_name + ":") :
                                    ai_result = ai_result[7:]
                                elif (ai_result[0:8].lower() == character_name + ":") :
                                    ai_result = ai_result[8:]
                                print(ai_result)
                                # Backup de l'historique
                                with open(BACKUP_FILE, "w", encoding="utf-8") as file:
                                    file.write(str(llama_manager.chat_history))
                                # S'assurer qu'on a bien gardé le prompt
                                llama_manager.chat_history[0]['content'] = character_prompt
                            if model == "google" :
                                if translate_toggle == True :
                                    ai_result = google_manager.chat_with_history(username + " : " + message_utilisateur_en, system=FIRST_SYSTEM_MESSAGE_TEMP, existing_history=backup)
                                elif translate_toggle == False :
                                    ai_result = google_manager.chat_with_history(username + " : " + message_utilisateur, system=FIRST_SYSTEM_MESSAGE_TEMP, existing_history=backup)
                                    print(username + " : " + message_utilisateur)
                                if (ai_result[0:7].lower() == character_name + ":") :
                                    ai_result = ai_result[7:]
                                elif (ai_result[0:8].lower() == character_name + ":") :
                                    ai_result = ai_result[8:]
                                print(f"[green]\n{ai_result}\n")
                                # Backup de l'historique
                                with open(BACKUP_FILE, "w", encoding="utf-8") as file:
                                    file.write(str(google_manager.chat_history))                        
                            MakeAndPlayAISound(TTS_api=tts_model)
                            print(f"[green]\n{ai_result}\n")

                            #print(f"[red]\n{llama_manager.chat_history}\n")
                            if translate_toggle == True :
                                print(f"[green]\n{ai_result_fr}\n")

                            print("[green]\n!!!!!!!\nFINISHED PROCESSING DIALOGUE.\nREADY FOR NEXT INPUT\n!!!!!!!\n")
                #print("J'ai plus de ligne :(")
                continue
            else :
                continue

        print("[green]User pressed F4 key! Now listening to your microphone:")

        # Ecouter le micro pour l'input
        mic_result_full = speechtotext_manager.speechtotext_from_mic_continuous_with_options()
            # format retourné : {'result' : , 'thinking' : , 'image' : }
        mic_result = mic_result_full['result']
        thinkythink = mic_result_full['thinking']
        image_toggle = mic_result_full['image']
        image_path = mic_result_full['image_ref']
        if translate_toggle == True :
            asyncio.run(translate_input())
            print(f"[blue] input translates to : {mic_result_en}")
            voice_input = mic_result_en
        elif translate_toggle == False :
            voice_input = mic_result
            print(f"[blue] input : {mic_result}")
        # Check si un trigger a été donné pour le contexte modulaire
        if modular_context_toggle == True :
            OPTIONAL_CONTEXT = ""
            for i in OPTIONAL_CONTEXT_LIST :
                if (i[0] in mic_result.lower() and translate_toggle == False) or (i[0] in mic_result_en.lower() and translate_toggle == True) :
                    print(i[0] + " was found in message ! Adding to context")
                    print("Optional context has been called !")
                    if OPTIONAL_CONTEXT == [] :
                        OPTIONAL_CONTEXT += Optional_context_base
                        OPTIONAL_CONTEXT += i[1]
                    if model == "llama" :
                        llama_manager.chat_history[0]['content'] += OPTIONAL_CONTEXT
                    elif model == "google" :
                        FIRST_SYSTEM_MESSAGE_TEMP = FIRST_SYSTEM_MESSAGE + OPTIONAL_CONTEXT

        # Envoyer l'input à l'API locale ou l'API Google, puis backup le nouvel historique
        if model == "lama" :
            ai_result = llama_manager.chat_with_history(voice_input)
            with open(BACKUP_FILE, "w", encoding="utf-8") as file:
                file.write(str(llama_manager.chat_history))
        elif model == "google" :
            if image_toggle == True :
                image_temp = image_path
            else :
                image_temp = None
            ai_result = google_manager.chat_with_history(prompt=voice_input, system=FIRST_SYSTEM_MESSAGE_TEMP, thinking_mode= thinkythink, existing_history=backup, image= image_temp)
            with open(BACKUP_FILE, "w", encoding="utf-8") as file:
                file.write(str(google_manager.chat_history))

        MakeAndPlayAISound(TTS_api=tts_model)

        print(f"[green]\n{ai_result}\n")

        if translate_toggle == True :
            print(f"[green]\n{ai_result_fr}\n")

        print("[green]\n!!!!!!!\nFINISHED PROCESSING DIALOGUE.\nREADY FOR NEXT INPUT\n!!!!!!!\n")