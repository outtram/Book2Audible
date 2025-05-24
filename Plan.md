<?xml version="1.0" encoding="UTF-8"?>
<project_brief>
    <project_info>
        <title>Book to Audio Conversion - MVP</title>
        <date>2025-05-24</date>
        <client_location>Bentleigh East, VIC, Australia</client_location>
    </project_info>
    <project_scope>
        <description>Convert a 200,000 character book into audio format, broken down into chapter-based WAV files. Orpheus TTS using the Tara voice for this book. It is a book on ADHD and needs to have perfect output.</description>
        <deliverables>
            <item>Individual WAV files per chapter</item>
            <item>High-quality text-to-speech conversion</item>
            <item>Seamless audio output</item>
        </deliverables>
        <research>
            <item>I want to use this website to host the orpheus tts model https://www.baseten.co/blog/canopy-labs-selects-baseten-as-preferred-inference-provider-for-orpheus-tts-model/#benchmarking-real-time-speech-synthesis
            </item> 
            <item>there is some example implementation code here that i think could help speed things up for you. https://github.com/canopyai/Orpheus-TTS/blob/main/additional_inference_options/baseten_inference_example/call_orpheus.py
            </item>
        </research>
    </project_scope>
    <technical_requirements>
        <text_to_speech>
            <model>Orpheus model hosted on Bastion</model>
            <output_format>WAV files</output_format>
            <voice_requirements>To be defined with client</voice_requirements>
        </text_to_speech>
        <audio_handling>
            <file_length_limitation>Research Bastion's maximum audio length per file</file_length_limitation>
            <splitting_stitching>Implement solution to split and stitch audio if needed</splitting_stitching>
            <quality_assurance>Ensure seamless final audio files</quality_assurance>
        </audio_handling>
    </technical_requirements>
    <development_approach>
        <user_stories>
            <story>As a user, I want to upload my book text and receive audio files organized by chapter</story>
            <story>As a user, I want high-quality audio that sounds natural and professional</story>
            <story>As a user, I want the process to handle large text files efficiently</story>
            <story>As a user, I want to see detailed log files of whats going in and out of the audio processing invluding verification of each chunk.</story>
        </user_stories>
        <testing_requirements>
            <unit_tests>Test individual components and functions</unit_tests>
            <integration_tests>Test text-to-speech conversion pipeline</integration_tests>
            <quality_tests>Verify audio quality and file integrity</quality_tests>
            <quality_tests>Will need to use a speech to text tool of some sort to check the words in the wav audio file match the words that were sent to the get processed. This book is written in english, australian, british. So it's important that when sending and checking we are looking at words such as "proritistion" and dont put a "z" in it for example.</quality_tests>
        </testing_requirements>
        <code_standards>
            <structure>Modular, maintainable code organization</structure>
            <documentation>Clear documentation for setup and usage</documentation>
            <error_handling>Robust error handling for API limitations and failures</error_handling>
        </code_standards>
    </development_approach>
    <deliverable_timeline>
        <phase1>Research Bastion API limitations and setup</phase1>
        <phase2>Implement text processing and chapter division</phase2>
        <phase3>Integrate text-to-speech conversion</phase3>
        <phase4>Testing and quality assurance</phase4>
    </deliverable_timeline>
</project_brief>