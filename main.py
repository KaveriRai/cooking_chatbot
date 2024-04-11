import openai
import os
from dotenv import find_dotenv, load_dotenv
import time
import logging
from datetime import datetime
import requests
import json
import streamlit as st

load_dotenv()

edamam_api_key = os.environ.get("EDAMAM_API_KEY")
edamam_app_id = os.environ.get("EDAMAM_APP_ID")
news_api_key = os.environ.get("NEWS_API_KEY")
spoonacular_api_key = os.environ.get("SPOONACULAR_API_KEY")


# client calls openAI api, assistant, etc
client = openai.OpenAI()
model = "gpt-3.5-turbo-16k"

def get_help(topic):
    url = (
        f"https://newsapi.org/v2/everything?q={topic}&apiKey={news_api_key}&pageSize=5"
    )
    # url = (
    #     f"https://api.edamam.com/search?q={topic}&app_id={edamam_app_id}&app_key={edamam_api_key}"
    # )
    # url = "https://api.spoonacular.com/food/converse"
    # params = {
    #     "apiKey": spoonacular_api_key,
    #     "text": topic
    # }

    # try:
    #     response = requests.get(url, params=params)
    try:
        response = requests.get(url)
        print(response)
        if response.status_code == 200:
            answer = json.dumps(response.json(), indent = 4)
            answer_json = json.loads(answer)
            data = answer_json
            # return data
            status = data["status"]
            total_results = data["totalResults"]
            articles = data["articles"]
            final = []
            for article in articles:
                source = article["source"]["name"]
                author = article["author"]
                title = article["title"]
                description = article["description"]
                url = article["url"]
                content = article["content"]
                title_desc = f"""
                    Title: {title},
                    Author: {author},
                    Description: {description},
                    URL: {url}
                """
                final.append(title_desc)

            return final

        else:
            return []


    except requests.exceptions.RequestException as e:
        print("Error occured during api request", e)



class AssistantManager:
    thread_id = "thread_Lec674a0pxbbog14ewQ2Qnce"
    assistant_id = "asst_L8yuexscFu8CsfwuYizYyPUG"

    def __init__(self, model: str = model):
        self.client = openai.OpenAI()
        self.model = model
        self.assistant = None
        self.thread = None
        self.run = None
        self.summary = None


        # retrieve existing assistant and threads ids if present
        if AssistantManager.assistant_id:
            self.assistant = self.client.beta.assistants.retrieve(
                assistant_id=AssistantManager.assistant_id
            )
        if AssistantManager.thread_id:
            self.thread = self.client.beta.threads.retrieve(
                thread_id=AssistantManager.thread_id
            )

    def create_assistant(self, name, instructions, tools):
        if not self.assistant:
            assistant_obj = self.client.beta.assistants.create(
                name=name,
                instructions=instructions,
                tools=tools,
                model=self.model
            )

            AssistantManager.assistant_id = assistant_obj.id
            self.assistant = assistant_obj
            print(f"Assis id: {self.assistant.id}")

    def create_thread(self):
        if not self.thread:
            thread_obj = self.client.beta.threads.create()

            AssistantManager.thread_id = thread_obj.id
            self.thread = thread_obj
            print(f"Thread id: {self.thread.id}")

    def add_message_to_thread(self, role, content):
        if self.thread:
            self.client.beta.threads.messages.create(
                thread_id=self.thread.id,
                role=role,
                content=content
            )

    def run_assistant(self, instructions):
        if self.thread and self.assistant:
            self.run = self.client.beta.threads.runs.create(
                thread_id=self.thread.id,
                assistant_id=self.assistant.id,
                instructions=instructions,
            )

    def process_messages(self):
        if self.thread:
            messages = self.client.beta.threads.messages.list(
                thread_id = self.thread.id,
            )
            summary = []
            last_message = messages.data[0]
            role = last_message.role
            response = last_message.content[0].text.value
            summary.append(response)

            self.summary = "\n".join(summary)
            print(f"summary ----> {role.capitalize()}: => {response}")

            # for msg in messages:
            #     role = msg.role
            #     content = msg.content[0].text.value
            #     print(f"summary ----> {role.capitalize()}: => {content}")

        # return summary

    def call_required_functions(self, required_actions):
        if not self.run:
            return
        tools_outputs = []

        for act in required_actions["tool_calls"]:
            func_name = act["function"]["name"]
            arguments = json.loads(act["function"]["arguments"])

            if func_name == "get_help":
                # get_help(topic)
                output = get_help(topic=arguments["topic"])
                print(f"STUFFF;;{output}")
                final_str = ""
                for item in output:
                    final_str += "".join(item)

                tools_outputs.append({"tool_call_id": act["id"],
                                      "output": final_str})

            else:
                raise ValueError(f"Unknown func: :{func_name}")

            print(f"Sumbmitting outputs back to assistant..")
            self.client.beta.threads.runs.submit_tool_outputs(

                thread_id=self.thread.id,
                run_id=self.run.id,
                tool_outputs=tools_outputs
            )

    # STREAMLIT
    def get_summary(self):
        return self.summary

    def wait_for_completion(self):
        if self.thread and self.run:
            while True:
                time.sleep(5)
                run_status = self.client.beta.threads.runs.retrieve(
                    thread_id=self.thread.id,
                    run_id=self.run.id
                )
                print(f"RUN STATUS ----> {run_status.model_dump_json(indent=4)}")

                if run_status.status == "completed":
                    self.process_messages()
                    break

                elif run_status.status == "requires_action":
                    print(f"FUNCTION CALLING NOW....")
                    self.call_required_functions(required_actions=run_status.required_action.submit_tool_outputs.model_dump())

    # Run steps
    def run_steps(self):
        run_steps = self.client.beta.threads.runs.steps.list(
            thread_id=self.thread.id,
            run_id=self.run.id
        )
        print(f"Run-Steps::: {run_steps}")
        return run_steps.data


def main():
    # ans = get_help("bitcoin")
    # # ans = get_help("how to thicken my curry")
    # print(ans)
    manager = AssistantManager()

    # Create streamlit ui
    st.title("News Summarizer")

    with st.form(key="user_input_form"):
        instructions = st.text_input("Enter topic")
        submit_btn = st.form_submit_button(label="Run Assistant")

        if submit_btn:
            manager.create_assistant(
                name="News Summarizer",
                instructions="You are a personal article summarizer Assistant who knows how to take a list of article's titles and descriptions and then write a short summary of all the news articles",
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "get_help",
                            "description": "Get the list of articles/news for the given topic",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "topic": {
                                        "type": "string",
                                        "description": "The topic for the news, e.g. bitcoin",
                                    }
                                },
                                "required": ["topic"],
                            },
                        },
                    }
                ],
            )
            manager.create_thread()

            # Add message and run assistant
            manager.add_message_to_thread(
                role="user", content=f"summarize the news on this topic {instructions}?"
            )
            manager.run_assistant(instructions="Summarize the news")

            # Wait for completions and process messages
            manager.wait_for_completion()

            summary = manager.get_summary()

            st.write(summary)

            st.text("Run Steps:")
            st.code(manager.run_steps(), line_numbers=True)


if __name__ == "__main__":
    main()