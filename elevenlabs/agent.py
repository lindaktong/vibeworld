import assemblyai as aai
from elevenlabs import stream
from elevenlabs.client import ElevenLabs
from openai import OpenAI
from dotenv import load_dotenv
import os

class AI_Assistant:
    def __init__(self):
        load_dotenv()
        aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.elevenlabs_client = ElevenLabs(
            api_key=os.getenv("ELEVENLABS_API_KEY"),
        )
        self.transcriber = None
        # Prompt
        self.full_transcript = [
            {"role": "system", "content": "The user is walking around in a blank 3d virtual world. You are a helpful assistant that can create 3D objects in the world by synthesizing a text prompt and calling an API for the user. Your goal is to respond to the user's ideas and help them add objects to the world. Listen to the user's thoughts. Then, create a prompt for the API describing the new object to add to the world. When it's time to give the API prompt, say, 'Let's create a <insert description of an object>.' Note that the object description should be brief but descriptive, and it should describe a standalone object that can be dropped into a 3d world (i.e. don't describe the background or surroundings of the object). If the user's idea was relatively short, add a few new fun details to the object's description. Don't say anything before 'let's create' since we want the object description to come out fast. Only if they didn't describe an object yet (say, they described a general place but not an object), ask a short follow up question. "},
        ]
    def start_transcription(self):
        self.transcriber = aai.RealtimeTranscriber(
            sample_rate=16000,
            on_data=self.on_data,
            on_error=self.on_error,
            on_open=self.on_open,
            on_close=self.on_close,
            end_utterance_silence_threshold = 1000
        )
        # stream microphone data to assemblyai
        self.transcriber.connect()
        microphone_stream = aai.extras.MicrophoneStream(sample_rate=16000)
        self.transcriber.stream(microphone_stream)
    
    def stop_transcription(self):
        if self.transcriber:
            self.transcriber.close()
            self.transcriber=None

    def on_open(self, session_opened: aai.RealtimeSessionOpened):
        print("Session ID:", session_opened.session_id)
        return

    def on_data(self, transcript: aai.RealtimeTranscript):
        if not transcript.text:
            return
        if isinstance(transcript, aai.RealtimeFinalTranscript):
            # print(transcript.text, end="\r\n")
            self.generate_ai_response(transcript.text)
        else:
            print(transcript.text, end="\r")

    def on_error(self, error: aai.RealtimeError):
        print("An error occurred:", error)
        return

    def on_close(self):
        # print("Closing Session")
        pass

    def generate_ai_response(self, transcript: str):
        self.stop_transcription()
        self.full_transcript.append({"role": "user", "content": transcript})
        print(f"\nUser: {transcript}", end="\n")
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=self.full_transcript,
            temperature=0.5,
        )

        ai_response = response.choices[0].message.content
        self.generate_audio(ai_response)
        self.start_transcription()

    def generate_audio(self, text: str):
        self.full_transcript.append({"role": "assistant", "content": text})
        print(f"\nAI: {text}", end="\n")
        audio_stream = self.elevenlabs_client.text_to_speech.convert(
            text=text,
            voice_id="JBFqnCBsd6RMkjVDRZzb",
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )
        stream(audio_stream)

greeting = "Hello! What do you want to explore today?"
ai_assistant = AI_Assistant()
ai_assistant.generate_audio(greeting)
ai_assistant.start_transcription()
