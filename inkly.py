#!/bin/env python3
import sys


LOG_FILE = "inkly.log"

def squeue() -> str:
    import subprocess

    # Run the squeue command and capture its output
    result = subprocess.run(['squeue', '-u', 'your_username'], stdout=subprocess.PIPE)

    # Decode the output from bytes to string
    output = result.stdout.decode('utf-8')

    # Print the output
    # print(output)
    return output


def chat_with_copilot(user_input: str) -> str:
    # Use subprocess to call our local github copilot CLI
    import subprocess
    result = subprocess.run(['copilot', '-p', user_input], stdout=subprocess.PIPE)
    output = result.stdout.decode('utf-8')
    return output



if __name__ == "__main__":
    # print("hello world")
    # Read the input from the user
    text = " ".join(sys.argv[1:])

    # Log the user input
    print(f"User input: {text}", file=open(LOG_FILE, "a"))
    
    # Grab information from the system
    squeue_output = squeue()

    # Combine the user input with the system information
    combined_text = f"{text}\n\nCurrent squeue output:\n{squeue_output}"

    # Now call copilot with the combined text
    copilot_response = chat_with_copilot(combined_text)

    # Log the copilot response
    print(f"Copilot response: {copilot_response}", file=open(LOG_FILE, "a"))

    # Print the copilot response to the user
    print(copilot_response)