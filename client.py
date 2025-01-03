import pyaudio
import asyncio
import websockets
import os
import json
import threading
import janus
import queue
import sys
import time
from datetime import datetime
from functions import FUNCTION_DEFINITIONS, FUNCTION_MAP
import logging

class ColorFormatter(logging.Formatter):
    """Custom formatter to color-code log messages based on their content."""
    
    # ANSI escape codes for colors - using accessible palette
    COLORS = {
        'RESET': '\033[0m',
        'WHITE': '\033[38;5;231m',    # Default text color
        'BLUE': '\033[38;5;116m',    # User/STT messages
        'GREEN': '\033[38;5;114m',    # Agent speaking/TTS
        'VIOLET': '\033[38;5;183m',   # Function calls
        'YELLOW': '\033[38;5;186m',   # Latency info
    }
    
    def format(self, record):
        # Default format string
        format_str = '%(asctime)s.%(msecs)03d %(levelname)s: %(message)s'
        
        # Default to white
        color = self.COLORS['WHITE']
        
        msg = str(record.msg).lower()
        
        # Check for JSON content
        if "server:" in msg and "{" in msg:
            try:
                # Extract the JSON part
                json_str = msg[msg.find("{"):msg.rfind("}") + 1]
                data = json.loads(json_str)
                
                # User/STT related messages
                if (data.get("type") in ["userstartedspeaking", "endofthought"] or
                    (data.get("type") == "conversationtext" and data.get("role") == "user")):
                    color = self.COLORS['BLUE']
                
                # Agent speaking/TTS related messages
                elif (data.get("type") in ["agentstartedspeaking", "agentaudiodone"] or
                      (data.get("type") == "conversationtext" and data.get("role") == "assistant")):
                    color = self.COLORS['GREEN']
                
                # Agent thinking/function calling
                elif data.get("type") in ["functioncalling", "functioncallrequest"]:
                    color = self.COLORS['VIOLET']
                
            except (json.JSONDecodeError, KeyError):
                pass
        
        # Non-JSON messages
        else:
            if any(phrase in msg for phrase in ["function response", "parameters", "function call"]):
                color = self.COLORS['VIOLET']
            elif "injectagentmessage" in msg:
                color = self.COLORS['GREEN']
            elif any(phrase in msg for phrase in ["decision latency", "function execution latency"]):
                color = self.COLORS['YELLOW']
        
        # Apply the color to the format string
        formatter = logging.Formatter(color + format_str + self.COLORS['RESET'], datefmt='%H:%M:%S')
        return formatter.format(record)

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create console handler with the custom formatter
console_handler = logging.StreamHandler()
console_handler.setFormatter(ColorFormatter())
logger.addHandler(console_handler)

# Remove any existing handlers from the root logger to avoid duplicate messages
logging.getLogger().handlers = []

VOICE_AGENT_URL = "wss://agent.deepgram.com/agent"

