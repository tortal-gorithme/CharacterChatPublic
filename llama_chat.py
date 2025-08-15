import tiktoken
import requests, json, os, re
import codecs
from rich import print

#### LLama specific setup

ENDPOINT = "http://192.168.1.234:5001"
# ENDPOINT = "http://localhost:5001"

temperature_set = 1.0

def prompt_to_post(input_prompt):
  return {
        "prompt": "\n### Instruction:\n" + input_prompt + "\n### Response:\n",
        "n": 1,
        "max_context_length": 2048,
        "max_length": 222,
        "rep_pen": 1.1,
        "rep_pen_range": 320,
        "rep_pen_slope": 0.7,
        "temperature": temperature_set,
        "tfs": 1,
        "top_a": 0,
        "top_k": 100,
        "top_p": 0.92,
        "typical": 1,
        "sampler_order": [6, 0, 1, 2, 3, 4, 5],
        "singleline": False, 
        "frmttriminc": True,
        "frmtrmblln": False,
        "min_p": 0,
        "quiet": True,
        "stop_sequence": ["### Instruction:", "### Response:"],
        "use_default_badwordsids": False
    }

def split_text(text):
  parts = re.split(r'\n\s+', text)
  return parts


def gpt_like_completion(base) :
  #print(base)
  text_result = ""
  for i in base :
    #print(i)
    role = ""
    if i['role'] == 'user' :
      role = "### Instruction:"
    elif i['role'] == 'assistant' or i['role'] == 'Assistant' :
      role = "### Response:"
    prompt = i['content']
    text_result = text_result + role + prompt + "\n"
  response = requests.post(f"{ENDPOINT}/api/v1/generate", json=prompt_to_post(text_result))
  if response.status_code == 200:
      results = response.json()['results']
      text = results[0]['text']
      response_text = split_text(text)
  llama_answer = " ".join([part.strip() for part in response_text])
  return llama_answer



def num_tokens_from_messages(messages, model='gpt-4'):
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


class LlamaManager:
    
    def __init__(self):
        self.chat_history = [] # Stores the entire conversation
        try:
            self.ENDPOINT = "http://192.168.1.234:5001"
        except TypeError:
            exit("Ooops! You forgot to set the ENDPOINT for the llama API in your environment!")


    # Asks a question with no chat history
    def chat(self, prompt=""):
        if not prompt:
            print("Didn't receive input!")
            return

        # Check that the prompt is under the token context limit
        chat_question = [{"role": "user", "content": prompt}]
        if num_tokens_from_messages(chat_question) > 2000:
            print("The length of this chat question is too large for the llama model currently linked")
            return

        print("[yellow]\nAsking Llama a question...")
        response = requests.post(f"{ENDPOINT}/api/v1/generate", json=prompt_to_post(prompt))
        if response.status_code == 200:
            results = response.json()['results']
            text = results[0]['text']
            response_text = split_text(text)


        # Process the answer
        llama_answer = " ".join([part.strip() for part in response_text])
        print(f"[green]\n{llama_answer}\n")
        return llama_answer

    # Asks a question that includes the full conversation history
    def chat_with_history(self, prompt=""):
        if not prompt:
            print("Didn't receive input!")
            return

        # Add our prompt into the chat history
        self.chat_history.append({"role": "user", "content": prompt})

        # Check total token limit. Remove old messages as needed
        print(f"[coral]Chat History has a current token length of {num_tokens_from_messages(self.chat_history)}")
        while num_tokens_from_messages(self.chat_history) > 2000:
            self.chat_history.pop(1) # We skip the 1st message since it's the system message
            print(f"Popped a message! New token length is: {num_tokens_from_messages(self.chat_history)}")

        print("[yellow]\nAsking Llama a question...")
        #response = requests.post(f"{ENDPOINT}/api/v1/generate", json=prompt_to_post(self.chat_history))
        #if response.status_code == 200:
        #    results = response.json()['results']
        #    text = results[0]['text']
        #    response_text = split_text(text)

        #llama_answer = " ".join([part.strip() for part in response_text])

        llama_answer = gpt_like_completion(self.chat_history)

        # Add this answer to our chat history
        self.chat_history.append({"role": "Assistant", "content": llama_answer})

        # Process the answer
        print(f"[green]\n{llama_answer}\n")
        return llama_answer
   

if __name__ == '__main__':
    llama_manager = LlamaManager()

    # CHAT TEST
    chat_without_history = llama_manager.chat("Hey Llama what is 2 + 2? But tell it to me as Yoda")

    # CHAT WITH HISTORY TEST
    FIRST_SYSTEM_MESSAGE = {"role": "system", "content": "Act like you are Captain Jack Sparrow from the Pirates of Carribean movie series!"}
    FIRST_USER_MESSAGE = {"role": "user", "content": "Ahoy there! Who are you, and what are you doing in these parts? Please give me a 1 sentence background on how you got here. And do you have any mayonnaise I can borrow?"}
    llama_manager.chat_history.append(FIRST_SYSTEM_MESSAGE)
    llama_manager.chat_history.append(FIRST_USER_MESSAGE)

    while True:
        new_prompt = input("\nNext question? \n\n")
        llama_manager.chat_with_history(new_prompt)
        