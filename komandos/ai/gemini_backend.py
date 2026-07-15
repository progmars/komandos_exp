from google import genai
from google.genai import types

from ai.tools.tool_dispatcher import call_tool, format_tool_result, format_system_prompt_for_tools, \
                                      find_file_path_by_parts, open_file, open_directory, browser_search

# should be configurable if things get serious
MODEL_NAME = "gemini-2.5-pro" # "gemini-2.5-flash" # "gemini-3-pro-preview"

# don't go wild; this also includes thoughts
MAX_OUTPUT_TOKENS = 2000

# let's allow whatever user wishes
RELAXED_SAFETY_SETTINGS = [
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                        threshold=types.HarmBlockThreshold.OFF),
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                        threshold=types.HarmBlockThreshold.OFF),
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                        threshold=types.HarmBlockThreshold.OFF),
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                        threshold=types.HarmBlockThreshold.OFF),                                                                       
    ]

# some models throw error with "This model only works in thinking mode."
MANDATORY_THINK_BUDGET = 128

# should have common base class to support many AI backends
# if things get serious
class GeminiBackend:

    def __init__(self, settings, translator):
        api_key = settings.get_setting("gemini_key")
        self.api = genai.Client(api_key=api_key)
        """
            conversation.push({
            role: x.role.replace("assistant", "model"), // Google has "model" role
            parts: [{ text: x.content }] })));
        """
        self.chat_history = []
        self.translator = translator
        self.system_prompt = translator.t("assistant_system_prompt")
        self.error_text = translator.t("assistant_error")   
        self.tool_prompt = format_system_prompt_for_tools(self.system_prompt)
        
        config = self.create_config()

        # In the new google.genai SDK, we can pass Python functions directly
        config.tools = [browser_search, find_file_path_by_parts, open_file]

        self.chat = self.api.chats.create(                
                model=MODEL_NAME,
                config=config
            )


    def reset_history(self):
        self.chat_history.clear()


    def respond(self, user_speech):
        print(f"Sending to LLM: `{user_speech}`...")

        item = types.Content(role="user",          
                            parts=[ types.Part(text=user_speech) ])
        self.chat_history.append(item)

        iter_count = 0
        while True:
            iter_count += 1
            # do not want to exhaust all quotas in a loop
            if iter_count > 2:
                return ""
            
            (resp, tool_call) = self.generate()
            if not resp and not tool_call:
                return ""

            item = types.Content(role="model",          
                    parts=[ types.Part(text=resp) ])
            self.chat_history.append(item)

            if tool_call is not None:
                print(f"Had tool call, calling...")
                result = call_tool(tool_call)
                print(f"Tool call result: {result}")
                tool_resp = format_tool_result(result)
                item = types.Content(role="user",          
                        parts=[ types.Part(text=tool_resp) ])
                self.chat_history.append(item)
            else:
                print(f"Returning final response: {resp}")
                return resp


    def process(self, user_speech):     
        print(f"Sending to LLM: `{user_speech}`...")

        try:
            # chat mode deals with the function call loop automatically
            """
            The Python SDK supports automatic function calling,
              which automatically converts Python functions to declarations, 
              handles the function call execution and response cycle for you.
            """
            response = self.chat.send_message(user_speech)
            print(f"AI: {response.text}")
            
            if response.text is None:
                # Gemini failed, print all
                print("Gemini ERROR!")
                print(response)
                return self.error_text

            # extracting thoughts is a bit complex, needs " include_thoughts=True"
            # and manual looping because no direct access
            # anyway, good to learn how to extract the data
            response_text = ""
            response_thoughts = ""
            for part in response.candidates[0].content.parts:
                if part.thought:
                    response_thoughts += part.text
                else:
                    response_text += part.text

            print(f"AI thought: {response_thoughts}")
            return response_text
        except Exception as e:
            print(f"Error from Gemini: {e}")

        return None


    # for self-coded tool handling
    def generate(self):
        # print(f"Generating continuation for {self.chat_history}");
        contents = self.chat_history
        # print(self.tool_prompt)

        config = self.create_config()
        
        try:
            response = self.api.models.generate_content(model=MODEL_NAME, 
                                                        contents=contents,
                                                        config=config)
            if response.text is None:
                # Gemini failed, print all
                print("Gemini ERROR!")
                print(response)
                return self.error_text
        
            # print(response)
            # print(response.sdk_http_response)

            # extracting thoughts is a bit complex, needs " include_thoughts=True"
            # and manual looping because no direct access
            # anyway, good to learn how to extract the data
            response_text = ""
            response_thoughts = ""
            for part in response.candidates[0].content.parts:
                if part.thought:
                    response_thoughts += response_thoughts
                else:
                    response_text += part.text

            function_call = response.candidates[0].content.parts[0].function_call

            print(f"AI thought: {response_thoughts}")
            return (response_text, function_call)
        except Exception as e:
            print(f"Error from Gemini: {e}")

        return (None, None)


    def create_config(self):
        
        config = types.GenerateContentConfig(
            system_instruction=self.tool_prompt,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            safety_settings=RELAXED_SAFETY_SETTINGS,
            thinking_config=types.ThinkingConfig(
                include_thoughts=True,
                # thinking_level=types.ThinkingLevel.LOW, # for gemini 3
                # thinking_budget=0 # for Flash
                thinking_budget=MANDATORY_THINK_BUDGET # for gemini 2.5 where 0 not allowed
            )
            #temperature=0,
            #candidate_count=1,
            #response_mime_type="application/json",
            #top_p=0.95,
            #top_k=20,
            #seed=5,
            #stop_sequences=["STOP!"],
            #presence_penalty=0.0,
            #frequency_penalty=0.0,
        )

        return config