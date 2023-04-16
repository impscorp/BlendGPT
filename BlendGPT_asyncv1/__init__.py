bl_info = {
    "name": "ChatGPT Integration",
    "author": "Jonas Voegel",
    "version": (1, 0),
    "blender": (3, 5, 0),
    "location": "View3D > Tool Shelf > ChatGPT",
    "description": "Interact with ChatGPT using the OpenAI API",
    "warning": "",
    "wiki_url": "",
    "category": "Development",
    "api_key": "",
}
import concurrent.futures
import bpy
import sys
sys.path.append('/Users/jonasvogel/Desktop/BlendGPT 2/venv/lib/python3.10/site-packages')

import openai
import aiohttp
import asyncio

# Store the Blender version number
blender_version = f"{bpy.app.version_string}"

class ChatGPTSettings(bpy.types.PropertyGroup):
    model: bpy.props.EnumProperty(
        name="Model",
        description="Choose the GPT model",
        items=[
            ("gpt-3.5-turbo", "3.5", "gpt-3.5-turbo"),
            ("gpt-4", "gpt-4", "gpt-4"),
            ("gpt-4-0314", "gpt-4-0314", "gpt-4-0314"),
            ("gpt-4-32k", "gpt-4-32k", "gpt-4-32k"),
            ("gpt-3.5-turbo-0301", "gpt-3.5-turbo-0301", "gpt-3.5-turbo-0301"),
        ],
        default="gpt-3.5-turbo",
    )
    user_prompt: bpy.props.StringProperty(
        name="Your Prompt",
        description="Enter your prompt for ChatGPT",
        maxlen=1024,
        default="",
    )


class ChatGPTAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    api_key: bpy.props.StringProperty(
        name="API Key",
        description="Enter your OpenAI API Key",
        maxlen=1024,
        subtype="PASSWORD",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "api_key")

class ChatGPT_PT_Panel(bpy.types.Panel):
    bl_label = "ChatGPT"
    bl_idname = "ChatGPT_PT_Panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ChatGPT"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.chat_gpt_settings

        layout.prop(settings, "model")
        layout.prop(settings, "user_prompt")
        layout.operator("chat_gpt.communicate")


class ChatGPT_OT_Communicate(bpy.types.Operator):
    bl_idname = "chat_gpt.communicate"
    bl_label = "Communicate with ChatGPT"
    bl_options = {"REGISTER"}

    def __init__(self):
        self.finished = False

    async def communicate_coroutine(self, context):
        addon_prefs = context.preferences.addons[__name__].preferences
        settings = context.scene.chat_gpt_settings
        openai.api_key = addon_prefs.api_key

        messages = [
            {"role": "system", "content": f"You are a code-only assistant for Blender {blender_version}. Your task is to provide answers strictly in the form of code without any additional explanation, comments, or notes."},
            {"role": "user", "content": f"Code only: {settings.user_prompt.replace('/n', '')}"},
        ]

        total_input_tokens = sum([len(message["content"]) for message in messages])

        if settings.model.startswith("gpt-3.5-turbo"):
            max_output_tokens = 4096 - total_input_tokens
        elif settings.model.startswith("gpt-4"):
            max_output_tokens = 8192 - total_input_tokens
        elif settings.model == "gpt-4-32k":
            max_output_tokens = 32768 - total_input_tokens
        else:
            max_output_tokens = 4096 - total_input_tokens

        if max_output_tokens <= 0:
            bpy.ops.ui.popup_message(
                message="Input is too long. Please shorten it.",
                title="Error",
                icon="ERROR",
            )
            self.finished = True
            return

        async with aiohttp.ClientSession() as session:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {openai.api_key}",
            }

            data = {
                "model": settings.model,
                "messages": messages,
                "max_tokens": max_output_tokens,
                "n": 1,
                "temperature": 0.8,
            }

            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=data,
            ) as resp:
                response = await resp.json()

        text_block = bpy.data.texts.new("ChatGPT_Response.txt")
        message = response['choices'][0]['message']['content'].strip()

        message = message.replace("```", "")
        message = message.replace("python", "")

        text_block.from_string(message)

        for area in bpy.context.screen.areas:
            if area.type == 'TEXT_EDITOR':
                area.spaces[0].text = text_block
                area.spaces[0].top = 0

        try:
            exec(message, globals())

        except Exception as e:
            message=f"Error executing script: {str(e)}",

        self.finished = True

    def execute(self, context):
        self.finished = False

        loop = asyncio.get_event_loop()
        task = loop.create_task(self.communicate_coroutine(context))
        task.add_done_callback(self.async_callback)

        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if self.finished:
            return {'FINISHED'}
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        return {'CANCELLED'}

    def async_callback(self, future):
        if future.exception() is not None:
            # Handle the exception if the future raised one
            print(f"Exception: {future.exception()}")
            return

        # Get the result from the future
        result = future.result()

        # Set the finished flag to True
        self.finished = True

        # Remove the event timer
        bpy.context.window_manager.event_timer_remove(self._timer)


def register():
    bpy.utils.register_class(ChatGPTAddonPreferences)
    bpy.utils.register_class(ChatGPTSettings)
    bpy.types.Scene.chat_gpt_settings = bpy.props.PointerProperty(type=ChatGPTSettings)
    bpy.utils.register_class(ChatGPT_PT_Panel)
    bpy.utils.register_class(ChatGPT_OT_Communicate)

def unregister():
    bpy.utils.unregister_class(ChatGPTAddonPreferences)
    bpy.utils.unregister_class(ChatGPTSettings)
    del bpy.types.Scene.chat_gpt_settings
    bpy.utils.unregister_class(ChatGPT_PT_Panel)
    bpy.utils.unregister_class(ChatGPT_OT_Communicate)

if __name__ == "__main__":
    register()