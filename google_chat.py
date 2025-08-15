import tiktoken
import ast
import requests, json, os, re
import codecs
from rich import print
from google import genai
from google.genai import types
from google.genai.types import Content, Part
import super_duper_private.auth_stuff as auth
import PIL

#### Specifique à l'API Google

try :
    client = genai.Client(api_key=auth.google_api)
except ValueError:
    exit("Ooops! You forgot to set Google api key ! Go change that in super_duper_private")

def prompt_to_response(history, system_prompt = "", thinking = False, tools = [], tools_only = False, force_model = ""):
    #print (tools)
    response = ""
    #models = ["gemini-2.0-flash","gemini-2.0-flash-lite","gemini-1.5-flash","gemini-1.5-flash-8b", "gemma-3-27b-it"]
    models = ["gemini-2.5-flash-lite-preview-06-17", "gemini-2.5-flash-preview-04-17", "gemini-2.0-flash","gemini-2.0-flash-lite","gemini-1.5-flash","gemini-1.5-flash-8b", "gemma-3-27b-it"]
    thinking_models = ["gemini-2.5-pro-preview-05-06","gemini-2.5-pro-exp-03-25", "gemini-2.0-flash-thinking-exp-01-21"]
    tools_models = ["gemini-2.0-flash-lite", "gemini-1.5-flash"]
    if tools == [] :
        generate_content_config = types.GenerateContentConfig(response_mime_type="text/plain",
                                                                system_instruction=[types.Part.from_text(text = system_prompt),])
    else :
        generate_content_config = types.GenerateContentConfig(response_mime_type="text/plain",
                                                                system_instruction=[types.Part.from_text(text = system_prompt),],
                                                                tools=[types.Tool(function_declarations=tools)])
    if tools_only == True :
        for item in tools_models :                                  # Si le premier modèle a atteint son quota, on passe au suivant
            try :
                response = client.models.generate_content(
                    model=item,
                    contents=history,
                    config = generate_content_config
                    )
                break
            except :
                continue
    elif thinking == False :
        for item in models :                                  # Si le premier modèle a atteint son quota, on passe au suivant
            try :
                response = client.models.generate_content(
                    model=item,
                    contents=history,
                    config = generate_content_config
                    )
                break
            except :
                continue
    elif thinking == True :
        for item in thinking_models :                                  # Si le premier modèle a atteint son quota, on passe au suivant
            try :
                response = client.models.generate_content(
                    model=item,
                    contents=history,
                    config = generate_content_config
                    )
                break
            except :
                continue
    if force_model != "" :
        response = client.models.generate_content(
                    model=force_model,
                    contents=history,
                    config = generate_content_config
                    )
    #print(response)
    print(response.model_version)
    return response
  

def split_text(text):
    parts = re.split(r'\n\s+', text)
    return parts

def num_tokens_from_messages(messages, model='gpt-4'):
    """A changer pour google, mais la limite de tokens est trop haute pour s'en soucier anyway"""
    """Returns the number of tokens used by a list of messages.
    Copied with minor changes from: https://platform.openai.com/docs/guides/chat/managing-tokens """
    try:
      encoding = tiktoken.encoding_for_model(model)
      num_tokens = 0
      for message in messages:
          num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
          for key, value in message.items():
              num_tokens += len(encoding.encode(value))
              if key == "name":  # if there's a name, the role is omitted
                  num_tokens += -1  # role is always required and always 1 token
      num_tokens += 2  # every reply is primed with <im_start>assistant
      return num_tokens
    except Exception:
      raise NotImplementedError(f"""num_tokens_from_messages() is not presently implemented for model {model}.
      #See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens.""")


