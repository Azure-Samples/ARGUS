import json
from mcp import ClientSession
from mcp.types import TextContent, ImageContent
import os
import re
from aiohttp import ClientSession
import chainlit as cl
from openai import AzureOpenAI, AsyncAzureOpenAI
import traceback
from dotenv import load_dotenv
load_dotenv()

SYSTEM_PROMPT = "you are a helpful assistant."

class ChatClient:
    def __init__(self) -> None:
        self.deployment_name = os.environ["AZURE_OPENAI_MODEL"]
        self.client = AsyncAzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.environ["OPENAI_API_VERSION"]
        )
        self.messages = []
        self.system_prompt = SYSTEM_PROMPT
        self.active_streams = []  # Track active response streams

    async def _cleanup_streams(self):
        """Helper method to clean up all active streams"""
        for stream in self.active_streams:
            try:
                await stream.aclose()
            except Exception:
                pass
        self.active_streams = []

    async def process_response_stream(self, response_stream, tools, temperature=0):
        """
        Process response stream to handle function calls without recursion.
        """
        function_arguments = ""
        function_name = ""
        tool_call_id = ""
        is_collecting_function_args = False
        collected_messages = []
        tool_called = False

        # Add to active streams for cleanup if needed
        self.active_streams.append(response_stream)

        try:
            async for part in response_stream:
                if part.choices == []:
                    continue
                delta = part.choices[0].delta
                finish_reason = part.choices[0].finish_reason

                # Process assistant content
                if delta.content:
                    collected_messages.append(delta.content)
                    yield delta.content

                # Handle tool calls
                if delta.tool_calls:
                    if len(delta.tool_calls) > 0:
                        tool_call = delta.tool_calls[0]

                        # Get function name
                        if tool_call.function.name:
                            function_name = tool_call.function.name
                            tool_call_id = tool_call.id

                        # Process function arguments delta
                        if tool_call.function.arguments:
                            function_arguments += tool_call.function.arguments
                            is_collecting_function_args = True

                # Check if we've reached the end of a tool call
                if finish_reason == "tool_calls" and is_collecting_function_args:
                    # Process the current tool call
                    print(f"function_name: {function_name} function_arguments: {function_arguments}")
                    function_args = json.loads(function_arguments)
                    mcp_tools = cl.user_session.get("mcp_tools", {})
                    mcp_name = None
                    for connection_name, session_tools in mcp_tools.items():
                        if any(tool.get("name") == function_name for tool in session_tools):
                            mcp_name = connection_name
                            break

                    # Add the assistant message with tool call
                    self.messages.append({
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": tool_call_id,
                                "function": {
                                    "name": function_name,
                                    "arguments": function_arguments
                                },
                                "type": "function"
                            }
                        ]
                    })

                    # Safely close the current stream before starting a new one
                    if response_stream in self.active_streams:
                        self.active_streams.remove(response_stream)
                        await response_stream.close()

                    # Call the tool and add response to messages
                    func_response = await call_tool(mcp_name, function_name, function_args)
                    print(f"Function Response: {json.loads(func_response)}")
                    self.messages.append({
                        "tool_call_id": tool_call_id,
                        "role": "tool",
                        "name": function_name,
                        "content": json.loads(func_response),
                    })

                    # Set flag that tool was called and store the function name
                    self.last_tool_called = function_name
                    tool_called = True
                    break  # Exit the loop instead of returning

                # Check if we've reached the end of assistant's response
                if finish_reason == "stop":
                    # Add final assistant message if there's content
                    if collected_messages:
                        final_content = ''.join([msg for msg in collected_messages if msg is not None])
                        if final_content.strip():
                            self.messages.append({"role": "assistant", "content": final_content})

                    # Remove from active streams after normal completion
                    if response_stream in self.active_streams:
                        self.active_streams.remove(response_stream)
                    break  # Exit the loop instead of returning

        except GeneratorExit:
            # Clean up this specific stream without recursive cleanup
            if response_stream in self.active_streams:
                self.active_streams.remove(response_stream)
                await response_stream.aclose()
            #raise
        except Exception as e:
            print(f"Error in process_response_stream: {e}")
            traceback.print_exc()
            if response_stream in self.active_streams:
                self.active_streams.remove(response_stream)
            self.last_error = str(e)

        # Store result in instance variables
        self.tool_called = tool_called
        self.last_function_name = function_name if tool_called else None

    async def generate_response(self, human_input, tools, temperature=0):

        self.messages.append({"role": "user", "content": human_input})
        print(f"self.messages: {self.messages}")
        # Handle multiple sequential function calls in a loop rather than recursively
        while True:
            response_stream = await self.client.chat.completions.create(
                model=self.deployment_name,
                messages=self.messages,
                tools=tools,
                # parallel_tool_calls=False, (param not supported by o3-mini)
                stream=True,
                # temperature=temperature (param not supported by o3-mini)
            )

            try:
                # Stream and process the response
                async for token in self._stream_and_process(response_stream, tools, temperature):
                    yield token

                # Check instance variables after streaming is complete
                if not self.tool_called:
                    break
                # Otherwise, loop continues for the next response that follows the tool call
            except GeneratorExit:
                # Ensure we clean up when the client disconnects
                await self._cleanup_streams()
                return

    async def _stream_and_process(self, response_stream, tools, temperature):
        """Helper method to yield tokens and return process result"""
        # Initialize instance variables before processing
        self.tool_called = False
        self.last_function_name = None
        self.last_error = None

        async for token in self.process_response_stream(response_stream, tools, temperature):
            yield token

        # Don't return values in an async generator - values are already stored in instance variables


def flatten(xss):
    return [x for xs in xss for x in xs]

@cl.on_mcp_connect
async def on_mcp(connection, session: ClientSession):
    result = await session.list_tools()
    tools = [{
        "name": t.name,
        "description": t.description,
        "parameters": t.inputSchema,
    } for t in result.tools]

    mcp_tools = cl.user_session.get("mcp_tools", {})
    mcp_tools[connection.name] = tools
    cl.user_session.set("mcp_tools", mcp_tools)


@cl.step(type="tool")
async def call_tool(mcp_name, function_name, function_args):
    try:
        resp_items = []
        print(f"Function Name: {function_name} Function Args: {function_args}")
        mcp_session, _ = cl.context.session.mcp_sessions.get(mcp_name)
        func_response = await mcp_session.call_tool(function_name, function_args)
        for item in func_response.content:
            if isinstance(item, TextContent):
                resp_items.append({"type": "text", "text": item.text})
            elif isinstance(item, ImageContent):
                resp_items.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{item.mimeType};base64,{item.data}",
                    },
                })
            else:
                raise ValueError(f"Unsupported content type: {type(item)}")

    except Exception as e:
        traceback.print_exc()
        resp_items.append({"type": "text", "text": str(e)})
    return json.dumps(resp_items)

@cl.on_chat_start
async def start_chat():
    client = ChatClient()
    cl.user_session.set("messages", [])
    cl.user_session.set("system_prompt", SYSTEM_PROMPT)

@cl.on_message
async def on_message(message: cl.Message):
    mcp_tools = cl.user_session.get("mcp_tools", {})
    tools = flatten([tools for _, tools in mcp_tools.items()])
    tools = [{"type": "function", "function": tool} for tool in tools]

    # Create a fresh client instance for each message
    client = ChatClient()
    # Restore conversation history
    client.messages = cl.user_session.get("messages", [])

    msg = cl.Message(content="")
    async for text in client.generate_response(human_input=message.content, tools=tools):
        await msg.stream_token(text)

    # Update the stored messages after processing
    cl.user_session.set("messages", client.messages)