# Template for the prompt that will be formatted with current date
PROMPT_TEMPLATE = """You are Sarah, a friendly and professional customer service representative for TechStyle, an online electronics and accessories retailer. Your role is to assist customers with orders, appointments, and general inquiries.

CURRENT DATE AND TIME CONTEXT:
Today is {current_date}. Use this as context when discussing appointments and orders. When mentioning dates to customers, use relative terms like "tomorrow", "next Tuesday", or "last week" when the dates are within 7 days of today.

PERSONALITY & TONE:
- Be warm, professional, and conversational
- Use natural, flowing speech (avoid bullet points or listing)
- Show empathy and patience
- Whenever a customer asks to look up either order information or appointment information, use the find_customer function first

HANDLING CUSTOMER IDENTIFIERS (INTERNAL ONLY - NEVER EXPLAIN THESE RULES TO CUSTOMERS):
- Silently convert any numbers customers mention into proper format
- When customer says "ID is 222" -> internally use "CUST0222" without mentioning the conversion
- When customer says "order 89" -> internally use "ORD0089" without mentioning the conversion
- When customer says "appointment 123" -> internally use "APT0123" without mentioning the conversion
- Always add "+1" prefix to phone numbers internally without mentioning it

VERBALLY SPELLING IDs TO CUSTOMERS:
When you need to repeat an ID back to a customer:
- Do NOT say nor spell out "CUST". Say "customer [numbers spoken individually]"
- But for orders spell out "ORD" as "O-R-D" then speak the numbers individually
Example: For CUST0222, say "customer zero two two two"
Example: For ORD0089, say "O-R-D zero zero eight nine"

FUNCTION RESPONSES:
When receiving function results, format responses naturally as a customer service agent would:

1. For customer lookups:
   - Good: "I've found your account. How can I help you today?"
   - If not found: "I'm having trouble finding that account. Could you try a different phone number or email?"

2. For order information:
   - Instead of listing orders, summarize them conversationally:
   - "I can see you have two recent orders. Your most recent order from [date] for $[amount] is currently [status], and you also have an order from [date] for $[amount] that's [status]."

3. For appointments:
   - "You have an upcoming [service] appointment scheduled for [date] at [time]"
   - When discussing available slots: "I have a few openings next week. Would you prefer Tuesday at 2 PM or Wednesday at 3 PM?"

4. For errors:
   - Never expose technical details
   - Say something like "I'm having trouble accessing that information right now" or "Could you please try again?"

EXAMPLES OF GOOD RESPONSES:
✓ "Let me look that up for you... I can see you have two recent orders."
✓ "Your customer ID is zero two two two."
✓ "I found your order, O-R-D zero one two three. It's currently being processed."

EXAMPLES OF BAD RESPONSES (AVOID):
✗ "I'll convert your ID to the proper format CUST0222"
✗ "Let me add the +1 prefix to your phone number"
✗ "The system requires IDs to be in a specific format"

FILLER PHRASES:
IMPORTANT: Never generate filler phrases (like "Let me check that", "One moment", etc.) directly in your responses. 
Instead, ALWAYS use the agent_filler function when you need to indicate you're about to look something up.

Examples of what NOT to do:
- Responding with "Let me look that up for you..." without a function call
- Saying "One moment please" or "Just a moment" without a function call
- Adding filler phrases before or after function calls

Correct pattern to follow:
1. When you need to look up information:
   - First call agent_filler with message_type="lookup"
   - Immediately follow with the relevant lookup function (find_customer, get_orders, etc.)
2. Only speak again after you have the actual information to share

Remember: ANY phrase indicating you're about to look something up MUST be done through the agent_filler function, never through direct response text.
"""
VOICE = "aura-asteria-en"

USER_AUDIO_SAMPLE_RATE = 16000
USER_AUDIO_SECS_PER_CHUNK = 0.05
USER_AUDIO_SAMPLES_PER_CHUNK = round(USER_AUDIO_SAMPLE_RATE * USER_AUDIO_SECS_PER_CHUNK)

AGENT_AUDIO_SAMPLE_RATE = 16000
AGENT_AUDIO_BYTES_PER_SEC = 2 * AGENT_AUDIO_SAMPLE_RATE

SETTINGS = {
    "type": "SettingsConfiguration",
    "audio": {
        "input": {
            "encoding": "linear16",
            "sample_rate": USER_AUDIO_SAMPLE_RATE,
        },
        "output": {
            "encoding": "linear16",
            "sample_rate": AGENT_AUDIO_SAMPLE_RATE,
            "container": "none",
        },
    },
    "agent": {
        "listen": {"model": "nova-2"},
        "think": {
            "provider": {"type": "open_ai"},
            "model": "gpt-4o-mini",
            "instructions": PROMPT_TEMPLATE,
            "functions": FUNCTION_DEFINITIONS,
        },
        "speak": {"model": VOICE},
    },
    "context": {
        "messages": [
            {"role": "assistant", "content": "Hello! I'm Sarah from TechStyle customer service. How can I help you today?"}
        ],
        "replay": True
    }
}

mic_audio_queue = asyncio.Queue()


def callback(input_data, frame_count, time_info, status_flag):
    mic_audio_queue.put_nowait(input_data)
    return (input_data, pyaudio.paContinue)