class GoogleManager:
    
    def __init__(self):
        self.chat_history = [] # Stores the entire conversation


    # Asks a question with no chat history
    def chat(self, prompt="", system ="", thinking_mode = False, image = None, tools = [], tools_only = False, print_stuff = True, force_model = ""):
        if not prompt :
            print("Didn't receive input!")
            return

        # Should check that the prompt is under the token context limit, but right now skip that part
        '''
        if num_tokens_from_messages(chat_question) > 16000:
            print("The length of this chat question is too large for the llama model currently linked")
            return
        '''
        # Type message as is or add image if one is given.
        if image == None :
            chat_question = types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                ],
            )
        else :
            chat_question = []
            image_encoded = PIL.Image.open(image)
            #print(image_encoded)
            chat_question_text = types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                ],
            )
            chat_question.append(chat_question_text)
            chat_question.append(image_encoded)

        response = prompt_to_response(history = chat_question,system_prompt=system, thinking= thinking_mode, tools=tools, tools_only=tools_only, force_model=force_model)
        model_used = response.model_version
        if print_stuff :
            print("[yellow]\nAsking Google model a question...")
            print(f"[red]\n{model_used}\n")
        function_call_found = 99
        text_found = 99
        for i in range(len(response.candidates[0].content.parts)) :
            if response.candidates[0].content.parts[i].function_call :
                function_call_found = i
            else :
                text_found = i
        if (function_call_found != 99) and (text_found == 99)  : 
            response_part = response.candidates[0].content.parts[function_call_found]
            function_name = response_part.function_call.name
            function_args = response_part.function_call.args
            if print_stuff :
                print(f"[green]\nGoogle is calling function : {function_name}, with arguments : {function_args}\n")
            return function_name, function_args, response
        elif (function_call_found == 99) and (text_found != 99) :
            text = response.candidates[0].content.parts[text_found].text
            response_text = split_text(text)
            # Process the answer
            google_answer = " ".join([part.strip() for part in response_text])
            if print_stuff :
                print(f"[green]\n{google_answer}\n")
            return google_answer
        elif (function_call_found != 99) and (text_found != 99) :
            # This is when there is both text and a function call in the response
            text = response.candidates[0].content.parts[text_found].text
            response_text = split_text(text)
            # Process the answer
            google_answer = " ".join([part.strip() for part in response_text])
            if print_stuff :
                print(f"[green]\n{google_answer}\n")
            response_part = response.candidates[0].content.parts[function_call_found]
            function_name = response_part.function_call.name
            function_args = response_part.function_call.args
            if print_stuff :
                print(f"[green]\nGoogle is calling function : {function_name}, with arguments : {function_args}\n")
            return function_name, function_args, text, response
            

    # Asks a question that includes the full conversation history
    def chat_with_history(self, prompt="", system ="", thinking_mode = False, image = None, tools = [], existing_history = ''):
        if not prompt:
            print("Didn't receive input!")
            return
        # Load existing history if any
        if existing_history == '' :
            pass
        else : 
            exec("self.chat_history = list(" + existing_history + ")")
            pass
        # Add our prompt into the chat history
        if image == None :
            self.chat_history.append(types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                ],
            ))
            #print(self.chat_history)
        else :
            image_encoded = PIL.Image.open(image)
            #print(image_encoded)
            '''
            self.chat_history.append(types.Content(
                role="user",
                parts=[
                    image_encoded,
                    types.Part.from_text(text=prompt),
                ],
            ))
            '''
            #Placeholder parce que c'est pas censé marcher ce que je fais là
            #    
            self.chat_history.append(types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                ],
            ))
            self.chat_history.append(image_encoded)
        # Check total token limit. Remove old messages as needed
        '''
        print(f"[coral]Chat History has a current token length of {num_tokens_from_messages(self.chat_history)}")
        while num_tokens_from_messages(self.chat_history) > 16000:
            self.chat_history.pop(1) # We skip the 1st message since it's the system message
            print(f"Popped a message! New token length is: {num_tokens_from_messages(self.chat_history)}")
        '''
        print("[yellow]\nAsking Google model a question...")
        try :
            response = prompt_to_response(self.chat_history, system_prompt=system, thinking= thinking_mode, tools=tools)
            text = response.text
        except :
            response = prompt_to_response(self.chat_history, system_prompt=system, thinking= thinking_mode, tools=tools)[0]
            text = response.text
        response_text = split_text(text)
        google_answer = " ".join([part.strip() for part in response_text])
        model_used = response.model_version

        # Add this answer to our chat history
        self.chat_history.append(types.Content(
            role="model",
            parts=[
                types.Part.from_text(text=google_answer),
            ],
        ))

        # Process the answer
        print(f"[green]\n{google_answer}\n")
        print(f"[red]\n({model_used})\n")
        return google_answer


    # Generates an additional response based on existing content (example : follow-up after a tool was called)
    def follow_up(self, previous_content, new_content, prompt="", thinking_mode = False, print_stuff = True, force_model = ""):
        combined_content =[
            previous_content,
            new_content
        ]
        print(combined_content)
        response = prompt_to_response(history = combined_content, thinking= thinking_mode, force_model=force_model, tools=[])
        text = response.text
        response_text = split_text(text)
        # Process the answer
        google_answer = " ".join([part.strip() for part in response_text])
        if print_stuff :
            print(f"[green]\n{google_answer}\n")
        return google_answer
        
if __name__ == '__main__':
    google_manager = GoogleManager()

    # CHAT TEST
    chat_without_history = google_manager.chat("Hey Llama what is 2 + 2? But tell it to me as Yoda")

    # CHAT WITH HISTORY TEST
    '''
    SYSTEM_MESSAGE = "Act like you are Captain Jack Sparrow from the Pirates of Carribean movie series!"
    #FIRST_USER_MESSAGE = {"role": "user", "content": "Ahoy there! Who are you, and what are you doing in these parts? Please give me a 1 sentence background on how you got here. And do you have any mayonnaise I can borrow?"}
    #google_manager.chat_history.append(FIRST_USER_MESSAGE)
    google_manager.chat_with_history("Ahoy there! Who are you, and what are you doing in these parts? Please give me a 1 sentence background on how you got here. And do you have any mayonnaise I can borrow?", system=SYSTEM_MESSAGE)
    #print(google_manager.chat_history)'
    '''

    while True:
        new_prompt = input("\nNext question? \n\n")
        google_manager.chat_with_history(new_prompt)
        