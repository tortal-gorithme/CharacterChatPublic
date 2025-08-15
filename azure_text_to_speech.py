import requests, json, os, re
import azure.cognitiveservices.speech as speechsdk
import codecs
import random

import super_duper_private.auth_stuff as auth

#### Fonction pour randomiser l'intonation

def random_contour():
    contour = ''
    n_points = random.randint(1,10)
    list_x = []
    list_y = []
    for i in range(n_points) :
        x = random.randint(0,100)
        while x in list_x :
            x = random.randint(0,100)
        y = random.randint(-100,100)
        list_x.append(x)
        list_y.append(y)
    list_x.sort()
    for i in range(n_points) :
        if list_y[i] < 0 :
            contour = contour + '(' + str(list_x[i]) + '%, ' + str(list_y[i]) + '%) '
        else :
            contour = contour + '(' + str(list_x[i]) + '%, +' + str(list_y[i]) + '%) '
    return contour

def random_rate():
    rate = random.randint(-50,20)
    if rate < 0 :
        newrate = str(rate) + '%'
    else :
        newrate = '+' + str(rate) + '%'
    return newrate


#### Azure setup ####
class AzureManager:
    languageCode = 'fr-FR'                          ### On pose des conditions de base : si rien n'est mentionné, la voix est Fabrice (la même que celle d'Ambroise)
    ssmlGender = 'MALE'
    voicName = 'fr-CH-FabriceNeural'
    speakingRate = '+0%'
    pitchh = '+0%'
    voiceStyle = 'cheerful'
    intonation = '(50%, -1%)'

    # définir les styles custom
    normal = {'rate' : "+0%", 'pitch' : "+0%", 'contour' : "(0%, +0%)"}
    # exemple de forme du contour : contour="(15%, -44%) (29%, +56%) (69%, +27%) (94%, -57%)"

    azureKey = auth.auth_azureKey
    azureRegion = auth.auth_azureRegion

#### Fonction pour générer le texte pour la requête sous forme de SSML

    def GenTTS_SSML(text, lang = languageCode, voice = voicName, style = voiceStyle, rate = speakingRate, pitch = pitchh, contour = intonation, intonation_random = False, debit_random = False, style_custom = normal):
        rate = style_custom['rate']
        pitch = style_custom['pitch']
        contour = style_custom['contour']
        if intonation_random == True :
            contour = random_contour()
            print(contour)
        if debit_random == True :
            rate = random_rate()
            print(rate)
        head1 = f'<speak xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="http://www.w3.org/2001/mstts" xmlns:emo="http://www.w3.org/2009/10/emotionml" version="1.0" xml:lang="{lang}">'
        head2 = f'<voice name="{voice}">'
        head3 =f'<mstts:express-as style="{style}">'
        head4 = f'<prosody rate="{rate}" pitch="{pitch}" contour="{contour}">'
        #head4 = f'<prosody rate="{rate}" pitch="{pitch}">'
        tail= '</prosody></mstts:express-as></voice></speak>'
        ssml = head1 + head2 + head3 + head4 + text + tail
        return ssml


#### Fonction pour envoyer la requête, pour générer l'audio et récupérer sous forme d'un fichier qui est ensuite lu

    def GenTTS_to_file(ssml, file, key = azureKey, region = azureRegion):
        try:
            speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
        except RuntimeError:
            exit("Ooops! You forgot to set AzureKey and AzureRegion ! Go change that in super_duper_private")
        audio_config = speechsdk.AudioConfig(filename=file)
        speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Audio48Khz96KBitRateMonoMp3)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        synthesizer.speak_ssml_async(ssml).get()