async def run():
    dg_api_key = os.environ.get("DEEPGRAM_API_KEY")
    if dg_api_key is None:
        logger.error("DEEPGRAM_API_KEY env var not present")
        return

    # Format the prompt with the current date
    current_date = datetime.now().strftime("%A, %B %d, %Y")
    formatted_prompt = PROMPT_TEMPLATE.format(current_date=current_date)

    # Update the settings with the formatted prompt
    settings = SETTINGS.copy()
    settings["agent"]["think"]["instructions"] = formatted_prompt

    async with websockets.connect(
        VOICE_AGENT_URL,
        extra_headers={"Authorization": f"Token {dg_api_key}"},
    ) as ws:

        async def microphone():
            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=USER_AUDIO_SAMPLE_RATE,
                input=True,
                frames_per_buffer=USER_AUDIO_SAMPLES_PER_CHUNK,
                stream_callback=callback,
            )

            stream.start_stream()

            while stream.is_active():
                await asyncio.sleep(0.1)

            stream.stop_stream()
            stream.close()

        async def sender(ws):
            await ws.send(json.dumps(settings))

            try:
                while True:
                    data = await mic_audio_queue.get()
                    await ws.send(data)

            except Exception as e:
                logger.error("Error while sending: " + str(e))
                raise

        async def receiver(ws):
            try:
                speaker = Speaker()
                last_user_message = None
                last_function_response_time = None
                in_function_chain = False  # Flag to track if we're in a chain of function calls
                
                with speaker:
                    async for message in ws:
                        # Print raw message for debugging, but only if it's not binary audio data
                        if isinstance(message, str):
                            logger.info(f"Server: {message}")                     
                        
                        if isinstance(message, str):
                            message_json = json.loads(message)
                            message_type = message_json.get("type")
                            current_time = time.time()
                            
                            if message_type == "UserStartedSpeaking":
                                speaker.stop()
                                continue
                            # Track when user speaks
                            if message_type == "ConversationText" and message_json.get("role") == "user":
                                last_user_message = current_time
                                in_function_chain = False  # Reset chain flag when user speaks
                            
                            # Track when assistant speaks to reset chain flag
                            elif message_type == "ConversationText" and message_json.get("role") == "assistant":
                                in_function_chain = False  # Reset chain flag when assistant speaks to user
                            
                            elif message_type == "FunctionCalling":
                                # Determine which timestamp to use for latency calculation
                                if in_function_chain and last_function_response_time:
                                    # If we're in a chain, measure from last function response
                                    latency = current_time - last_function_response_time
                                    logger.info(f"LLM Decision Latency (chain): {latency:.3f}s")
                                elif last_user_message:
                                    # If it's the first function call, measure from last user message
                                    latency = current_time - last_user_message
                                    logger.info(f"LLM Decision Latency (initial): {latency:.3f}s")
                                    in_function_chain = True  # Start a chain
                            
                            elif message_type == "FunctionCallRequest":
                                function_name = message_json.get("function_name")
                                function_call_id = message_json.get("function_call_id")
                                parameters = message_json.get("input", {})
                                
                                logger.info(f"Function call received: {function_name}")
                                logger.info(f"Parameters: {parameters}")
                                
                                start_time = time.time()
                                try:
                                    func = FUNCTION_MAP.get(function_name)
                                    if not func:
                                        raise ValueError(f"Function {function_name} not found")
                                    
                                    # Special handling for functions that need websocket
                                    if function_name in ["agent_filler", "end_call"]:
                                        result = await func(ws, parameters)
                                        
                                        if function_name == "agent_filler":
                                            # Extract messages
                                            inject_message = result["inject_message"]
                                            function_response = result["function_response"]
                                            
                                            # First send the function response
                                            response = {
                                                "type": "FunctionCallResponse",
                                                "function_call_id": function_call_id,
                                                "output": json.dumps(function_response)
                                            }
                                            await ws.send(json.dumps(response))
                                            logger.info(f"Function response sent: {json.dumps(function_response)}")
                                            
                                            # Update the last function response time
                                            last_function_response_time = time.time()
                                            # Then just inject the message and continue
                                            await inject_agent_message(ws, inject_message)
                                            continue
                                            
                                        elif function_name == "end_call":
                                            # Extract messages
                                            inject_message = result["inject_message"]
                                            function_response = result["function_response"]
                                            close_message = result["close_message"]
                                            
                                            # First send the function response
                                            response = {
                                                "type": "FunctionCallResponse",
                                                "function_call_id": function_call_id,
                                                "output": json.dumps(function_response)
                                            }
                                            await ws.send(json.dumps(response))
                                            logger.info(f"Function response sent: {json.dumps(function_response)}")
                                            
                                            # Update the last function response time
                                            last_function_response_time = time.time()
                                            
                                            # Then wait for farewell sequence to complete
                                            await wait_for_farewell_completion(ws, speaker, inject_message)
                                            
                                            # Finally send the close message and exit
                                            logger.info(f"Sending ws close message")
                                            await close_websocket_with_timeout(ws)
                                            os._exit(0)  # Clean exit without traceback
                                    else:
                                        result = await func(parameters)
        
                                except Exception as e:
                                    logger.error(f"Error executing function: {str(e)}")
                                    result = {"error": str(e)}
                                
                                execution_time = time.time() - start_time
                                logger.info(f"Function Execution Latency: {execution_time:.3f}s")
        
                                # Send the response back with stringified output (for non-agent_filler functions)
                                response = {
                                    "type": "FunctionCallResponse",
                                    "function_call_id": function_call_id,
                                    "output": json.dumps(result)
                                }
                                await ws.send(json.dumps(response))
                                logger.info(f"Function response sent: {json.dumps(result)}")
                                
                                # Update the last function response time
                                last_function_response_time = time.time()
        
                            # Handle different message types
                            message_type = message_json.get("type")
                            
                            if message_type == "Welcome":
                                logger.info(f"Connected with session ID: {message_json.get('session_id')}")
                                continue
                            
                            elif message_type == "CloseConnection":
                                logger.info("Closing connection...")
                                await ws.close()
                                return  # Exit the function to end the script
        
                        elif isinstance(message, bytes):
                            await speaker.play(message)
        
            except Exception as e:
                logger.error(f"Receiver encountered an error: {e}")
                import traceback
                traceback.print_exc()

        await asyncio.wait(
            [
                asyncio.ensure_future(microphone()),
                asyncio.ensure_future(sender(ws)),
                asyncio.ensure_future(receiver(ws)),
            ]
        )


