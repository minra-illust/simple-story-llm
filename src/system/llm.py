from openai import OpenAI
import json
import threading
import google.generativeai as genai
import time
from colorama import Fore, Style
import re
import os
from pathlib import Path

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
models = [
    {
        "id": "deepseek-reasoner",
        "client": OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com"),
        "type": "openai",
        "stream": True,
        "stream_delta_format": "json_content_reasoning"
    },
    {
        "id": "deepseek-chat",
        "client": OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com"),
        "type": "openai",
        "stream": False
    },
    {
        "id": "deepseek-chat",
        "client": OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com"),
        "type": "openai",
        "stream": False,
    }
]

def llm_call(local_messages, currentModel=0, log_filename='_last_llm_call.log', result_log_filename='_last_llm_call_result.log', system_prompt=''):
    global models
    
    # Add system prompt to messages if provided
    if system_prompt:
        system_message = {"role": "system", "content": system_prompt}
        local_messages = [system_message] + local_messages
    
    try:
        with open(log_filename, 'w', encoding='utf-8') as f:
            # Log all messages with their roles
            for message in local_messages:
                f.write(f"[{message['role'].upper()}]\n")
                f.write(message['content'])
                f.write("\n\n" + "="*80 + "\n\n")
    except Exception as e:
        print(Fore.RED + f"Error writing message log: {e}" + Style.RESET_ALL)
    if currentModel < 0 or currentModel >= len(models):
        print(Fore.RED + f"Error: Invalid model index {currentModel}" + Style.RESET_ALL)
        return None
    model_config = models[currentModel]
    model_type = model_config.get("type", "openai")
    retrying = True
    content = ""
    reasoning_content = ""
    done = False
    max_retries = 3
    retry_count = 0
    while retrying and retry_count < max_retries:
        print(f"--... llm call ({retry_count + 1})...--")
        content = ""
        reasoning_content = ""
        done = False
        try:
            if model_type == "openai":
                if not model_config.get("client"):
                    print(Fore.RED + f"Error: OpenAI client not configured for model {model_config['id']}" + Style.RESET_ALL)
                    return None
                # Prepare request parameters based on model type
                request_params = {
                    "model": model_config["id"],
                    "messages": local_messages,
                    "stream": model_config["stream"],
                    "temperature": 1,
                    "frequency_penalty": 0,
                    "presence_penalty": 0,
                    "max_tokens": 8192,
                }
                
                # Add deepseek-chat specific parameters
                if model_config["id"] == "deepseek-chat":
                    request_params.update({
                        "frequency_penalty": 0,
                        "presence_penalty": 0,
                        "max_tokens": 8192,
                        "response_format": {"type": "text"},
                        "stop": None,
                        "stream_options": None,
                        "top_p": 1,
                        "tools": None,
                        "tool_choice": "none",
                        "logprobs": False,
                        "top_logprobs": None
                    })
                    
                if currentModel == 2:
                    request_params.update({
                        "temperature": 1.4,
                        "presence_penalty": 1,
                    })
                
                response = model_config["client"].chat.completions.create(**request_params)
                if not model_config["stream"]:
                    raw_content = response.choices[0].message.content
                    thinking_token = model_config.get("thinking_token_end")
                    if thinking_token and thinking_token in raw_content:
                        try:
                            reasoning_content = raw_content.split(thinking_token)[0] + thinking_token
                            content = raw_content.split(thinking_token)[1]
                        except IndexError:
                            content = raw_content
                            reasoning_content = ""
                            print(Fore.YELLOW + "Warning: thinking_token found but split failed." + Style.RESET_ALL)
                    else:
                        content = raw_content
                    # Write entire raw response to result log
                    try:
                        with open(result_log_filename, 'w', encoding='utf-8') as f:
                            f.write(raw_content)
                    except Exception as e:
                        print(Fore.RED + f"Error writing result log: {e}" + Style.RESET_ALL)
                    retrying = False
                    done = True
                else:
                    stream_response_ref = [response]
                    def observer(callback, timeout=99999):
                        nonlocal retrying, done, reasoning_content, content
                        start_time = time.time()
                        while not done:
                            if time.time() - start_time >= timeout and not content and not reasoning_content:
                                print(Fore.YELLOW + f"\nTimeout ({timeout}s) waiting for stream start. Retrying..." + Style.RESET_ALL)
                                callback()
                                return
                            if done:
                                retrying = False
                                return
                            time.sleep(0.5)
                    def cancel_processing():
                        nonlocal stream_response_ref, retrying, done
                        try:
                            if not done and stream_response_ref[0] and hasattr(stream_response_ref[0], 'close'):
                                print(Fore.YELLOW + "(Closing stream and retrying)" + Style.RESET_ALL, flush=True)
                                stream_response_ref[0].close()
                        except Exception as e:
                            print(Fore.RED + f"Error closing stream: {e}" + Style.RESET_ALL)
                    def process_chunks(stream_response):
                        nonlocal content, reasoning_content, done, model_config
                        word_count = 0
                        reasoning_word_count = 0
                        stream_delta_format = model_config.get("stream_delta_format")
                        thinking_token = model_config.get("thinking_token_end")
                        # Open result log for streaming
                        log_file = None
                        try:
                            log_file = open(result_log_filename, 'w', encoding='utf-8')
                        except Exception as e:
                            print(Fore.RED + f"Error opening result log for streaming: {e}" + Style.RESET_ALL)
                            log_file = None
                        try:
                            for chunk in stream_response:
                                delta_content_text = None
                                delta_reasoning_text = None
                                if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta:
                                    delta = chunk.choices[0].delta
                                    if stream_delta_format == "json_content_reasoning":
                                        delta_content_text = getattr(delta, 'content', None)
                                        delta_reasoning_text = getattr(delta, 'reasoning_content', None)
                                        if delta_reasoning_text:
                                            # Write thinking start tag if this is the first reasoning content
                                            if not reasoning_content and log_file:
                                                log_file.write("<thinking_start>\n")
                                                log_file.flush()
                                            reasoning_content += delta_reasoning_text
                                            reasoning_word_count += len(delta_reasoning_text.split())
                                            if log_file:
                                                log_file.write(delta_reasoning_text)
                                                log_file.flush()
                                    else:
                                        delta_content_text = delta.content
                                        if delta_content_text:
                                            raw_content_accumulator = reasoning_content + content + delta_content_text
                                            if thinking_token and thinking_token in raw_content_accumulator:
                                                if not content and thinking_token in (reasoning_content + delta_content_text):
                                                    parts = (reasoning_content + delta_content_text).split(thinking_token, 1)
                                                    reasoning_content = parts[0] + thinking_token
                                                    delta_content_text = parts[1]
                                                    reasoning_word_count = len(reasoning_content.split())
                                                    # Write thinking end tag when we encounter the thinking token
                                                    if log_file and delta_content_text:
                                                        log_file.write("\n<thinking_end>\n")
                                                        log_file.flush()
                                            if thinking_token and not content:
                                                # Write thinking start tag if this is the first reasoning content
                                                if not reasoning_content and log_file:
                                                    log_file.write("<thinking_start>\n")
                                                    log_file.flush()
                                                reasoning_content += delta_content_text
                                                reasoning_word_count += len(delta_content_text.split())
                                                if log_file:
                                                    log_file.write(delta_content_text)
                                                    log_file.flush()
                                                delta_content_text = None
                                    if delta_content_text:
                                        # Write thinking end tag if this is the first content after reasoning
                                        if not content and reasoning_content and log_file:
                                            log_file.write("\n<thinking_end>\n")
                                            log_file.flush()
                                        content += delta_content_text
                                        word_count += len(delta_content_text.split())
                                        if log_file:
                                            log_file.write(delta_content_text)
                                            log_file.flush()
                        except Exception as e:
                            print(Fore.RED + f"\nError during stream processing: {e}" + Style.RESET_ALL)
                            return
                        finally:
                            if log_file:
                                log_file.close()
                        done = True
                    observer_thread = threading.Thread(target=observer, args=(cancel_processing,))
                    observer_thread.start()
                    process_thread = threading.Thread(target=process_chunks, args=(stream_response_ref[0],))
                    process_thread.start()
                    process_thread.join()
                    if not done:
                        print(Fore.YELLOW + "Warning: Process thread finished but 'done' flag not set. Setting manually." + Style.RESET_ALL)
                        done = True
                    observer_thread.join()
            else:
                print(Fore.RED + f"Error: Unknown model type '{model_type}' for model {model_config['id']}" + Style.RESET_ALL)
                retrying = False
                retry_count = max_retries
                return None
        except Exception as e:
            print(Fore.RED + f"An unexpected error occurred during API call or processing: {e}" + Style.RESET_ALL)
        if not done:
            retry_count += 1
            if retry_count < max_retries:
                print(Fore.YELLOW + f"-- Retrying ({retry_count}/{max_retries})... --" + Style.RESET_ALL)
                time.sleep(2)
            else:
                print(Fore.RED + "-- Max retries reached. Failing call. --" + Style.RESET_ALL)
                retrying = False
                return None
        else:
            retrying = False
    if content:
        content = content.replace('**', '*')
        content = content.replace('“', '"')
        content = content.replace('”', '"')
        content = content.strip()
    else:
        content = ""
    
    # Debug: if content contains tags with spaces, warn about it
    if content and ('<| ' in content or ' |>' in content):
        print(Fore.YELLOW + "Warning: LLM response contains tags with spaces which may cause parsing issues." + Style.RESET_ALL)
    
    return content
