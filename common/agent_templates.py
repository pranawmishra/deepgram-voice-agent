from common.agent_functions import FUNCTION_DEFINITIONS
from common.prompt_templates import PROMPT_TEMPLATE
from datetime import datetime
import os
import glob





VOICE = "aura-2-thalia-en"

# audio settings
USER_AUDIO_SAMPLE_RATE = 48000
USER_AUDIO_SECS_PER_CHUNK = 0.05
USER_AUDIO_SAMPLES_PER_CHUNK = round(USER_AUDIO_SAMPLE_RATE * USER_AUDIO_SECS_PER_CHUNK)

AGENT_AUDIO_SAMPLE_RATE = 16000
AGENT_AUDIO_BYTES_PER_SEC = 2 * AGENT_AUDIO_SAMPLE_RATE

VOICE_AGENT_URL = "wss://agent.deepgram.com/v1/agent/converse"

AUDIO_SETTINGS = {
    "input": {
        "encoding": "linear16",
        "sample_rate": USER_AUDIO_SAMPLE_RATE,
    },
    "output": {
        "encoding": "linear16",
        "sample_rate": AGENT_AUDIO_SAMPLE_RATE,
        "container": "none",
    },
}

LISTEN_SETTINGS = {
    "provider": {
        "type": "deepgram",
        "model": "nova-3",
    }
}

THINK_SETTINGS = {
    "provider": {
        "type": "open_ai",
        "model": "gpt-4o-mini",
        "temperature": 0.7,
    },
    "prompt": PROMPT_TEMPLATE.format(
        current_date=datetime.now().strftime("%A, %B %d, %Y")
    ),
    "functions": FUNCTION_DEFINITIONS,
}

SPEAK_SETTINGS = {
    "provider": {
        "type": "deepgram",
        "model": VOICE,
    }
}

AGENT_SETTINGS = {
    "language": "en",
    "listen": LISTEN_SETTINGS,
    "think": THINK_SETTINGS,
    "speak": SPEAK_SETTINGS,
    "greeting": "",
}

SETTINGS = {"type": "Settings", "audio": AUDIO_SETTINGS, "agent": AGENT_SETTINGS}


class AgentTemplates:
    def __init__(
        self,
        industry="tech_support",
        voiceModel="aura-2-thalia-en",
        voiceName="",
    ):
        self.voiceModel = voiceModel
        if voiceName == "":
            self.voiceName = self.get_voice_name_from_model(self.voiceModel)
        else:
            self.voiceName = voiceName

        self.personality = ""
        self.company = ""
        self.first_message = ""
        self.capabilities = ""

        self.industry = industry

        self.voice_agent_url = VOICE_AGENT_URL
        self.settings = SETTINGS
        self.user_audio_sample_rate = USER_AUDIO_SAMPLE_RATE
        self.user_audio_secs_per_chunk = USER_AUDIO_SECS_PER_CHUNK
        self.user_audio_samples_per_chunk = USER_AUDIO_SAMPLES_PER_CHUNK
        self.agent_audio_sample_rate = AGENT_AUDIO_SAMPLE_RATE
        self.agent_audio_bytes_per_sec = AGENT_AUDIO_BYTES_PER_SEC

        match self.industry:
            case "tech_support":
                self.tech_support()
            case "healthcare":
                self.healthcare()
            case "banking":
                self.banking()
            case "pharmaceuticals":
                self.pharmaceuticals()
            case "retail":
                self.retail()
            case "travel":
                self.travel()

        self.first_message = f"Hello! I'm {self.voiceName} from {self.company} customer service. {self.capabilities} How can I help you today?"

        self.settings["agent"]["speak"]["provider"]["model"] = self.voiceModel
        self.settings["agent"]["think"]["prompt"] = self.prompt
        self.settings["agent"]["greeting"] = self.first_message

        self.prompt = self.personality + "\n\n" + self.prompt

    def tech_support(
        self, company="TechStyle", agent_voice="aura-2-thalia-en", voiceName=""
    ):
        if voiceName == "":
            voiceName = self.get_voice_name_from_model(agent_voice)
        self.voiceName = voiceName
        self.company = company
        self.voiceModel = agent_voice

        self.personality = f"You are {self.voiceName}, a friendly and professional customer service representative for {self.company}, an online electronics and accessories retailer. Your role is to assist customers with orders, appointments, and general inquiries."

        self.capabilities = "I'd love to help you with your order or appointment."

    def tech_support(self, company="TechStyle"):
        self.company = company
        self.personality = f"You are {self.voiceName}, a friendly and professional customer service representative for {self.company}, a tech-forward company who uses technology to improve the lives of their customers. Your role is to assist potential customers about their applications and services."
        self.capabilities = "I can help you answer questions about our tech."

    def healthcare(self, company="HealthFirst"):
        self.company = company
        self.personality = f"You are {self.voiceName}, a compassionate and knowledgeable healthcare assistant for {self.company}, a leading healthcare provider. Your role is to assist patients with general information about their appointments and orders."
        self.capabilities = "I can help you answer questions about healthcare."

    def banking(self, company="SecureBank"):
        self.company = company
        self.personality = f"You are {self.voiceName}, a professional and trustworthy banking representative for {self.company}, a secure financial institution. Your role is to assist customers with general information about their accounts and transactions."
        self.capabilities = "I can help you answer questions about banking."

    def pharmaceuticals(self, company="MedLine"):
        self.company = company
        self.personality = f"You are {self.voiceName}, a professional and trustworthy pharmaceutical representative for {self.company}, a secure pharmaceutical company. Your role is to assist customers with general information about their prescriptions and orders."
        self.capabilities = "I can help you answer questions about pharmaceuticals."

    def retail(self, company="StyleMart"):
        self.company = company
        self.personality = f"You are {self.voiceName}, a friendly and attentive retail associate for {self.company}, a trendy clothing and accessories store. Your role is to assist customers with general information about their orders and transactions."
        self.capabilities = "I can help you answer questions about retail."

    def travel(self, company="TravelTech"):
        self.company = company
        self.personality = f"You are {self.voiceName}, a friendly and professional customer service representative for {self.company}, a tech-forward travel agency. Your role is to assist customers with general information about their travel plans and orders."
        self.capabilities = "I can help you answer questions about travel."

    @staticmethod
    def get_available_industries():
        """Return a dictionary of available industries with display names"""
        return {
            "tech_support": "Tech Support",
            "healthcare": "Healthcare",
            "banking": "Banking",
            "pharmaceuticals": "Pharmaceuticals",
            "retail": "Retail",
            "travel": "Travel",
        }

    def get_voice_name_from_model(self, model):
        return (
            model.replace("aura-2-", "").replace("aura-", "").split("-")[0].capitalize()
        )