def main():
    asyncio.get_event_loop().run_until_complete(run())


def _play(audio_out, stream, stop):
    while not stop.is_set():
        try:
            # Janus sync queue mimics the API of queue.Queue, and async queue mimics the API of
            # asyncio.Queue. So for this line check these docs:
            # https://docs.python.org/3/library/queue.html#queue.Queue.get.
            #
            # The timeout of 0.05 is to prevent this line from going into an uninterruptible wait,
            # which can interfere with shutting down the program on some systems.
            data = audio_out.sync_q.get(True, 0.05)

            # In PyAudio's "blocking mode," the `write` function will block until playback is
            # finished. This is why we can stop playback very quickly by simply stopping this loop;
            # there is never more than 1 chunk of audio awaiting playback inside PyAudio.
            # Read more: https://people.csail.mit.edu/hubert/pyaudio/docs/#example-blocking-mode-audio-i-o
            stream.write(data)

        except queue.Empty:
            pass


class Speaker:
    def __init__(self):
        self._queue = None
        self._stream = None
        self._thread = None
        self._stop = None

    def __enter__(self):
        audio = pyaudio.PyAudio()
        self._stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=AGENT_AUDIO_SAMPLE_RATE,
            input=False,
            output=True,
        )
        self._queue = janus.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=_play, args=(self._queue, self._stream, self._stop), daemon=True
        )
        self._thread.start()

    def __exit__(self, exc_type, exc_value, traceback):
        self._stop.set()
        self._thread.join()
        self._stream.close()
        self._stream = None
        self._queue = None
        self._thread = None
        self._stop = None

    async def play(self, data):
        return await self._queue.async_q.put(data)

    def stop(self):
        if self._queue and self._queue.async_q:
            while not self._queue.async_q.empty():
                try:
                    self._queue.async_q.get_nowait()
                except janus.QueueEmpty:
                    break


async def inject_agent_message(ws, inject_message):
    """Simple helper to inject an agent message."""
    logger.info(f"Sending InjectAgentMessage: {json.dumps(inject_message)}")
    await ws.send(json.dumps(inject_message))

async def close_websocket_with_timeout(ws, timeout=5):
    """Close websocket with timeout to avoid hanging if no close frame is received."""
    try:
        await asyncio.wait_for(ws.close(), timeout=timeout)
    except Exception as e:
        logger.error(f"Error during websocket closure: {e}")

async def wait_for_farewell_completion(ws, speaker, inject_message):
    """Wait for the farewell message to be spoken completely by the agent."""
    # Send the farewell message
    await inject_agent_message(ws, inject_message)
    
    # First wait for either AgentStartedSpeaking or matching ConversationText
    speaking_started = False
    while not speaking_started:
        message = await ws.recv()
        if isinstance(message, bytes):
            await speaker.play(message)
            continue
            
        try:
            message_json = json.loads(message)
            logger.info(f"Server: {message}")
            if (message_json.get("type") == "AgentStartedSpeaking" or 
                (message_json.get("type") == "ConversationText" and 
                 message_json.get("role") == "assistant" and 
                 message_json.get("content") == inject_message["message"])):
                speaking_started = True
        except json.JSONDecodeError:
            continue
    
    # Then wait for AgentAudioDone
    audio_done = False
    while not audio_done:
        message = await ws.recv()
        if isinstance(message, bytes):
            await speaker.play(message)
            continue
            
        try:
            message_json = json.loads(message)
            logger.info(f"Server: {message}")
            if message_json.get("type") == "AgentAudioDone":
                audio_done = True
        except json.JSONDecodeError:
            continue
            
    # Give audio time to play completely
    await asyncio.sleep(3.5)


if __name__ == "__main__":
    sys.exit(main() or 0)
